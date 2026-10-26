#!/usr/bin/env python3
"""P1+ HQ: declared-delay HPSS oracle, source-known mixtures and phase controls.

No carrier-level or latency veto. Source labels and residual models define only
these controlled experiments; they do not become labels for unknown music.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import windows
import research_p1plus as P
import test_engine as T
from vb_quality.stage_capture import INDEX as I


def power(x): return float(np.mean(np.asarray(x,dtype=float)**2))
def db_ratio(a,b): return float(10*np.log10(max(a,1e-30)/max(b,1e-30)))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def offline_hpss(band, centered, prominence=False):
    """Independent vectorized rFFT/median/OLA; periodic Hann, 192/16 at 3 kHz.

    Returns source-clock H/P before the known 191 (+80) core-sample delay.
    Zero time-boundary extension, nearest frequency-boundary extension match
    the specified filters. No native renderer or candidate output is an oracle.
    """
    x=np.asarray(band,float);win=windows.hann(192,sym=False)
    frames=sliding_window_view(np.pad(x,(191,0)),192)[15::16]*win
    spec=np.fft.rfft(frames,axis=1);mag=abs(spec)
    pad=(5,5) if centered else (10,0)
    hm=np.median(sliding_window_view(np.pad(mag,(pad,(0,0))),11,axis=0),axis=-1)
    pm=np.median(sliding_window_view(np.pad(mag,((0,0),(3,3)),mode='edge'),7,axis=1),axis=-1)
    mask=hm**2/(hm**2+pm**2+1e-20)
    if prominence:
        past=np.median(sliding_window_view(np.pad(mag,((10,0),(0,0))),11,axis=0),axis=-1)
        causal=past**2/(past**2+pm**2+1e-20)
        weight=np.clip((mag/(pm+1e-20)-1)/(np.sqrt(10)-1),0,1)
        mask=causal+weight*(mask-causal)
    hf=np.fft.irfft(spec*mask,n=192,axis=1)
    h=np.zeros(len(x));p=np.zeros(len(x))
    for j in range(len(frames)-(5 if centered else 0)):
        positions=j*16+15-191+np.arange(192)
        valid=(positions>=0)&(positions<len(x))
        h[positions[valid]]+=(hf[j]*win)[valid]
        p[positions[valid]]+=((frames[j]-hf[j])*win)[valid]
    norm=np.array([np.sum(win[r::16]**2) for r in range(16)])
    return h/norm[np.arange(len(x))%16],p/norm[np.arange(len(x))%16]


def oracle_check(lib):
    fs=48000;t=np.arange(fs*2)/fs;rng=np.random.default_rng(2026102603)
    x=.1*np.cos(2*np.pi*61*t)+rng.normal(0,.08,len(t))*np.exp(-((t-.87)/.015)**2)
    rows=[]
    for flags in (0,4,6,14):
        actual=P.render(lib,x,fs,flags)
        z=actual['stages'];delay=191+(80 if flags&4 else 0)
        rh,rp=offline_hpss(z[:,I['band']],bool(flags&4),bool(flags&8))
        a,b=900,len(z)-600-delay
        h=z[a+delay:b+delay,I['original_h']];p=z[a+delay:b+delay,I['original_p']]
        eh=db_ratio(power(h-rh[a:b]),power(rh[a:b]))
        ep=db_ratio(power(p-rp[a:b]),power(rp[a:b]))
        complement=float(np.max(abs(h+p-z[a+delay:b+delay,I['band_delayed191']])))
        assert eh<-180 and ep<-180,(flags,eh,ep)
        assert complement<1e-10,(flags,complement)
        rows.append(dict(flags=flags,h_nmse_db=eh,p_nmse_db=ep,complement_max_error=complement))
    return rows


def engineering(lib,old,phase,flags=14):
    rows=[]
    for fs in (44100,48000):
        t=np.arange(fs*3)/fs
        x=.12*np.cos(2*np.pi*55*t)+.0012*(1+.8*np.sin(2*np.pi*2*t))*np.cos(2*np.pi*165*t+1.7)
        ref=P.render(old,x,fs,0);off=P.render(lib,x,fs,0)
        assert np.array_equal(ref['output'],off['output'])
        prev=P.render(phase,x,fs,2);current=P.render(lib,x,fs,2)
        assert np.array_equal(prev['output'],current['output'])
        candidate=P.render(lib,x,fs,flags);chunk=P.render(lib,x,fs,flags,block=1379)
        assert np.array_equal(candidate['output'],chunk['output'])
        assert np.array_equal(candidate['stages'],chunk['stages'])
        capture_off=P.render(lib,x,fs,flags,capture=False)
        assert np.array_equal(candidate['output'],capture_off['output'])
        extra=round(fs*80/3000)
        assert candidate['latency']==off['latency']+extra,(fs,candidate['latency'],off['latency'],extra)
        future=x.copy();future[int(1.7*fs):]*=-1
        altered=P.render(lib,future,fs,flags)
        assert np.array_equal(candidate['output'][:int(1.7*fs)],altered['output'][:int(1.7*fs)])
        assert np.all(candidate['rows'][:,8]==271)
        for algo in (7,8,9,10):
            a=P.render(lib,x[:fs],fs,0,algo=algo);b=P.render(lib,x[:fs],fs,flags,algo=algo)
            assert np.array_equal(a['output'],b['output']) and a['latency']==b['latency']
        e=T.Engine(lib,fs,vb_on=1,vb_algo=6,vb_level_db=6,out_db=-18,ramp_ms=0)
        try:
            assert lib.pvb_set_p1plus_research(e.h,flags)==1
            assert lib.pvb_set_p1plus_research(e.h,8)==0
            assert lib.pvb_set_p1plus_research(e.h,16)==0
            e.process(T.stereo(x[:fs]));lib.pvb_reset(e.h)
            silent=e.process(np.zeros((fs,2),np.float32))
            assert np.max(abs(silent))<1e-7
        finally:e.close()
        # A constant harmonic source should not acquire an extra relative phase
        # rotation simply because both source and dry paths are delayed.
        steady=.12*np.cos(2*np.pi*55*t)
        a=P.render(lib,steady,fs,2);b=P.render(lib,steady,fs,flags)
        lo=round(1.3*fs);hi=round(2.5*fs)
        align=db_ratio(power(b['output'][lo+extra:hi+extra]-a['output'][lo:hi]),power(a['output'][lo:hi]))
        assert align<-70,('steady delay/phase alignment',fs,align)
        rows.append(dict(fs=fs,flags=flags,default_bit_exact=True,phase_v01_bit_exact=True,
                         block_and_capture_bit_exact=True,prefix_causal=True,reset=True,
                         other_profiles_bit_exact=True,latency=candidate['latency'],
                         extra_latency_frames=extra,extra_latency_ms=extra/fs*1000,
                         steady_aligned_nmse_db=align))
    return rows


def mixtures(fs,heldout=False):
    t=np.arange(round(fs*4.5))/fs
    rng=np.random.default_rng(2026102604 if heldout else 2026102603)
    count=8 if heldout else 4
    for j in range(count):
        f=float(rng.uniform(43,125)) if heldout else (55,72,83,64)[j]
        rate=float(rng.uniform(1,9)) if heldout else (0,5,0,0)[j]
        h=.09*(1+.35*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*f*t+.3)
        short=bool(j%4==2)
        if short:
            env=np.zeros(len(t))
            for start in (.55,1.3,2.25,3.4):
                dt=t-start;env+=np.where((dt>=0)&(dt<.12),np.sin(np.pi*np.clip(dt/.12,0,1))**2,0)
            h*=env
        if j%4==3:
            h=.09*np.cos(2*np.pi*(f*t+3*t*t)+.3)
        p=np.zeros(len(t));centers=(.8,1.6,2.8,3.7)
        width=float(rng.uniform(.006,.028)) if heldout else .012
        noise=rng.normal(0,1,len(t))
        for at in centers:p+=.32*noise*np.exp(-.5*((t-at)/width)**2)
        if j%4==1:
            # A pitched kick is also transient in this declared source model.
            for at in centers:
                dt=np.maximum(0,t-at)
                p+=np.where(t>=at,.07*np.exp(-dt/.04)*np.cos(2*np.pi*(150*dt-160*dt*dt)),0)
        yield f'{"held" if heldout else "dev"}_mix_{j}',h,p,dict(frequency=f,am_rate=rate,noise_width=width,short_notes=short)


def separation(lib,h,p,fs):
    truth_h=P.render(lib,h,fs,0)['stages'][:,I['band']]
    truth_p=P.render(lib,p,fs,0)['stages'][:,I['band']]
    results={}
    for flags in (0,2,4,6,14):
        r=P.render(lib,h+p,fs,flags);z=r['stages'];delay=191+(80 if flags&4 else 0)
        # Identical source-clock interval for every variant, regardless of its
        # output delay. Leave the maximum delay as the common end margin.
        a,b=900,len(z)-1200-271
        actual_h=z[a+delay:b+delay,I['original_h']]
        actual_p=z[a+delay:b+delay,I['original_p']]
        rh,rp=truth_h[a:b],truth_p[a:b]
        error=actual_h-rh
        # The truth is filtered component input, not the candidate's chosen gain.
        results[str(flags)]=dict(h_error_nmse_db=db_ratio(power(error),power(rh)),
                                 p_error_nmse_db=db_ratio(power(actual_p-rp),power(rp)),
                                 h_gain_change_db=db_ratio(power(actual_h),power(rh)),
                                 h_error_peak=float(np.max(abs(error))),
                                 source_evaluation_start_core=a,source_evaluation_end_core=b,
                                 full_mix_rms_dbfs=db_ratio(power(r['output']),1),
                                 stem_rms_dbfs=db_ratio(power(r['stem']),1),latency=r['latency'])
        assert np.max(abs(z[a+delay:b+delay,I['band_delayed191']]-(rh+rp)))<1e-7
    return results


def phase_cases(lib,fs):
    rng=np.random.default_rng(2026102605);t=np.arange(fs*5)/fs;rows=[]
    for j in range(8):
        f=float(rng.uniform(42,111));rate=float(rng.uniform(1.3,8.6));ph=float(rng.uniform(-np.pi,np.pi))
        k=3 if f<75 else 2
        x=.12*np.sin(2*np.pi*f*t+.2)+.0012*(1+.85*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*k*f*t+ph)
        modes={}
        for flag in (0,2,6,14):
            r=P.render(lib,x,fs,flag)
            modes[str(flag)]=dict(support=P.spectral_support(r['stem'],fs,[f],rate),latency=r['latency'])
        rows.append(dict(name=f'phase_holdout_{j}',f=f,rate=rate,phase=ph,variants=modes))
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--previous',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--development-only',action='store_true')
    ap.add_argument('--engineering-only',action='store_true')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    lib=P.api(a.candidate.resolve());old=P.api(a.baseline.resolve());phase=P.api(a.previous.resolve())
    report=dict(schema='pvb.p1hq.v1',candidate_sha256=sha(a.candidate),baseline_sha256=sha(a.baseline),
                previous_sha256=sha(a.previous),level_and_latency_are_costs=True,
                oracle=oracle_check(lib),engineering=engineering(lib,old,phase,6)+engineering(lib,old,phase,14),mixtures={},phase={})
    print('Independent HPSS oracle and engineering checks PASS',flush=True)
    if a.engineering_only:
        report['execution']='completed_engineering_only'
        (a.out/'hq-engineering.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        return
    for held in ((False,) if a.development_only else (False,True)):
        for name,h,p,description in mixtures(48000,held):
            values=separation(lib,h,p,48000)
            report['mixtures'][name]=dict(description=description,variants=values)
            change=values['6']['h_error_nmse_db']-values['2']['h_error_nmse_db']
            print(name,'centered-minus-causal H error dB',round(change,4),flush=True)
            print(name,'prominence-minus-causal H error dB',round(values['14']['h_error_nmse_db']-values['2']['h_error_nmse_db'],4),flush=True)
            (a.out/'hq-study.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    if not a.development_only:
        for fs in (44100,48000):
            report['phase'][str(fs)]=phase_cases(lib,fs)
            print('Fresh phase cases complete',fs,flush=True)
    report['execution']='completed';report['listening_validated']=report['device_validated']=False
    (a.out/'hq-study.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
