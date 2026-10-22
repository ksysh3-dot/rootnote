#!/usr/bin/env python3
"""C2-0 global assignment: exact optimization, then observational audio tests.

This does not establish instrument identity across an unresolved crossing.
"""
import argparse,ctypes as C,hashlib,itertools,json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
import test_modulation_research as P
import test_harmonic_continuity as H
import test_engine as T
from vb_quality import measurement as Q
DP=C.POINTER(C.c_double);IP=C.POINTER(C.c_int)

def costs(observed,previous):
    # Independent exhaustive optimizer below checks the declared cost objective.
    count=len(observed);tracks=len(previous);matrix=np.full((count,tracks+count),1e6)
    for i,(f,phase,amplitude,_,_) in enumerate(observed):
        for j,(old,phi,a,life,missing) in enumerate(previous):
            if life<=0 or abs(f-old)>=.1*f:continue
            delta=phase-(phi+np.pi*(f+old)*16/3000)
            ph=np.angle(np.exp(1j*delta))/np.pi
            matrix[i,j]=((f-old)/(.1*f))**2+.08*ph*ph+.04*min(3,abs(np.log((amplitude+1e-9)/(a+1e-9))))**2+.01*missing
        matrix[i,tracks+i]=1.5
    return matrix

def native(lib,observed,previous):
    observed=np.ascontiguousarray(observed,np.float64);previous=np.ascontiguousarray(previous,np.float64);out=np.empty(len(observed),np.int32)
    assert lib.pvb_track_assignment(observed.ctypes.data_as(DP),len(observed),previous.ctypes.data_as(DP),len(previous),out.ctypes.data_as(IP))==0
    assert len(set(out[out>=0]))==sum(out>=0)
    return out

def direct(lib):
    lib.pvb_track_assignment.argtypes=[DP,C.c_int,DP,C.c_int,IP]
    rng=np.random.default_rng(2026101807);max_error=0.
    for case in range(120):
        n=int(rng.integers(1,4));m=int(rng.integers(0,5));f=float(rng.uniform(40,120))
        old=np.column_stack((f+rng.uniform(-7,7,m),rng.uniform(-np.pi,np.pi,m),rng.uniform(.02,.2,m),np.ones(m),rng.integers(0,7,m)))
        obs=np.column_stack((f+rng.uniform(-7,7,n),rng.uniform(-np.pi,np.pi,n),rng.uniform(.02,.2,n),np.ones(n),np.zeros(n)))
        matrix=costs(obs,old);out=native(lib,obs,old);columns=np.where(out>=0,out,m+np.arange(n))
        actual=float(sum(matrix[i,j] for i,j in enumerate(columns)))
        optimum=min(sum(matrix[i,j] for i,j in enumerate(cols)) for cols in itertools.permutations(range(m+n),n))
        error=abs(actual-optimum);max_error=max(max_error,error);assert error<1e-10,(case,actual,optimum)
    # Check the maximum production dimensions with a separate assignment solver,
    # beyond the tiny cases where complete enumeration is affordable.
    full_error=0.
    for case in range(240):
        n=int(rng.integers(1,7));m=int(rng.integers(0,13));f=float(rng.uniform(40,120))
        old=np.column_stack((f+rng.uniform(-12,12,m),rng.uniform(-np.pi,np.pi,m),rng.uniform(.02,.2,m),np.ones(m),rng.integers(0,7,m)))
        obs=np.column_stack((f+rng.uniform(-12,12,n),rng.uniform(-np.pi,np.pi,n),rng.uniform(.02,.2,n),np.ones(n),np.zeros(n)))
        matrix=costs(obs,old);out=native(lib,obs,old);columns=np.where(out>=0,out,m+np.arange(n))
        rr,cc=linear_sum_assignment(matrix)
        error=abs(float(matrix[np.arange(n),columns].sum()-matrix[rr,cc].sum()))
        full_error=max(full_error,error);assert error<1e-10,(case,error)
    # Physical clock counterexample: the production hold path has already
    # advanced the old phase. Adding missing+1 hops again chooses the decoy.
    phase_cases=0
    for f in (55.,68.3,110.):
        omega=2*np.pi*f*16/3000
        for missing in range(1,7):
            old=np.array([[f,missing*omega,.1,1,missing],[f,0,.1,1,missing]],float)
            obs=np.array([[f,(missing+1)*omega,.1,1,0]],float)
            assert np.array_equal(native(lib,obs,old),[0]),(f,missing)
            phase_cases+=1
    old=np.array([[50,0,.1,1,0],[53,0,.1,1,0]],float)
    obs=np.array([[52,2*np.pi*51*16/3000,.1,1,0],[56,2*np.pi*54.5*16/3000,.1,1,0]],float)
    out=native(lib,obs,old);assert np.array_equal(out,[0,1]),out
    # Sorted greedy takes53for52, then cannot match50to56 (6Hz >5.6Hz).
    for n,m in ((0,0),(6,0),(6,12)):
        a=np.tile([55.,0,.1,1,0],(n,1));b=np.tile([55.,0,.1,1,0],(m,1));native(lib,a,b)
    for bad in (np.nan,np.inf):
        invalid=obs.copy();invalid[0,4]=bad;out=np.zeros(len(obs),np.int32)
        assert lib.pvb_track_assignment(invalid.ctypes.data_as(DP),len(obs),old.ctypes.data_as(DP),len(old),out.ctypes.data_as(IP))==-2
    return dict(seed=2026101807,exhaustive_cases=120,max_objective_error=max_error,
                full_dimension_oracle_cases=240,full_dimension_max_objective_error=full_error,
                held_phase_clock_cases=phase_cases,
                greedy_counterexample={'previous':[50,53],'observed':[52,56],'global_matches':[50,53],'greedy_matches':[53,None]},bounds_passed=True)

