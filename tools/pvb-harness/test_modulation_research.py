#!/usr/bin/env python3
"""P1 numerical/streaming research. Quality targets are reported, not waived gates.

Frozen config: 128ms/3kHz/degree4/4 iterations/residual-20dB; first held-out
seed 20261021. Tuning exploration used seed20261020. No source/audio adoption.
"""
import argparse, ctypes as C, hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
import test_engine as T
import test_harmonic_continuity as H
sys.path.insert(0,str(Path(__file__).resolve().parent/'vb_quality'))
import modulated as M
from vb_quality import measurement as Q
import test_native_renderer as NR
import test_native_stream as NS
HERE=Path(__file__).resolve().parent
DP=C.POINTER(C.c_double)

def api(path):
    lib=H.api(path)
    lib.pvb_modulation_fit.argtypes=[DP,C.c_double,DP,C.c_int,DP]
    lib.pvb_set_modulation_research.argtypes=[C.c_void_p,C.c_int,C.c_int]
    lib.pvb_copy_diagnostic.argtypes=[C.c_void_p,T.FP,T.FP,C.c_int,T.FP,C.c_int]
    return lib

def native_fit(lib,x,seed,neighbors=()):
    x=np.ascontiguousarray(x,np.float64);nb=np.ascontiguousarray(neighbors,np.float64);out=np.zeros(20)
    start=time.perf_counter()
    ok=lib.pvb_modulation_fit(x.ctypes.data_as(DP),seed,nb.ctypes.data_as(DP),len(nb),out.ctypes.data_as(DP))
    elapsed=(time.perf_counter()-start)*1000
    m=dict(accepted=bool(ok),amplitude=out[0],frequency_hz=out[1],phase_rad=out[2],amplitude_slope=out[3],frequency_slope=out[4],
        carrier_hz=out[5],carrier_slope=out[6],residual_db=out[7],qr_diagonal_ratio=out[8],coefficients=out[10::2]+1j*out[11::2],elapsed_ms=elapsed)
    assert np.isfinite(out).all()
    return m

def render(lib,x,mode=0,c1=False,fs=48000,algo=4,block=4096,tonal=False,level=6,stage_flags=None,stage_capacity=None):
    x=np.asarray(x,np.float32);x=T.stereo(x) if x.ndim==1 else x
    e=T.Engine(lib,fs,vb_on=1,vb_algo=algo,vb_level_db=level,out_db=-18,ramp_ms=0)
    lib.pvb_set_modulation_research(e.h,mode,int(tonal))
    if c1:lib.pvb_set_continuity_research(e.h,1,2,6,6)
    lib.pvb_set_diagnostic_capture(e.h,1)
    capture=None
    if stage_flags is not None:
        from vb_quality.stage_capture import StageCapture
        capture=StageCapture(lib,e.h,stage_flags,stage_capacity or int(len(x)/fs*3000)+8)
    y=x.copy();stem=np.zeros_like(y);full=np.empty_like(y)
    buf=np.empty(H.ROWS*H.FIELDS,np.float32);tr=np.empty(32+lib.pvb_param_count(),np.float32);rows=[];cost=[]
    for off in range(0,len(x),block):
        b=y[off:off+block];s=stem[off:off+block];f=full[off:off+block]
        start=time.perf_counter();lib.pvb_process(e.h,b.ctypes.data_as(T.FP),len(b));cost.append((time.perf_counter()-start)*1000)
        assert lib.pvb_copy_diagnostic(e.h,s.ctypes.data_as(T.FP),f.ctypes.data_as(T.FP),b.size,tr.ctypes.data_as(T.FP),len(tr))==1
        n=lib.pvb_copy_harmonic(e.h,buf.ctypes.data_as(T.FP),len(buf));assert n>=0
        if n:
            r=buf[:n*H.FIELDS].reshape(n,H.FIELDS).copy();r[:,0]+=off;rows.append(r)
    latency=e.latency();meters=e.meters()
    try:stages=capture.copy() if capture else None
    finally:
        if capture:capture.close()
        e.close()
    rows=np.vstack(rows) if rows else np.empty((0,H.FIELDS),np.float32)
    assert np.isfinite(y).all() and np.isfinite(stem).all() and np.isfinite(rows).all()
    assert not len(rows) or ((rows[:,27].astype(int)&31)==mode+16*int(tonal)).all()
    return dict(output=y,stem=stem,rows=rows,stages=stages,latency=latency,meters=meters,cost_ms=cost)

