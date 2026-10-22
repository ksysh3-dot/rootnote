#!/usr/bin/env python3
"""D2 development measurements, not learned source labels/listening scores."""
import argparse,ctypes as C,hashlib,json
from pathlib import Path
import numpy as np
import test_modulation_research as P
import test_engine as T
from vb_quality import measurement as Q
from vb_quality.stage_capture import INDEX
HERE=Path(__file__).resolve().parent;DP=C.POINTER(C.c_double)

def fit_controls(lib):
    lib.pvb_detail_fit.argtypes=[DP,C.c_double,C.c_double,DP]
    rng=np.random.default_rng(2026101804);t=(np.arange(96)-48)/3000;groups={}
    for kind in ('steady','am7','am20','fm7','close_pair','noise','silence'):
        errors=[];amplitude_errors=[];accepted=0
        for _ in range(48):
            f=float(rng.uniform(40,120));phase=float(rng.uniform(-np.pi,np.pi));mp=float(rng.uniform(-np.pi,np.pi));a=.15
            amp=np.full(96,a);phi=2*np.pi*f*t+phase;truth_f=f;truth_a=a;slope=0.
            if kind.startswith('am'):
                rate=int(kind[2:]);amp=a*(1+.7*np.sin(2*np.pi*rate*t+mp));truth_a=a*(1+.7*np.sin(mp))
            if kind=='fm7':
                phi+=.2*np.sin(2*np.pi*7*t+mp);truth_f=f+1.4*np.cos(mp);slope=-.2*2*np.pi*49*np.sin(mp)
            x=amp*np.cos(phi)
            if kind=='close_pair':x+=.7*a*np.cos(2*np.pi*(f+3)*t+.6)
            if kind=='noise':x=rng.normal(0,a,96)
            if kind=='silence':x=np.zeros(96)
            x=np.ascontiguousarray(x,np.float64);out=np.zeros(20)
            ok=lib.pvb_detail_fit(x.ctypes.data_as(DP),truth_f,slope,out.ctypes.data_as(DP))
            assert np.isfinite(out).all()
            accepted+=ok==1
            if ok==1 and kind not in ('close_pair','noise','silence'):
                errors.append(abs(1200*np.log2(out[1]/truth_f)));amplitude_errors.append(abs(out[0]-truth_a)/truth_a)
        groups[kind]=dict(cases=48,accepted=int(accepted),pitch_cents_p95=float(np.percentile(errors,95)) if errors else None,
                          amplitude_relative_error_p95=float(np.percentile(amplitude_errors,95)) if amplitude_errors else None)
    assert groups['steady']['accepted']==48 and groups['steady']['pitch_cents_p95']<1e-5
    assert groups['silence']['accepted']==0 and groups['noise']['accepted']==0
    return dict(seed=2026101804,groups=groups,note='Development set. Close-pair acceptance is ambiguity, not source separation.')

def evaluate(lib,x,kind,flags,c1=True,carrier=55,rate=7,depth=.7,seconds=3.4):
    r=P.render(lib,x,3,c1,tonal=True,stage_flags=flags)
    mask=(r['stages'][:,0]>=3750)&(r['stages'][:,0]<9000)
    stats=dict(detail_applied_core_fraction=float(r['stages'][mask,INDEX['detail_applied']].mean()),
               stem_rms_dbfs=float(T.db(np.sqrt(np.mean(r['stem']**2)))),peak_dbfs=T.true_peak_db(r['output']),
               gain_mean=float(r['stages'][mask,INDEX['applied_gain']].mean()),
               callback_ms_p95=float(np.percentile(r['cost_ms'],95)),latency=r['latency'])
    assert stats['peak_dbfs']<-1 and np.isfinite(r['output']).all()
    if kind=='am':
        stats['metrics']=Q.am_harmonics(r['stem'],48000,carrier,rate,depth,algorithm=4,latency=r['latency']/48000,temporal=True)
        stats['quality']=Q.aggregate_am(stats['metrics'])
    elif kind=='fm':
        stats['metrics']=Q.fm_harmonics(r['stem'],48000,carrier,rate,depth,algorithm=4,latency=r['latency']/48000,temporal=True)
        stats['quality']=Q.aggregate_am(stats['metrics'])
    elif kind=='off':
        stats['tail_peak']=float(np.max(abs(r['stem'][int(2.8*48000):])))
        assert stats['tail_peak']<1e-7
    else:stats['quality']='not_evaluated'
    return stats

def run(args):
    lib=P.api(args.lib);fit=fit_controls(lib);fs=48000;t=np.arange(int(3.4*fs))/fs;cases={}
    signals={}
    for f in (40,55,80,120):
        for rate in (2,7,15,20):
            signals[f'am_f{f}_r{rate}']=(.15*(1+.7*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*f*t),'am',f,rate,.7)
    signals['fm55_7_35']=(Q.fm_tone(fs,len(t),55,7,35),'fm',55,7,35)
    signals['close_pair']=(.10*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6),'ambiguous',55,7,.7)
    signals['off']=(.15*np.cos(2*np.pi*55*t)*(t<1.7),'off',55,7,.7)
    for name,(x,kind,f,rate,d) in signals.items():
        modes={}
        for flags in ((0,2,16,18) if name in ('am_f55_r7','fm55_7_35') else (0,18)):
            modes[str(flags)]=evaluate(lib,x,kind,flags,carrier=f,rate=rate,depth=d)
            print(name,flags,modes[str(flags)].get('quality'),modes[str(flags)]['detail_applied_core_fraction'],flush=True)
        cases[name]=modes
    result=dict(schema='pvb.phase2.detail.v1',fit=fit,cases=cases,
                candidates={'0':'C1+P1-AS','2':'G2 fixed gain ablation','16':'D2 short detail','18':'D2+G2 fixed gain'},
                data_split='development; not sealed evaluation',device='not_evaluated',listening='not_evaluated',
                settings=dict(sample_rate=fs,algorithm=4,layer_db=6,output_db=-18,tonal_only=True,mode=3,c1=True),
                library_sha256=hashlib.sha256(Path(args.lib).read_bytes()).hexdigest())
    Path(args.report).write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lib',default=str(HERE/'build/libpvbcapi.so'));p.add_argument('--report',default='detail-research.json');run(p.parse_args())
