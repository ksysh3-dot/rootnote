#!/usr/bin/env python3
"""J2-S strict single AM-family development oracle and full-path measurements.

Three exactly equivalent tones remain ambiguous; symmetry is a hypothesis test,
not source separation. Quality failures are reported, never waived assertions.
"""
import argparse,ctypes as C,hashlib,json,re,time
from pathlib import Path
import numpy as np
import test_modulation_research as P
import test_detail_research as D
from vb_quality import measurement as Q
from vb_quality.stage_capture import INDEX
DP=C.POINTER(C.c_double)

def response(f):
    body=re.search(r'kBandSos\[\d+\] = \{(.*?)\};',Q.TABLE.read_text(),re.S)[1]
    sos=np.fromstring(body.replace('\n',''),sep=',').reshape(4,6)
    z=np.exp(-2j*np.pi*np.asarray(f)/3000);h=np.ones_like(z,dtype=complex)
    for b in sos:h*=(b[0]+b[1]*z+b[2]*z*z)/(1+b[4]*z+b[5]*z*z)
    return h

def direct(lib):
    lib.pvb_am_family_fit.argtypes=[DP,C.c_double,DP]
    rng=np.random.default_rng(2026101805);t=(np.arange(384)-192)/3000;groups={};timing=[]
    for kind in ('am','steady','one_sideband','incoherent_triplet','fm','noise','silence','equivalent_triplet'):
        errors=[];rates=[];depths=[];accepted=0;coherence=[]
        for case in range(48):
            f=rng.uniform(40,120);r=rng.uniform(4.5,22.5);a=.15;phase=rng.uniform(-np.pi,np.pi);mp=rng.uniform(-np.pi,np.pi);depth=rng.uniform(.2,.85)
            freq=np.array([f-r,f,f+r]);z=np.array([-.5j*depth*np.exp(1j*(phase-mp)),np.exp(1j*phase),.5j*depth*np.exp(1j*(phase+mp))])*a
            # sin modulation: lower coefficient +i*m/2, upper -i*m/2.
            z[[0,2]]*=-1
            if kind=='steady':z[[0,2]]=0
            if kind=='one_sideband':z[0]=0
            if kind=='incoherent_triplet':z[0]*=np.exp(1j*1.2)
            x=np.real(np.exp(2j*np.pi*t[:,None]*freq)@(z*response(freq)))
            if kind=='fm':x=a*np.cos(2*np.pi*f*t+phase+.4*np.sin(2*np.pi*r*t+mp))
            if kind=='noise':x=rng.normal(0,a,len(t))
            if kind=='silence':x=np.zeros(len(t))
            x=np.ascontiguousarray(x,np.float64);out=np.zeros(16);start=time.perf_counter()
            ok=lib.pvb_am_family_fit(x.ctypes.data_as(DP),f+.3,out.ctypes.data_as(DP));timing.append(1000*(time.perf_counter()-start))
            assert np.isfinite(out).all();accepted+=ok==1;coherence.append(float(out[8]))
            if ok==1 and kind in ('am','equivalent_triplet'):
                errors.append(abs(1200*np.log2(out[1]/f)));rates.append(abs(out[2]-r));depths.append(abs(np.hypot(out[5],out[6])-depth))
        groups[kind]=dict(cases=48,accepted=accepted,pitch_cents_max=max(errors) if errors else None,
                          rate_error_hz_max=max(rates) if rates else None,depth_error_max=max(depths) if depths else None,
                          coherence_median=float(np.median(coherence)))
    assert groups['am']['accepted']>=46,groups
    assert groups['am']['pitch_cents_max']<1 and groups['am']['rate_error_hz_max']<.1,groups['am']
    for name in ('steady','one_sideband','incoherent_triplet','fm','noise','silence'):
        assert groups[name]['accepted']==0,(name,groups[name])
    for bad in (np.nan,np.inf):
        x=np.zeros(384);x[3]=bad;out=np.zeros(16)
        assert lib.pvb_am_family_fit(x.ctypes.data_as(DP),55,out.ctypes.data_as(DP))==0
    return dict(seed=2026101805,groups=groups,native_fit_ms_p50=float(np.median(timing)),native_fit_ms_p95=float(np.percentile(timing,95)),
                ambiguity='A coherent triplet is mathematically indistinguishable from AM; expected acceptance is not a source label.')

def evaluate(lib,x,kind,flags,carrier,rate,depth):
    r=P.render(lib,x,3,True,tonal=True,stage_flags=flags)
    rows=r['stages'];mask=(rows[:,0]>=3750)&(rows[:,0]<9000)
    result=dict(detail_fraction=float(rows[mask,INDEX['detail_applied']].mean()),family_fraction=float(rows[mask,INDEX['family_applied']].mean()),
                callback_ms_p95=float(np.percentile(r['cost_ms'],95)),full_peak_dbfs=D.T.true_peak_db(r['output']))
    assert result['full_peak_dbfs']<-1
    if kind=='am':result['metrics']=Q.am_harmonics(r['stem'],48000,carrier,rate,depth,algorithm=4,latency=r['latency']/48000,temporal=True)
    if kind=='fm':result['metrics']=Q.fm_harmonics(r['stem'],48000,carrier,rate,depth,algorithm=4,latency=r['latency']/48000,temporal=True)
    if 'metrics' in result:result['quality']=Q.aggregate_am(result['metrics'])
    if kind=='off':
        result['tail_peak']=float(np.max(abs(r['stem'][int(2.8*48000):])));assert result['tail_peak']<1e-7
    return result