def direct(lib):
    rng=np.random.default_rng(20261021);groups={};max_agree=0.;timings=[]
    probe=NR.Probe(lib)
    for kind in ('steady','am','vibrato','chirp','decay','neighbor','close_pair','noise','silence'):
        errors=[];accepted=0;falseaccepted=0;local_errors=[];stationary_errors=[];linear_errors=[];res=[];ratios=[];svd=[]
        for case in range(48):
            f=rng.uniform(40,120);p=rng.uniform(-np.pi,np.pi);a=rng.uniform(.05,.25);t=M.T
            neighbors=();phase=2*np.pi*f*t+p;amplitude=np.full_like(t,a);instant=f
            if kind=='am':
                rate=rng.uniform(2,9);d=rng.uniform(.2,.8);mp=rng.uniform(-np.pi,np.pi)
                amplitude=a*(1+d*np.sin(2*np.pi*rate*t+mp))
            if kind=='vibrato':
                rate=rng.uniform(3,6);d=rng.uniform(.1,.7);mp=rng.uniform(-np.pi,np.pi)
                phase+=d*np.sin(2*np.pi*rate*t+mp);instant=f+d*rate*np.cos(mp)
            if kind=='chirp':
                slope=rng.uniform(-70,70);phase+=np.pi*slope*t*t
            if kind=='decay':amplitude=a*np.exp(-rng.uniform(1,5)*t)
            x=amplitude*np.cos(phase)
            if kind=='neighbor':neighbors=(f+40,);x+=.06*np.cos(2*np.pi*(f+40)*t+.3)
            if kind=='close_pair':x+=.7*a*np.cos(2*np.pi*(f+3)*t+.6)
            if kind=='noise':x=rng.normal(0,a,size=M.N)
            if kind=='silence':x=np.zeros(M.N)
            seed=(f+.4 if kind=='neighbor' else M.seed_frequency(x)) if kind!='silence' else 55.
            n=native_fit(lib,x,seed,neighbors);py=M.fit(x,seed,neighbors);timings.append(n['elapsed_ms'])
            accepted+=n['accepted'];falseaccepted+=int(n['accepted'] and kind in ('close_pair','noise','silence'))
            if 'frequency_hz' in py:
                delta=np.max(np.abs(np.array([n['amplitude']-py['amplitude'],n['frequency_hz']-py['frequency_hz'],n['amplitude_slope']-py['amplitude_slope'],n['frequency_slope']-py['frequency_slope']])))
                max_agree=max(max_agree,float(delta));assert delta<1e-5,(kind,delta)
                assert np.max(np.abs(n['coefficients']-py['coefficients']))<1e-6
                res.append(n['residual_db']);ratios.append(n['qr_diagonal_ratio']);svd.append(py['condition'])
            if n['accepted'] and kind not in ('close_pair','noise','silence'):
                errors.append(abs(1200*np.log2(n['frequency_hz']/instant)))
                # Ground truth comes from the declared source formula. Actual
                # samples come from production renderTrack52, not M.evaluate.
                sl=slice(176,208);lt=t[sl];weights,gain,offsets=Q.table_at(n['frequency_hz'])
                def mix(amp,ph):
                    return sum(amp*gain*w*np.cos(k*ph+offsets[k-2]) for k,w in enumerate(weights,2) if w>1e-4)
                reference=mix(amplitude[sl],phase[sl])
                fitted=probe.grain(NR.encode(n))
                stationary=mix(n['amplitude'],n['phase_rad']+2*np.pi*n['frequency_hz']*lt)
                linear=mix(n['amplitude']+n['amplitude_slope']*lt,n['phase_rad']+2*np.pi*n['frequency_hz']*lt+np.pi*n['frequency_slope']*lt*lt)
                energy=np.mean(reference**2)
                for target,v in ((local_errors,fitted),(stationary_errors,stationary),(linear_errors,linear)):
                    target.append(float(10*np.log10(max(np.mean((v-reference)**2)/energy,1e-30))))
        groups[kind]=dict(cases=48,accepted=accepted,numerically_accepted_ambiguous_or_negative=falseaccepted,
            pitch_cents_median=float(np.median(errors)) if errors else None,pitch_cents_p95=float(np.percentile(errors,95)) if errors else None,
            native_grain_nmse_db_median=float(np.median(local_errors)) if local_errors else None,
            stationary_grain_nmse_db_median=float(np.median(stationary_errors)) if stationary_errors else None,
            derivative_grain_nmse_db_median=float(np.median(linear_errors)) if linear_errors else None,
            residual_db_median=float(np.median(res)) if res else None,qr_diagonal_ratio_max=max(ratios) if ratios else None,
            python_svd_condition_max=max(svd) if svd else None)
    # Silence/nonfinite must not become valid oscillators; zero residual is undefined
    # for an early rejected fit and must never be presented as an exact fit.
    assert groups['silence']['accepted']==0 and groups['noise']['accepted']==0
    for kind in ('steady','am','vibrato','chirp','decay','neighbor'):
        assert groups[kind]['pitch_cents_p95']<=10
    for v in (np.nan,np.inf):
        x=np.zeros(M.N);x[10]=v;assert not native_fit(lib,x,55)['accepted']
        assert not native_fit(lib,np.zeros(M.N),v)['accepted']
    probe.close()
    return dict(seed=20261021,groups=groups,max_python_cpp_parameter_absolute_difference=max_agree,
        native_frame_fit_ms=dict(p50=float(np.median(timings)),p95=float(np.percentile(timings,95)),max=max(timings)),
        note='Native raw aggregate grain; table weights held at estimated center frequency for all comparisons. No OLA/filter/listening oracle. Nearby tones can be indistinguishable from AM.')

