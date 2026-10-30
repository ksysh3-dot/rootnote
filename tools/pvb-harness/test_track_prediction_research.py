#!/usr/bin/env python3
"""C2 predictors: oracle observations, then real native analyzer coverage.

Prediction error, tracking registration and source observability are separate.
No phone/listening verdict, and no musical ID target at unresolved crossings.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
import test_modulation_research as P
import test_track_assignment_research as A
import test_harmonic_continuity as H
import test_engine as T
from vb_quality import measurement as Q

DP=C.POINTER(C.c_double)
IP=C.POINTER(C.c_int)
HERE=Path(__file__).resolve().parent
FLAGS={'constant':256,'linear':768,'burg2':1280}


def api(path):
    lib=P.api(path)
    lib.pvb_track_prediction.argtypes=[DP,C.c_int,C.c_int,C.c_int,DP]
    lib.pvb_track_assignment_predicted.argtypes=[DP,C.c_int,DP,C.c_int,DP,IP]
    return lib


def predict(lib,history,horizon,mode):
    h=np.ascontiguousarray(history,np.float64);out=np.empty(4,np.float64)
    assert lib.pvb_track_prediction(h.ctypes.data_as(DP),len(h),horizon,mode,out.ctypes.data_as(DP))==0
    assert np.isfinite(out).all()
    assert 20<=out[0]<=200
    assert abs(out[0]-h[-1])<=400*16/3000*horizon+1e-10
    return out


def assign(lib,obs,old,forecasts):
    obs=np.ascontiguousarray(obs,np.float64).reshape(-1,5)
    old=np.ascontiguousarray(old,np.float64).reshape(-1,5)
    forecasts=np.ascontiguousarray(forecasts,np.float64);out=np.empty(len(obs),np.int32)
    assert lib.pvb_track_assignment_predicted(obs.ctypes.data_as(DP),len(obs),old.ctypes.data_as(DP),len(old),forecasts.ctypes.data_as(DP),out.ctypes.data_as(IP))==0
    assert len(set(out[out>=0]))==sum(out>=0)
    return out


def direct(lib):
    groups={};limited={};used={};constant=0;linear=0
    for seed in (2026101809,2026101810):
        rng=np.random.default_rng(seed)
        for kind in ('steady','glide','vibrato','noisy_steady','noisy_vibrato'):
            key=f'{seed}:{kind}';errors=[[],[],[]];limited[key]=[0,0,0];used[key]=[[],[],[]]
            for case in range(48):
                f=rng.uniform(55,100);rate=rng.uniform(3,7);amp=rng.uniform(1,6);phase=rng.uniform(-np.pi,np.pi)
                t=np.arange(-31,7)*16/3000
                truth=np.full_like(t,f)
                if kind=='glide':truth=f+rng.uniform(-90,90)*t
                if 'vibrato' in kind:truth=f+amp*np.sin(2*np.pi*rate*t+phase)
                history=truth[:32].copy()
                if kind.startswith('noisy'):history+=rng.normal(0,.25,len(history))
                for horizon in (1,3,6):
                    for mode in range(3):
                        p=predict(lib,history,horizon,mode)
                        errors[mode].append(abs(p[0]-truth[31+horizon]));limited[key][mode]+=int(p[3]);used[key][mode].append(int(p[2]))
                    assert predict(lib,history,horizon,0)[0]==history[-1];constant+=1
                    if kind=='glide':
                        assert abs(predict(lib,history,horizon,1)[0]-truth[31+horizon])<1e-10;linear+=1
            groups[key]={name:dict(cases=len(errors[m]),mae_hz=float(np.mean(errors[m])),p95_hz=float(np.percentile(errors[m],95)),max_hz=float(max(errors[m])),limited=limited[key][m],used_modes={str(v):used[key][m].count(v) for v in set(used[key][m])}) for m,name in enumerate(FLAGS)}
    # A separate global optimizer validates the objective with forecast anchors.
    rng=np.random.default_rng(2026101811);maxdiff=0
    for case in range(120):
        n=int(rng.integers(1,7));m=int(rng.integers(1,13))
        old=np.column_stack((rng.uniform(55,80,m),rng.uniform(-np.pi,np.pi,m),rng.uniform(.02,.2,m),np.ones(m),rng.integers(0,7,m)))
        obs=np.column_stack((rng.uniform(55,80,n),rng.uniform(-np.pi,np.pi,n),rng.uniform(.02,.2,n),np.ones(n),np.zeros(n)))
        forecasts=old[:,0]+rng.uniform(-3,3,m)
        matrix=np.full((n,m+n),1e6)
        for i,(f,phase,a,_,_) in enumerate(obs):
            for j,(of,op,oa,life,missing) in enumerate(old):
                if abs(f-forecasts[j])>=.1*f:continue
                ph=np.angle(np.exp(1j*(phase-op-np.pi*(f+of)*16/3000)))/np.pi
                matrix[i,j]=((f-forecasts[j])/(.1*f))**2+.08*ph*ph+.04*min(3,abs(np.log((a+1e-9)/(oa+1e-9))))**2+.01*missing
            matrix[i,m+i]=1.5
        actual=assign(lib,obs,old,forecasts);cols=np.where(actual>=0,actual,m+np.arange(n));rr,cc=linear_sum_assignment(matrix)
        error=abs(matrix[np.arange(n),cols].sum()-matrix[rr,cc].sum());maxdiff=max(maxdiff,float(error));assert error<1e-10
    # Keep the physical phase clock counterexamples with explicit forecasts.
    phase_cases=0
    for f in (55.,68.3,110.):
        omega=2*np.pi*f*16/3000
        for missing in range(1,7):
            old=[[f,missing*omega,.1,1,missing],[f,0,.1,1,missing]]
            assert np.array_equal(assign(lib,[[f,(missing+1)*omega,.1,1,0]],old,[f,f]),[0]);phase_cases+=1
    out=np.zeros(4);valid=np.full(32,55.)
    for bad in (np.nan,np.inf,-1.,201.):
        x=valid.copy();x[-1]=bad
        assert lib.pvb_track_prediction(x.ctypes.data_as(DP),32,1,2,out.ctypes.data_as(DP))==-2
    return dict(seeds=[2026101809,2026101810],cases=groups,constant_identity_cases=constant,linear_exact_glide_cases=linear,forecast_assignment_oracle_cases=120,max_objective_difference=maxdiff,held_phase_clock_cases=phase_cases)


def observation_rows(r):
    ts=H.tracks(r['rows'])
    return [q[(q[:,1]==1)|(q[:,1]==2)] for q in ts]


def observability(r,truth,fs,seconds):
    times=(r['rows'][:,0].astype(float)+r['rows'][:,9])/fs
    observed=observation_rows(r);last_ids={};last_hop={}
    counts=dict(evaluated_hops=0,eligible_component_hops=0,covered_component_hops=0,
        missing_component_hops=0,unmatched_observations=0,unresolved_hops=0,
        no_observation_component_hops=0,out_of_tolerance_component_hops=0,
        peak_count_deficit_component_hops=0,
        adjacent_id_switches=0,reacquisition_id_changes=0,adjacent_links=0)
    frequency_errors=[];unresolved_counts={};eligible_counts={}
    for hop,(time,obs) in enumerate(zip(times,observed)):
        if time<.65 or time>seconds-.4:continue
        frequencies,active=truth(time);frequencies=np.array(frequencies)[np.array(active,bool)]
        counts['evaluated_hops']+=1
        if len(frequencies)>1 and min(abs(a-b) for i,a in enumerate(frequencies) for b in frequencies[i+1:])<12:
            counts['unresolved_hops']+=1
            key=str(len(obs));unresolved_counts[key]=unresolved_counts.get(key,0)+1
            last_ids.clear();last_hop.clear();continue
        counts['eligible_component_hops']+=len(frequencies)
        key=f'{len(frequencies)}:{len(obs)}';eligible_counts[key]=eligible_counts.get(key,0)+1
        counts['peak_count_deficit_component_hops']+=max(0,len(frequencies)-len(obs))
        if len(frequencies) and len(obs):
            distance=np.abs(frequencies[:,None]-obs[None,:,2]);rr,cc=linear_sum_assignment(distance)
            pairs=[(i,j) for i,j in zip(rr,cc) if distance[i,j]<=2.]
        else:pairs=[]
        counts['covered_component_hops']+=len(pairs);counts['missing_component_hops']+=len(frequencies)-len(pairs)
        if len(obs)==0:counts['no_observation_component_hops']+=len(frequencies)
        else:counts['out_of_tolerance_component_hops']+=len(frequencies)-len(pairs)
        counts['unmatched_observations']+=len(obs)-len(pairs)
        for source,index in pairs:
            identity=int(obs[index,0])+65536*int(obs[index,13]);frequency_errors.append(abs(float(obs[index,2])-frequencies[source]))
            if source in last_ids:
                gap=hop-last_hop[source]
                if gap==1:
                    counts['adjacent_links']+=1;counts['adjacent_id_switches']+=identity!=last_ids[source]
                elif gap<=6:counts['reacquisition_id_changes']+=identity!=last_ids[source]
            last_ids[source]=identity;last_hop[source]=hop
    counts['coverage']=counts['covered_component_hops']/counts['eligible_component_hops'] if counts['eligible_component_hops'] else None
    counts['frequency_mae_hz']=float(np.mean(frequency_errors)) if frequency_errors else None
    assert counts['missing_component_hops']==counts['no_observation_component_hops']+counts['out_of_tolerance_component_hops']
    counts['eligible_truth_count_observation_count_histogram']=eligible_counts
    counts['unresolved_observation_count_histogram']=unresolved_counts
    counts['contract']='source clock=host event+header9; warmup.65s/end.4s; eligible separation>=12Hz; coverage tolerance2Hz. These are diagnostic thresholds, not a resolution theorem.'
    return counts


def native_cases(lib,baseline=None):
    fs=48000;seconds=3.4;t=np.arange(int(seconds*fs))/fs
    cases={
      'steady':(.15*np.cos(2*np.pi*55*t),lambda s:([55],[True])),
      'glide':(.15*np.cos(2*np.pi*(45*t+10*t*t)),lambda s:([45+20*s],[True])),
      'vibrato':(.15*np.cos(2*np.pi*70*t+1.5*np.sin(2*np.pi*4*t)),lambda s:([70+6*np.cos(2*np.pi*4*s)],[True])),
      'crossing':(.10*np.cos(2*np.pi*(48*t+5*t*t))+.07*np.cos(2*np.pi*(96*t-5*t*t)+.8),lambda s:([48+10*s,96-10*s],[True,True])),
      'near_pair':(.10*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6),lambda s:([55,58],[True,True])),
      'am7':(.15*(1+.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*55*t),lambda s:([55],[True])),
      'off':(.15*np.cos(2*np.pi*70*t)*(t<1.7),lambda s:([70],[s<1.7])),
    }
    results={};dispatch={name:0 for name in ('linear','burg2')};old_invariance=[]
    for name,(x,truth) in cases.items():
        modes={};ref=None;ref_obs=None
        for mode,flags in FLAGS.items():
            r=A.measure(lib,x,flags,fs)[0]
            obs=observation_rows(r)
            if ref is None:ref=r;ref_obs=obs
            else:
                assert np.array_equal(H.core_indices(ref['rows']),H.core_indices(r['rows']))
                assert all(np.array_equal(a[:,[2,4,6]],b[:,[2,4,6]]) for a,b in zip(ref_obs,obs)),'observations changed across predictors'
                count=int((H.tracks(ref['rows'])[:,:,[0,13]]!=H.tracks(r['rows'])[:,:,[0,13]]).sum());dispatch[mode]+=count
            if name=='off':assert np.max(abs(r['stem'][int(2.8*fs):]))<1e-7
            modes[mode]=dict(tracking=H.summarize(r['rows']),observability=observability(r,truth,fs,seconds),
                stem_rms_dbfs=float(T.db(np.sqrt(np.mean(r['stem']**2)))),peak_dbfs=T.true_peak_db(r['output']),
                callback_p95_ms=float(np.percentile(r['cost_ms'],95)),latency_frames=r['latency'])
        if baseline is not None and name in ('steady','crossing','am7'):
            old=P.render(baseline,x,3,True,fs=fs,stage_flags=256)
            assert np.array_equal(old['output'],ref['output']) and np.array_equal(old['stem'],ref['stem']) and np.array_equal(old['rows'],ref['rows'])
            old_invariance.append(name)
        results[name]=modes
        print(name,{k:(v['observability']['coverage'],v['observability']['adjacent_id_switches']) for k,v in modes.items()},flush=True)
    assert all(v>0 for v in dispatch.values()),('native predictor dispatch not reached',dispatch)
    return dict(cases=results,changed_native_id_slots=dispatch,constant_c2_bit_exact_with_previous=old_invariance)


def stream(lib):
    checks=[]
    for fs in (44100,48000):
        t=np.arange(fs*2)/fs;x=.15*np.cos(2*np.pi*(55*t+12*t*t))
        for name,flags in FLAGS.items():
            a=P.render(lib,x,3,True,fs=fs,stage_flags=flags)
            b=P.render(lib,x,3,True,fs=fs,stage_flags=flags,block=1379)
            assert np.array_equal(a['output'],b['output']) and np.array_equal(a['stages'],b['stages']) and np.array_equal(a['rows'],b['rows'])
            changed=x.copy();changed[int(.8*fs):]*=-1;c=P.render(lib,changed,3,True,fs=fs,stage_flags=flags)
            assert np.array_equal(a['output'][:int(.8*fs)],c['output'][:int(.8*fs)])
            checks.append(dict(fs=fs,mode=name,chunk_prefix='pass'))
        # Exercise both new predictors with the previously validated AM-family
        # path, not just the simpler P1 path. These are actual native stems.
        t=np.arange(int(3.4*fs))/fs
        am=.15*(1+.7*np.sin(2*np.pi*20*t))*np.cos(2*np.pi*80*t)
        for name in ('linear','burg2'):
            flags=FLAGS[name]+240
            r=P.render(lib,am,3,True,fs=fs,stage_flags=flags)
            metrics=Q.am_harmonics(r['stem'],fs,80,20,.7,algorithm=4,latency=r['latency']/fs,temporal=True)
            assert Q.aggregate_am(metrics)=='pass',('AM family regression',fs,name)
            checks.append(dict(fs=fs,mode=name,am_family_depth_rate_phase='pass'))
    e=T.Engine(lib,48000)
    #2048 is now the valid P2-O flag, 8192 the study 2 (#4) C1 flag, 16384..524288 the study 3 flags, 1048576
    # Resultant R1, 2097152 / 4194304 Resultant R3, 8388608 R3-a and 16777216 / 33554432 Resultant R4; retain invalid
    # combinations and test the new upper boundary (67108864) plus correction-without-oscillator rejection.
    for flags in (512,1024,1792,4096,8192|4096,67108864):assert not lib.pvb_stage_attach(e.h,flags,100)
    lib.pvb_stage_attach.argtypes=[C.c_void_p,C.c_uint,C.c_int];lib.pvb_stage_attach.restype=C.c_void_p
    lib.pvb_stage_detach.argtypes=[C.c_void_p]
    for flags in (8192,16384,32768,65536,131072,262144,524288,1048576,2097152,4194304,8388608,16777216,16777216|33554432):
        handle=lib.pvb_stage_attach(e.h,flags,100);assert handle;lib.pvb_stage_detach(handle)
    e.close()
    # Reset the actual engine after predictor history is populated. The output
    # must equal a clean run; this is independent of diagnostic track ID epochs.
    for name in ('linear','burg2'):
        e=T.Engine(lib,48000,vb_on=1,vb_algo=4,vb_level_db=6,out_db=-18,ramp_ms=0)
        lib.pvb_set_modulation_research(e.h,3,0);lib.pvb_set_continuity_research(e.h,1,2,6,6)
        handle=lib.pvb_stage_attach(e.h,FLAGS[name],20000);assert handle
        t=np.arange(48000*2)/48000;x=T.stereo(.15*np.cos(2*np.pi*(55*t+12*t*t)))
        lib.pvb_reset(e.h);first=e.process(x);lib.pvb_reset(e.h);second=e.process(x)
        assert np.array_equal(first,second),('predictor engine reset',name)
        lib.pvb_stage_detach(handle);e.close()
        checks.append(dict(mode=name,engine_reset='bit_exact'))
    return checks


def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',required=True);p.add_argument('--baseline');p.add_argument('--report',required=True);a=p.parse_args()
    lib=api(a.lib);baseline=P.api(a.baseline) if a.baseline else None
    result=dict(schema='pvb.phase2.track_prediction.v1',config=dict(history=32,order=2,minimum_history=8,reflection_limit=.999,slope_limit_hz_s=400,frequency_only=True,hold_release_unchanged=True,flags=FLAGS),direct=direct(lib))
    result['native']=native_cases(lib,baseline);result['stream']=stream(lib)
    if baseline:
        import research_stage_ablation as S
        result['default_invariance']=S.invariance(lib,baseline)
    result.update(library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest(),
        baseline_library_sha256=hashlib.sha256(Path(a.baseline).read_bytes()).hexdigest() if a.baseline else None,
        oracle_forecasts=sum(v['cases'] for g in result['direct']['cases'].values() for v in g.values()),
        quality='not_evaluated',device='not_evaluated',listening='not_evaluated')
    Path(a.report).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