def mechanics(lib):
    import research_stage_ablation as A
    checks=A.invariance(lib)
    overlap=Q.am_harmonics(np.zeros(48000),48000,40,20,.7,algorithm=4)
    assert Q.aggregate_am(overlap)=='not_evaluated'
    assert all(q['status']=='overlap_ambiguous' for q in overlap if q['expected_weight']>1e-4)
    streams=[]
    for fs in (44100,48000):
        t=np.arange(int(2.4*fs))/fs
        # The second section invalidates the AM-family hypothesis; returning to
        # a valid AM checks that a rejected cache cannot suppress reacquisition.
        am=.15*(1+.7*np.sin(2*np.pi*20*t))*np.cos(2*np.pi*80*t)
        pair=.1*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6)
        x=np.where((t>=.8)&(t<1.5),pair,am)
        a=P.render(lib,x,3,True,fs=fs,stage_flags=240)
        b=P.render(lib,x,3,True,fs=fs,stage_flags=240,block=1379)
        assert np.array_equal(a['output'],b['output']) and np.array_equal(a['stem'],b['stem']),('chunk',fs)
        assert np.array_equal(a['stages'],b['stages']),('stage_chunk',fs)
        changed=x.copy();changed[int(.7*fs):]*=-1
        c=P.render(lib,changed,3,True,fs=fs,stage_flags=240)
        assert np.array_equal(a['output'][:int(.7*fs)],c['output'][:int(.7*fs)]),('prefix',fs)
        stages=a['stages'];clock=stages[:,0]/3000
        # The aligned analysis includes an old part of the input for128ms.
        rejected=(clock>1.2)&(clock<1.45);recovered=(clock>2.05)&(clock<2.35)
        off=float(stages[rejected,INDEX['family_applied']].mean());on=float(stages[recovered,INDEX['family_applied']].mean())
        assert off==0 and on>.95,('cache invalidate/reacquire',fs,off,on)
        streams.append(dict(fs=fs,block_and_stage_bit_exact=True,prefix_invariant=True,invalid_family_fraction=off,recovered_family_fraction=on))
    return dict(capture_invariance=checks,streams=streams)

def validation(lib):
    # New frequencies/rates/depths after implementation freeze; not a listening
    # validation set, and not promised sealed after this first use.
    rng=np.random.default_rng(2026101806);cases=[];fs=48000;t=np.arange(int(3.4*fs))/fs
    for case in range(8):
        f=float(rng.uniform(50,140));rate=float(rng.uniform(4.5,min(23.,(f-15)/2)));depth=float(rng.uniform(.25,.8))
        x=.15*(1+depth*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*f*t)
        result=evaluate(lib,x,'am',240,f,rate,depth)
        cases.append(dict(carrier=f,rate=rate,depth=depth,result=result));print('validation',case,result.get('quality'),flush=True)
    # Cross-rate filter/time budget: no fixture-dependent delay alignment.
    cross=[]
    for f,rate in ((40,15),(80,20),(120,20)):
        fs=44100;t=np.arange(int(3.4*fs))/fs;x=.15*(1+.7*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*f*t)
        r=P.render(lib,x,3,True,fs=fs,tonal=True,stage_flags=240)
        m=Q.am_harmonics(r['stem'],fs,f,rate,.7,algorithm=4,latency=r['latency']/fs,temporal=True)
        cross.append(dict(fs=fs,carrier=f,rate=rate,metrics=m,quality=Q.aggregate_am(m)))
    return dict(seed=2026101806,cases=cases,cross_rate=cross)

def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',required=True);p.add_argument('--report',required=True);p.add_argument('--direct-only',action='store_true');a=p.parse_args()
    lib=P.api(a.lib);result=dict(schema='pvb.phase2.am_family.v1',measurement_version=Q.VERSION,direct=direct(lib),data_split='development',device='not_evaluated',listening='not_evaluated',
        library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest(),candidates={'18':'D2 + unconditional gain bypass','112':'J2-S -> D2 + conditional gain','240':'J2-S + physical output-filter/time compensation -> D2'})
    if not a.direct_only:
        fs=48000;t=np.arange(int(3.4*fs))/fs;cases={}
        for f in (40,55,80,120):
            for rate in (2,7,15,20):
                x=.15*(1+.7*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*f*t);name=f'am_f{f}_r{rate}';modes={}
                for flags in (18,112,240):
                    modes[str(flags)]=evaluate(lib,x,'am',flags,f,rate,.7)
                    print(name,flags,modes[str(flags)]['quality'],modes[str(flags)]['family_fraction'],flush=True)
                    if flags & 64 and rate>=4:
                        assert modes[str(flags)]['family_fraction']>.95,('family cache/ownership',name,flags)
                    if flags==240 and 2*rate<f:
                        assert modes[str(flags)]['quality']=='pass',('frozen AM engineering gate',name)
                cases[name]=modes
        for name,x,kind in [('fm',Q.fm_tone(fs,len(t),55,7,35),'fm'),('pair',.1*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6),'ambiguous'),('off',.15*np.cos(2*np.pi*55*t)*(t<1.7),'off')]:
            cases[name]={str(flags):evaluate(lib,x,kind,flags,55,7,35) for flags in (18,112,240)}
            if name in ('pair','fm'):
                assert cases[name]['240']['family_fraction']==0,('negative family ownership',name)
            if name=='fm':assert cases[name]['240']['quality']=='pass'
            print(name,'complete',flush=True)
        result['cases']=cases
        result['mechanics']=mechanics(lib)
        result['validation']=validation(lib)
    Path(a.report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['direct'],indent=2),flush=True)
if __name__=='__main__':main()