def stream(lib,baseline=None):
    fs=48000;t=np.arange(int(fs*3.4))/fs
    signals=dict(steady=.15*np.cos(2*np.pi*55*t),am=.15*(1+.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*55*t),
        vibrato=.15*np.cos(2*np.pi*55*t+.5*np.sin(2*np.pi*5*t)),glide=.15*np.cos(2*np.pi*(45*t+5*t*t)),
        close_pair=.10*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6),note_off=.15*np.cos(2*np.pi*55*t)*(t<1.7),
        noise=np.random.default_rng(20261022).normal(0,.08,len(t)))
    signals['vibrato_35cents']=Q.fm_tone(fs,len(t),55,7,35)
    signals['note_change_55_65']=.15*np.cos(2*np.pi*(55*np.minimum(t,1.7)+65*np.maximum(t-1.7,0)))
    signals['am_triplet']=.15*np.cos(2*np.pi*55*t)+.0525*np.cos(2*np.pi*48*t+np.pi/2)+.0525*np.cos(2*np.pi*62*t-np.pi/2)
    assert np.max(abs(signals['am']-signals['am_triplet']))<1e-12
    result={}
    for name,x in signals.items():
        modes={}
        for mode,c1,label in ((0,False,'B0'),(1,False,'P1-S'),(2,False,'P1-A'),(3,False,'P1-AS'),(3,True,'C1+P1-AS')):
            r=render(lib,x,mode,c1,tonal=True)
            assert r['latency']==7140 and T.true_peak_db(r['output'])<-1
            if name=='note_off':assert np.max(np.abs(r['stem'][int(2.8*fs):]))<1e-7
            stats=H.summarize(r['rows']);tt=H.tracks(r['rows']);steady=r['rows'][:,0]>fs
            obs=(tt[:,:,1]==2)&steady[:,None];fit=(tt[:,:,6]<=-20)&obs
            stats.update(residual_under_minus20_observed_hops=int(fit.sum()),observed_after_1s=int(obs.sum()),
                modulation_reestimated_hops=int((r['rows'][:,27]>=32).sum()),
                stem_rms_dbfs=float(T.db(np.sqrt(np.mean(r['stem']**2)))),full_true_peak_dbfs=T.true_peak_db(r['output']),
                host_audio_seconds_per_wall_second=float(len(x)/fs/(sum(r['cost_ms'])/1000)),
                host_callback_ms_p95=float(np.percentile(r['cost_ms'],95)))
            if name=='vibrato_35cents':
                stats['fm_harmonics']=Q.fm_harmonics(r['stem'],fs,55,7,35,latency=r['latency']/fs,temporal=True)
                stats['fm_quality_status']=Q.aggregate_am(stats['fm_harmonics'])
            if name=='am':
                stats['am_harmonics']=Q.am_harmonics(r['stem'],fs,55,7,.7,latency=r['latency']/fs,temporal=True)
                stats['am_quality_status']=Q.aggregate_am(stats['am_harmonics'])
                # Track parameters are measured separately from the emitted layer.
                select=(tt[:,:,1]>0)&(abs(tt[:,:,2]-55)<4)
                dominant=np.where(select,tt[:,:,4],-1).argmax(axis=1)
                aa=tt[np.arange(len(tt)),dominant,4];valid=select[np.arange(len(tt)),dominant]
                seconds=(H.core_indices(r['rows'])-382)/3000
                valid &= (seconds>=1.25)&(seconds<3)
                design=np.column_stack((np.ones(len(seconds)),np.cos(2*np.pi*7*seconds),np.sin(2*np.pi*7*seconds)))
                coef=np.linalg.lstsq(design[valid],aa[valid],rcond=None)[0]
                stats['tracked_carrier_amplitude_depth']=float(np.hypot(coef[1],coef[2])/coef[0]) if coef[0]>1e-10 else None
            modes[label]=stats
        result[name]=modes
    invariants=[]
    for fs in (44100,48000):
        t=np.arange(fs)/fs;x=.12*np.cos(2*np.pi*55*t)+.04*np.cos(2*np.pi*110*t+.3)
        for alg in range(6):
            current=render(lib,x,fs=fs,algo=alg)
            if baseline:
                y,_,lat=H.render(baseline,x,fs=fs,algo=alg)
                assert np.array_equal(current['output'],y) and current['latency']==lat,(fs,alg)
            invariants.append(dict(sample_rate=fs,algorithm=alg,baseline_bit_exact=bool(baseline)))
        a=render(lib,x,3,True,fs=fs,block=4096)
        b=render(lib,x,3,True,fs=fs,block=1379)
        assert np.array_equal(a['output'],b['output']) and np.array_equal(a['stem'],b['stem'])
        # Trace callback offsets differ; core-domain metadata must not.
        assert np.array_equal(a['rows'][:,1:],b['rows'][:,1:])
        prefix=x.copy();prefix[int(.65*fs):]*=-1
        c=render(lib,prefix,3,True,fs=fs)
        assert np.array_equal(a['output'][:int(.65*fs)],c['output'][:int(.65*fs)])
    return dict(cases=result,invariance=invariants,chunk_and_prefix_causality='passed at44.1/48kHz',
        note='Tonal path only: percussion suppressed by explicit host-only control. Fullmix is not shipped behavior. HPSS, gates, EQ, envelope, filters remain active.')

