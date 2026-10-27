#!/usr/bin/env python3
"""Level-swept finite impacts through frozen P1/P1+: diagnostic, not noise truth."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.signal import butter,sosfilt,hilbert

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
HARNESS=HERE if (HERE/'research_p1plus.py').is_file() else ROOT/'work/p1pp-impact-src/tools/pvb-harness'
sys.path.insert(0,str(HARNESS))
import research_p1plus as P
import test_harmonic_continuity as H
import test_engine as T
from p1plus_paths import default_library


def energy(x):return float(np.sum(np.asarray(x,dtype=float)**2))
def db(a,b=1):return float(10*np.log10(max(a,1e-30)/max(b,1e-30)))


def fixtures(fs=48000):
    n=int(3.2*fs);t=np.arange(n)/fs;onset=1.25
    rng=np.random.default_rng(2026102607)
    for shape,duration in (('noise_bang',.040),('kick_bang',.160)):
        u=t-onset;active=(u>=0)&(u<duration)
        z=np.zeros(n)
        if shape=='noise_bang':
            noise=sosfilt(butter(2,[30,4000],btype='bandpass',fs=fs,output='sos'),rng.normal(size=n))
            z[active]=noise[active]*np.sin(np.pi*u[active]/duration)**2
        else:
            # A short wide-band attack plus a finite decaying pitched impact.
            ph=2*np.pi*(48*u+90*.024*(1-np.exp(-np.maximum(u,0)/.024)))
            env=(1-np.exp(-np.maximum(u,0)/.0008))*np.exp(-np.maximum(u,0)/.035)
            env*=np.minimum(1,np.maximum(0,(duration-u)/.01))
            z[active]=env[active]*np.cos(ph[active])
            noise=rng.normal(size=n)*np.exp(-np.maximum(u,0)/.004)
            z[active]+=.15*noise[active]*np.sin(np.minimum(np.pi/2,u[active]*np.pi/.001))
        z/=np.max(abs(z))
        for bed in (False,True):
            b=.018*np.cos(2*np.pi*55*t+.2)*np.minimum(1,t/.05) if bed else np.zeros(n)
            yield shape,bed,t,b,z,onset,duration


def fresh_fixtures(fs=48000):
    rng=np.random.default_rng(2026102608);t=np.arange(round(3.2*fs))/fs;onset=1.25;u=t-onset
    for j in range(8):
        duration=float(rng.uniform(.08,.22) if j<6 else rng.uniform(.02,.08))
        active=(u>=0)&(u<duration);z=np.zeros_like(t)
        if j<6:
            end=float(rng.uniform(41,70));jump=float(rng.uniform(65,155));tau=float(rng.uniform(.015,.035));decay=float(rng.uniform(.02,.06))
            ph=2*np.pi*(end*u+jump*tau*(1-np.exp(-np.maximum(u,0)/tau)))
            env=(1-np.exp(-np.maximum(u,0)/.001))*np.exp(-np.maximum(u,0)/decay)
            env*=np.minimum(1,np.maximum(0,(duration-u)/.01))
            z[active]=env[active]*np.cos(ph[active])
            z[active]+=.12*rng.normal(size=len(t))[active]*np.exp(-u[active]/.004)
            kind='kick'
        else:
            noise=sosfilt(butter(2,[30,4000],btype='bandpass',fs=fs,output='sos'),rng.normal(size=len(t)))
            z[active]=noise[active]*np.sin(np.pi*u[active]/duration)**2;kind='noise'
        z/=np.max(abs(z));bf=float(rng.uniform(43,103));phase=float(rng.uniform(-np.pi,np.pi))
        b=.018*np.cos(2*np.pi*bf*t+phase)*np.minimum(1,t/.05)
        yield f'fresh_{kind}_{j}',True,t,b,z,onset,duration


def score(r,base,source,impact,t,onset,duration,fs):
    d=r['latency'];y=r['stem'][d:d+len(t),0].astype(float)
    if base is not None:y-=base['stem'][base['latency']:base['latency']+len(t),0]
    source_peak=float(np.max(abs(source)));input_energy=energy(impact)
    masks=dict(pre=(t>=onset-.15)&(t<onset-.005),
               attack=(t>=onset)&(t<onset+duration),
               early_tail=(t>=onset+duration)&(t<onset+duration+.08),
               late_tail=(t>=onset+duration+.08)&(t<onset+duration+.5))
    metrics={k+'_energy_per_input_db':db(energy(y[m]),input_energy) for k,m in masks.items()}
    # A fixed phase/amplitude change of a legitimate background carrier is not
    # noise. Fit constant input-defined harmonics in each diagnostic window.
    # The input bed is a known pure sinusoid here, never estimated from output.
    bed=source-impact
    if base is not None:
        quiet=bed[t>onset+duration+.6]
        c=float(quiet[1:-1]@(quiet[:-2]+quiet[2:])/(2*(quiet[1:-1]@quiet[1:-1])))
        bed_frequency=float(np.arccos(np.clip(c,-1,1))*fs/(2*np.pi))
    else:bed_frequency=None
    metrics['input_bed_frequency']=bed_frequency
    for label in ('pre','early_tail','late_tail'):
        m=masks[label];z=y[m]
        if bed_frequency is None:res=z
        else:
            tt=t[m];basis=np.column_stack([v for k in range(1,9) for v in
                (np.cos(2*np.pi*k*bed_frequency*tt),np.sin(2*np.pi*k*bed_frequency*tt))])
            res=z-basis@np.linalg.lstsq(basis,z,rcond=1e-10)[0]
        metrics[label+'_stationary_residual_per_input_db']=db(energy(res),input_energy)
        if label=='early_tail' and base is not None:
            # Split the early-tail change: the part that is the bed's own generated layer (from the bed-only render)
            # with a gain and a quadrature term varying piecewise linearly over 10 ms knots is a gap, step or phase
            # slip of the legitimate bed (an upper bound of bed loss); the rest is generated energy that is not the
            # bed (a lower bound). In an 80 ms window an extra tone near a bed harmonic cannot be told apart and is
            # partly counted as bed: see check_p1pp_tail_split.py for the controls.
            full=base['stem'][base['latency']:base['latency']+len(t),0].astype(float)
            bs,bq=full[m],np.imag(hilbert(full))[m]
            knots=np.arange(tt[0],tt[-1]+.01,.01);hats=np.clip(1-abs(tt[:,None]-knots[None,:])/.01,0,None)
            mod=np.column_stack([bs[:,None]*hats,bq[:,None]*hats])
            other=z-mod@np.linalg.lstsq(mod,z,rcond=1e-10)[0]
            metrics['early_tail_bed_shaped_per_input_db']=db(max(energy(z)-energy(other),0),input_energy)
            metrics['early_tail_nonbed_per_input_db']=db(energy(other),input_energy)
    event=masks['attack']|masks['early_tail'];peak=float(np.max(abs(y[event])))
    # Recovery relative to this event's generated peak; 30 ms consecutive quiet.
    bins=np.sqrt(np.mean(y[:len(y)//240*240].reshape(-1,240)**2,axis=1))
    bt=(np.arange(len(bins))+.5)*.005;end=onset+duration
    threshold=max(peak*.01,1e-10);recovery=None
    for j in np.where(bt>=end)[0]:
        if j+6<=len(bins) and np.all(bins[j:j+6]<=threshold):recovery=float((bt[j]-end)*1000);break
    rows=r['rows'];tracks=H.tracks(rows);hs=tracks[:,:,14:].reshape(-1,12,7,6)
    ht=(rows[:,0]+rows[:,9])/fs;win=(ht>=onset-.15)&(ht<onset+duration+.4)
    observed=(tracks[:,:,1]==1)|(tracks[:,:,1]==2)
    suspicious=observed&(tracks[:,:,12]>-15)&(tracks[:,:,6]<=-15)
    metrics.update(input_sample_peak=source_peak,generated_delta_peak=peak,
                   generated_peak_per_input_peak_db=20*np.log10(max(peak,1e-30)/max(np.max(abs(impact)),1e-30)),
                   recovery_ms=recovery,onset_hops=int(np.sum(rows[win,24]>0)),
                   onset_raw_mismatch_accepted_track_hops=int(np.sum(suspicious[win])),
                   births=int(np.sum(tracks[win,:,1]==1)),
                   emitted_energy_proxy=float(np.sum(hs[win,:,:,1]**2)),
                   max_output_sample=float(np.max(abs(r['output']))),
                   final_limiter_gr_db=float(r['meters'][T.M['LIM_GR_DB']]),
                   final_limiter_active_pct=float(r['meters'][T.M['LIM_ACTIVE_PCT']]))
    return metrics,y


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--out',type=Path,required=True);p.add_argument('--flags',type=int,nargs='+',default=[0,2,6])
    p.add_argument('--impact-mode',type=int,choices=(0,1,2,3,4),default=0)
    p.add_argument('--fresh',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);lib=P.api(a.library.resolve());fs=48000
    cases=[]
    source_fixtures=fresh_fixtures(fs) if a.fresh else fixtures(fs)
    for shape,bed,t,b,z,onset,duration in source_fixtures:
        for flag in a.flags:
            base=P.render(lib,np.r_[b,np.zeros(fs//2)],fs,flag,impact_mode=a.impact_mode) if bed else None
            soft=None
            for peak_db in ((-24,-12,-6,-1) if a.fresh else (-36,-24,-12,-6,-1)):
                impact=z*10**(peak_db/20);x=b+impact
                assert np.max(abs(x))<1,'No input clipping is allowed'
                r=P.render(lib,np.r_[x,np.zeros(fs//2)],fs,flag,impact_mode=a.impact_mode)
                metrics,y=score(r,base,x,impact,t,onset,duration,fs)
                normalized=y/10**(peak_db/20)
                if soft is None:soft=normalized
                metrics['normalized_shape_change_from_soft_db']=db(energy(normalized-soft),energy(soft))
                row=dict(shape=shape,bed=bed,flags=flag,impact_mode=a.impact_mode,impact_peak_dbfs=peak_db,**metrics)
                cases.append(row)
                if peak_db in (-36,-1):
                    np.savez_compressed(a.out/f'{shape}-bed{int(bed)}-flag{flag}-{abs(peak_db)}.npz',
                                        t=t,x=x,impact=impact,stem_delta=y,stages=r['stages'],hops=r['rows'])
                print(shape,'bed',bed,'flag',flag,'level',peak_db,'late',round(metrics['late_tail_energy_per_input_db'],2),
                      'mismatch',metrics['onset_raw_mismatch_accepted_track_hops'],'recovery',metrics['recovery_ms'],flush=True)
    result=dict(schema='pvb.p1pp.impacts.v1',seed=2026102608 if a.fresh else 2026102607,sample_rate=fs,
                library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                settings=dict(algorithm=6,vb_level_db=6,out_db=-18,ramp_ms=0),
                latency_compensation='Engine-reported frames, no fitted shift',
                note='Late energy and model-mismatch acceptance are diagnostics, not a universal noise label. Bed cases subtract the separately rendered same-mode bed.',
                stationary_residual_definition='Project out constant-amplitude/phase harmonics 1..8 of the known input sinusoidal bed within each window. Retain modulation/other components; no output-derived frequencies.',
                listening_validated=False,device_validated=False,cases=cases)
    (a.out/'impacts.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
