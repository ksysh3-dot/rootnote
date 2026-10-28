#!/usr/bin/env python3
"""P1+ full-analysis experiments. Diagnostic metrics are not listening scores.

The real app profile (algorithm 6) runs through the production Engine. Harmonic
trace and stage capture are observers. The frequency support comes from the
input generator, never from peaks selected in the candidate output.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.signal import resample_poly
import test_engine as T
import test_harmonic_continuity as H
from vb_quality.stage_capture import StageCapture


def api(path):
    lib = H.api(str(path))
    lib.pvb_copy_diagnostic.argtypes = [C.c_void_p,T.FP,T.FP,C.c_int,T.FP,C.c_int]
    if hasattr(lib, 'pvb_set_p1plus_research'):
        lib.pvb_set_p1plus_research.argtypes = [C.c_void_p, C.c_uint]
    if hasattr(lib, 'pvb_set_p1pp_impact_research'):
        lib.pvb_set_p1pp_impact_research.argtypes = [C.c_void_p, C.c_int]
    if hasattr(lib, 'pvb_set_p1pp_v04_research'):
        lib.pvb_set_p1pp_v04_research.argtypes = [C.c_void_p, C.c_int]
    return lib


def render(lib, x, fs=48000, flags=0, block=4096, algo=6, capture=True, impact_mode=0,
           stage_flags=0, out_db=-18, before_process=None):
    engine = T.Engine(lib, fs, vb_on=1, vb_algo=algo, vb_level_db=6,
                      out_db=out_db, ramp_ms=0)
    if flags:
        assert lib.pvb_set_p1plus_research(engine.h, flags) == 1
    if impact_mode:
        assert lib.pvb_set_p1pp_impact_research(engine.h, impact_mode) == 1
    # P1++ research knobs (modes 5-8): "hold,historyDb,steadyHops,steadyA"; unset = the evaluated defaults
    v04 = int(__import__('os').environ.get('P1PP_V04', '0'))
    if v04:
        assert lib.pvb_set_p1pp_v04_research(engine.h, v04) == 1
    params = __import__('os').environ.get('P1PP_PARAMS')
    if params:
        hold, hist, hops, ratio, *rest = params.split(',')
        strength = float(rest[0]) if rest else .4
        lib.pvb_set_p1pp_research_params.argtypes = [C.c_void_p, C.c_int, C.c_double, C.c_int, C.c_double, C.c_double]
        assert lib.pvb_set_p1pp_research_params(engine.h, int(hold), float(hist), int(hops), float(ratio), strength) == 1
    if before_process:
        before_process(lib, engine.h)  # host research hooks that reset the module (e.g. study 1 injection)
    lib.pvb_set_diagnostic_capture(engine.h, int(capture))
    stages = StageCapture(lib, engine.h, stage_flags, int(len(x)/fs*3000)+16) if capture else None
    source=np.asarray(x,np.float32)
    output=T.stereo(source) if source.ndim==1 else np.ascontiguousarray(source).copy()
    if output.ndim!=2 or output.shape[1]!=2:raise ValueError('Only mono or stereo input is supported')
    stem = np.zeros_like(output)
    full = np.zeros_like(output)
    buf = np.empty(H.ROWS*H.FIELDS, np.float32)
    header = np.empty(32+lib.pvb_param_count(), np.float32)
    rows, costs = [], []
    try:
        for start in range(0, len(x), block):
            b = output[start:start+block]
            begin = time.perf_counter()
            lib.pvb_process(engine.h, b.ctypes.data_as(T.FP), len(b))
            costs.append(time.perf_counter()-begin)
            if capture:
                s, f = stem[start:start+block], full[start:start+block]
                assert lib.pvb_copy_diagnostic(engine.h, s.ctypes.data_as(T.FP),
                       f.ctypes.data_as(T.FP), b.size, header.ctypes.data_as(T.FP), len(header)) == 1
                n = lib.pvb_copy_harmonic(engine.h, buf.ctypes.data_as(T.FP), len(buf))
                assert n >= 0
                if n:
                    row = buf[:n*H.FIELDS].reshape(n, H.FIELDS).copy()
                    row[:,0] += start
                    rows.append(row)
        result = dict(output=output, stem=stem,
                      rows=np.vstack(rows) if rows else np.empty((0,H.FIELDS)),
                      stages=stages.copy() if stages else None,
                      latency=engine.latency(), meters=engine.meters(),
                      callback_total_seconds=float(sum(costs)),
                      callback_p95_ms=float(np.percentile(costs,95)*1000))
        assert np.isfinite(output).all() and np.isfinite(stem).all()
        return result
    finally:
        if stages: stages.close()
        engine.close()


def fixtures(fs=48000, heldout=False):
    t=np.arange(fs*5)/fs
    if heldout:
        rng=np.random.default_rng(2026102602)
        for j in range(6):
            f=float(rng.uniform(43,110)); rate=float(rng.uniform(1.2,8))
            phase=float(rng.uniform(-np.pi,np.pi)); k=3 if f<70 else 2
            x=.12*np.sin(2*np.pi*f*t+.2)+.0012*(1+.8*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*k*f*t+phase)
            yield f'held_anchor_{j}',x,[f],rate
        return
    for f in (55.,83.):
        yield f'steady_{f:g}',.12*np.sin(2*np.pi*f*t+.2),[f],0.
    for rate in (3.,7.,11.):
        yield f'am_{rate:g}',.12*(1+.7*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*55*t+.2),[55.],rate
    for phase in (.3,1.7):
        for rate in (2.,7.):
            x=.12*np.sin(2*np.pi*55*t+.2)+.0012*(1+.8*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*165*t+phase)
            yield f'anchor_{phase:g}_{rate:g}',x,[55.],rate
    a=.08*(1+.4*np.sin(2*np.pi*2*t))
    b=.08*(1-.4*np.sin(2*np.pi*2*t))
    yield 'rank_cross',a*np.sin(2*np.pi*55*t)+b*np.sin(2*np.pi*83*t+.4),[55.,83.],2.
    yield 'close_pair',.12*np.sin(2*np.pi*55*t)+.07*np.sin(2*np.pi*58*t+.4),[55.,58.],0.
    yield 'note_off',.12*np.sin(2*np.pi*55*t)*(t<2.5),[],0.
    rng=np.random.default_rng(2026102601)
    yield 'noise',rng.normal(0,.025,len(t)),[],0.
    yield 'silence',np.zeros_like(t),[],0.


def spectral_support(y, fs, fundamentals, rate):
    """Project on declared input-derived lines, including genuine AM sidebands.

    The residual is a limited-model diagnostic, not a general perceptual noise
    estimate. Constant phase is free; no gain normalization of the output is done.
    """
    if not fundamentals:return None
    z=resample_poly(np.asarray(y[:,0],float),3000,fs)[3000:12000]
    t=np.arange(len(z))/3000
    carriers=sorted(set(round(k*f,9) for f in fundamentals for k in range(2,9) if k*f<1300))
    lines=sorted(set(round(k*f+d*rate,9) for f in fundamentals for k in range(1,9)
                     for d in ((-1,0,1) if rate else (0,)) if 1<k*f+d*rate<1300))
    design=np.column_stack([v for f in lines for v in (np.cos(2*np.pi*f*t),np.sin(2*np.pi*f*t))])
    coef=np.linalg.lstsq(design,z,rcond=1e-10)[0]
    residual=z-design@coef
    amps={str(f):float(np.hypot(*coef[2*j:2*j+2])) for j,f in enumerate(lines) if f in carriers}
    wanted=sum(v*v/2 for v in amps.values())
    return dict(residual_db=float(10*np.log10((np.mean(residual**2)+1e-30)/(wanted+1e-30))),
                carrier_rms=float(np.sqrt(wanted)),carrier_amplitudes=amps,
                residual_rms=float(np.sqrt(np.mean(residual**2))),
                total_rms=float(np.sqrt(np.mean(z*z))))


def summarize(r, fs, fundamentals, rate):
    rows=r['rows']; tr=H.tracks(rows); hs=tr[:,:,14:].reshape(-1,12,7,6)
    active=(tr[:,:,1]>0)&(tr[:,:,1]<5)
    observed=(tr[:,:,1]==1)|(tr[:,:,1]==2)
    late=rows[:,0]>fs
    valid=observed & late[:,None]
    # A high raw residual is not itself an error: valid modulation can explain it.
    rescued=valid & (tr[:,:,12]>-15) & (tr[:,:,6]<=-20)
    rejected=valid & (tr[:,:,6]>-15)
    amps=hs[:,:,:,1]
    weights=amps**2
    phase_energy=float(np.sum(weights*hs[:,:,:,3]**2)/(np.sum(weights)+1e-30))
    out=dict(hops=len(rows),active_track_hops=int(active.sum()),
             raw_high_but_modulation_accepted=int(rescued.sum()),
             rejected_observed_track_hops=int(rejected.sum()),
             phase_step_weighted_rms=float(np.sqrt(phase_energy)),
             stem_rms=float(np.sqrt(np.mean(r['stem'].astype(float)**2))),
             output_peak=float(np.max(abs(r['output']))),latency_frames=r['latency'],
             callback_p95_ms=r['callback_p95_ms'],
             output_sha256=hashlib.sha256(r['output'].tobytes()).hexdigest(),
             support=spectral_support(r['stem'],fs,fundamentals,rate))
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--flags',type=int,default=0)
    p.add_argument('--fs',type=int,default=48000)
    p.add_argument('--heldout',action='store_true')
    p.add_argument('--save-arrays',action='store_true')
    args=p.parse_args(); lib=api(args.library.resolve())
    result=dict(schema='pvb.p1plus.exploration.v1',flags=args.flags,fs=args.fs,
                heldout=args.heldout,listening_validated=False,cases={})
    args.report.parent.mkdir(parents=True,exist_ok=True)
    for name,x,freqs,rate in fixtures(args.fs,args.heldout):
        r=render(lib,x,args.fs,args.flags)
        result['cases'][name]=summarize(r,args.fs,freqs,rate)
        if args.save_arrays:
            np.savez_compressed(args.report.parent/(args.report.stem+'-'+name+'.npz'),
                                output=r['output'],stem=r['stem'],rows=r['rows'],stages=r['stages'])
        s=result['cases'][name]
        print(name, 'rescue',s['raw_high_but_modulation_accepted'],
              'reject',s['rejected_observed_track_hops'],
              'support',s['support']['residual_db'] if s['support'] else None,flush=True)
        args.report.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