def audio(lib,path):
    import soundfile as sf
    x,fs=sf.read(path,dtype='float32',always_2d=True);source_fs=fs
    if fs!=48000:x=resample_poly(x,48000//np.gcd(fs,48000),fs//np.gcd(fs,48000),axis=0).astype(np.float32);fs=48000
    result=[]
    # Fixed regions selected BEFORE P1 renders, with4s causal preroll. These are
    # coverage probes of the available song, not held-out listening/buzz labels.
    for start in (0,40,90,150):
        lo=max(0,start-4);segment=x[int(lo*fs):int((start+8)*fs)]
        modes={}
        for mode,c1,label in ((0,False,'B0'),(1,False,'P1-S'),(2,False,'P1-A'),(3,False,'P1-AS'),(3,True,'C1+P1-AS')):
            r=render(lib,segment,mode,c1,level=9);rows=r['rows'];keep=rows[:,0]>=(start-lo)*fs;rows=rows[keep]
            stats=H.summarize(rows);stats['modulation_reestimated_hops']=int((rows[:,27]>=32).sum());s=int((start-lo)*fs)
            stats.update(stem_rms_dbfs=float(T.db(np.sqrt(np.mean(r['stem'][s:]**2)))),full_true_peak_dbfs=T.true_peak_db(r['output'][s:]),
                host_audio_seconds_per_wall_second=float(len(segment)/fs/(sum(r['cost_ms'])/1000)))
            modes[label]=stats
        result.append(dict(start_seconds=start,evaluation_seconds=8,preroll_seconds=start-lo,modes=modes))
    return dict(sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),source_rate=source_fs,processing_rate=fs,
        regions=result,note='Fixed algo4/+9/out-18,default EQ,dyn off; not phone ZIP replay. Available song only, no labeled buzz/quality conclusions.')