def measure(lib,x,flags,fs=48000):
    r=P.render(lib,x,3,True,fs=fs,stage_flags=flags)
    s=H.summarize(r['rows']);s.update(stem_rms_dbfs=float(T.db(np.sqrt(np.mean(r['stem']**2)))),full_peak_dbfs=T.true_peak_db(r['output']),
                                   callback_ms_p95=float(np.percentile(r['cost_ms'],95)))
    assert s['full_peak_dbfs']<-1 and np.isfinite(r['output']).all()
    return r,s

def integration(lib):
    # A fixed synthetic mixture reaches ambiguous assignments in the actual
    # analyzer/tracker/renderer path. Disabling both native C2 dispatch branches
    # must fail this guard even if the standalone assignment API still works.
    fs=48000;t=np.arange(int(3.4*fs))/fs
    rng=np.random.default_rng(2026101808);x=np.zeros_like(t)
    for f in rng.uniform(42,100,5):
        amplitude=.025*(1+.8*np.sin(2*np.pi*rng.uniform(.7,10)*t+rng.uniform(-np.pi,np.pi)))
        phase=2*np.pi*f*t+4*np.sin(2*np.pi*rng.uniform(.3,1.4)*t+rng.uniform(-np.pi,np.pi))
        x+=amplitude*np.cos(phase)
    old,_=measure(lib,x,0);new,_=measure(lib,x,256)
    assert old['rows'].shape==new['rows'].shape
    assert np.array_equal(H.core_indices(old['rows']),H.core_indices(new['rows']))
    count=int((H.tracks(old['rows'])[:,:,0]!=H.tracks(new['rows'])[:,:,0]).sum())
    assert count>0,'native_c2_assignment_not_reached'
    return dict(seed=2026101808,changed_id_slots=count,
                note='Dispatch reachability only; changes in IDs are not correct-source labels.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',required=True);p.add_argument('--baseline');p.add_argument('--report',required=True);a=p.parse_args()
    lib=P.api(a.lib);result=dict(schema='pvb.phase2.track_assignment.v2',direct=direct(lib),integration=integration(lib),cases={},device='not_evaluated',listening='not_evaluated',
                               quality='not_evaluated',note='Registration counts are not source identities or listening scores.',library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest())
    fs=48000;t=np.arange(int(3.4*fs))/fs
    signals={'crossing':.10*np.cos(2*np.pi*(48*t+3*t*t))+.07*np.cos(2*np.pi*(72*t-3*t*t)+.8),
             'near_pair':.10*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6),
             'note_change':.15*np.cos(2*np.pi*(55*np.minimum(t,1.7)+65*np.maximum(t-1.7,0))),
             'off':.15*np.cos(2*np.pi*55*t)*(t<1.7),
             'am20':.15*(1+.7*np.sin(2*np.pi*20*t))*np.cos(2*np.pi*80*t)}
    for name,x in signals.items():
        modes={}
        for flags in (0,256,240,496):
            r,s=measure(lib,x,flags)
            if name=='off':assert np.max(abs(r['stem'][int(2.8*fs):]))<1e-7
            if name=='am20' and flags in (240,496):
                s['am_harmonics']=Q.am_harmonics(r['stem'],fs,80,20,.7,algorithm=4,latency=r['latency']/fs,temporal=True)
                s['am_quality']=Q.aggregate_am(s['am_harmonics']);assert s['am_quality']=='pass'
            modes[str(flags)]=s
        result['cases'][name]=modes;print(name,{k:(v['birth_tracks'],v['zero_pre_envelope_hops']) for k,v in modes.items()},flush=True)
    checks=[]
    for fs in (44100,48000):
        t=np.arange(fs*2)/fs;x=.15*(1+.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*55*t)
        aa=P.render(lib,x,3,True,fs=fs,stage_flags=496);bb=P.render(lib,x,3,True,fs=fs,stage_flags=496,block=1379)
        assert np.array_equal(aa['output'],bb['output']) and np.array_equal(aa['stages'],bb['stages'])
        prefix=x.copy();prefix[int(.8*fs):]*=-1;cc=P.render(lib,prefix,3,True,fs=fs,stage_flags=496)
        assert np.array_equal(aa['output'][:int(.8*fs)],cc['output'][:int(.8*fs)])
        checks.append(dict(fs=fs,chunk_and_prefix='pass'))
    if a.baseline:
        import research_stage_ablation as A
        result['baseline_invariance']=A.invariance(lib,P.api(a.baseline))
    result['stream_checks']=checks;Path(a.report).write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