def run(args):
    lib=api(args.lib);native=NR.renderer_correctness(lib);native_stream=NS.stream_correctness(lib)
    result=dict(schema='pvb.modulation_research.v2',measurement_version=Q.VERSION,
        evaluation_mode='promotion_gate' if args.require_quality else 'engineering_and_measurement',
        listening_validated=False,adopted_in_app=False,native_renderer=native,native_stream=native_stream,
        config=dict(frame_samples=384,core_rate=3000,hop_samples=16,degree=4,reassignment_iterations=4,residual_threshold_db=-20,qr_diagonal_guard=1e4,max_neighbor_columns=3),
        host=dict(platform=platform.platform(),python=platform.python_version(),numpy=np.__version__),direct=direct(lib))
    if not args.direct_only:result['stream']=stream(lib,H.api(args.baseline) if args.baseline else None)
    if args.audio:result['audio']=audio(lib,args.audio)
    if 'stream' in result:
        cases=result['stream']['cases'];am=cases['am'][args.candidate]['am_harmonics'];fm=cases['vibrato_35cents'][args.candidate]['fm_harmonics']
        quality=Q.aggregate_am(am+fm)
    else:quality='not_evaluated'
    result['checks']=dict(correctness='pass',quality=quality,device='not_evaluated',listening='not_evaluated')
    result['quality_scope']='55Hz AM7Hz depth.7 and FM7Hz35cents: depth, independently estimated rate and fixed-clock phase; not complete phase2 adoption suite'
    blocked=[k+':'+v for k,v in result['checks'].items() if v!='pass']
    result['promotion']=dict(candidate=args.candidate,status='blocked' if blocked else 'eligible',reasons=blocked)
    result['library_sha256']=hashlib.sha256(Path(args.lib).read_bytes()).hexdigest()
    result['source_sha256']={p:hashlib.sha256((HERE/('../../app/src/main/cpp/libpvb/'+p)).read_bytes()).hexdigest() for p in ('pvb_vb52.cpp','pvb_vb_modulation.h','pvb_vb.h')}
    result['source_sha256']['modulated.py']=hashlib.sha256((HERE/'vb_quality/modulated.py').read_bytes()).hexdigest()
    result['harness_sha256']={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ('pvb_capi.cpp','test_native_renderer.py','test_native_stream.py','vb_quality/measurement.py',Path(__file__).name)}
    Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Saved',args.report,flush=True)
    print(json.dumps(result['direct'],indent=2),flush=True)
    print(json.dumps(dict(checks=result['checks'],promotion=result['promotion'])),flush=True)
    if args.require_quality and blocked:raise SystemExit(2)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lib',default=str(HERE/'build/libpvbcapi.so'));p.add_argument('--baseline');p.add_argument('--direct-only',action='store_true');p.add_argument('--audio')
    p.add_argument('--candidate',choices=['P1-AS','C1+P1-AS'],default='C1+P1-AS')
    p.add_argument('--require-quality',action='store_true',help='exit2 unless correctness,quality,device,listening all pass')
    p.add_argument('--report',default=str(HERE/'vb_quality/results/modulation-p1-host-v2.json'));run(p.parse_args())
