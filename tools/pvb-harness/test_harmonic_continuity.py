#!/usr/bin/env python3
"""Harmonic-hop diagnostics and opt-in C1 research gates, not listening results."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.signal import resample_poly
import test_engine as T

HERE=Path(__file__).resolve().parent
FIELDS,HEADER,TRACK,TRACKS,ROWS=700,28,56,12,72

def api(path):
    lib=T.load_lib(str(path))
    lib.pvb_set_diagnostic_capture.argtypes=[C.c_void_p,C.c_int]
    lib.pvb_copy_harmonic.argtypes=[C.c_void_p,T.FP,C.c_int]
    lib.pvb_set_continuity_research.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int]
    assert lib.pvb_harmonic_fields()==FIELDS and lib.pvb_harmonic_rows()==ROWS
    return lib

def render(lib,x,fs=48000,algo=4,c1=False,capture=True,block=4096,level=6):
    e=T.Engine(lib,fs,vb_on=1,vb_algo=algo,vb_level_db=level,out_db=-18,ramp_ms=0)
    if c1: lib.pvb_set_continuity_research(e.h,1,2,6,6)
    lib.pvb_set_diagnostic_capture(e.h,int(capture))
    out=np.ascontiguousarray(x,np.float32).copy()
    if out.ndim==1: out=T.stereo(out)
    rows=[];buf=np.empty(ROWS*FIELDS,np.float32)
    for off in range(0,len(out),block):
        b=out[off:off+block]
        lib.pvb_process(e.h,b.ctypes.data_as(T.FP),len(b))
        n=lib.pvb_copy_harmonic(e.h,buf.ctypes.data_as(T.FP),len(buf))
        if capture:
            assert n>=0,n
            if n:
                data=buf[:n*FIELDS].reshape(n,FIELDS).copy()
                assert ((data[:,0]>=0)&(data[:,0]<len(b))).all()
                data[:,0]+=off;rows.append(data)
        else: assert n==-1
    latency=e.latency();e.close()
    return out,np.vstack(rows) if rows else np.empty((0,FIELDS),np.float32),latency

def tracks(rows): return rows[:,HEADER:].reshape(-1,TRACKS,TRACK)
def core_indices(rows): return sum(rows[:,3+i].astype(np.int64)<<(16*i) for i in range(4))
def summarize(rows):
    ts=tracks(rows);valid=ts[:,:,1]>0
    hs=ts[:,:,14:].reshape(-1,TRACKS,7,6)
    return dict(hops=len(rows),observed_tracks=int((ts[:,:,1]==2).sum()),
        birth_tracks=int((ts[:,:,1]==1).sum()),held_tracks=int((ts[:,:,1]==3).sum()),
        releasing_tracks=int((ts[:,:,1]==4).sum()),ended_tracks=int((ts[:,:,1]==5).sum()),
        lost_track_hops=int(rows[:,22].sum()),fit_rejected_track_hops=int(((ts[:,:,10].astype(int)&8)>0).sum()),
        grid_rejected_harmonic_hops=int(((hs[:,:,:,4].astype(int)&16)>0).sum()),
        capacity_omissions=int(rows[:,21].sum()),capacity_hops=int((rows[:,21]>0).sum()),
        emitted_harmonic_hops=int((hs[:,:,:,1]>1e-12).sum()),
        permission_held_harmonic_hops=int(((hs[:,:,:,2]>0)&((hs[:,:,:,4].astype(int)&16)>0)).sum()),
        zero_pre_envelope_hops=int((np.sum(hs[:,:,:,1]**2,axis=(1,2))<1e-20).sum()),
        tracks_with_id=int(valid.sum()))

def run(args):
    lib=api(HERE/'build/libpvbcapi.so');result={'schema':'pvb.harmonic_research.v1','listening_validated':False,'adopted_in_app':False,'quality_acceptance':'not established; engineering checks only','cases':[]}
    # Counter/timestamp mapping, boundary shapes, and diagnostic output invariance.
    for fs in (44100,48000):
        t=np.arange(fs*3)/fs
        x=.11*np.sin(2*np.pi*55*t)+.04*np.sin(2*np.pi*110*t+.3)
        y,r,d=render(lib,x,fs,block=1379)
        yn,_,dn=render(lib,x,fs,capture=False,block=1379)
        assert np.array_equal(y,yn) and d==dn
        assert np.all(np.diff(core_indices(r))==16) and (r[:,23]==1).all()
        # Exact host event mapping is floor(core_index * host/core), including fractional44.1k phase.
        expected=(core_indices(r)*fs)//3000
        start_offset=r[:,0].astype(np.int64)-expected
        assert np.all(start_offset==start_offset[0]), np.unique(start_offset)
        assert np.allclose(r[:,9],core_indices(r)*fs/3000-expected-382.*fs/3000-80*fs/48000,atol=.001)
        assert np.isfinite(r).all()
        ts=tracks(r);h=ts[:,:,14:].reshape(-1,12,7,6)
        assert ((h[:,:,:,2]>=0)&(h[:,:,:,2]<=1)).all()
        assert np.max(np.abs(h[:,:,:,3]))<=.120001
        for alg in (0,1):
            _,rr,_=render(lib,x[:fs],fs,algo=alg)
            assert len(rr)==0
        # A largest supported callback remains bounded; insufficient consumer capacity is explicit.
        e=T.Engine(lib,fs,vb_on=1,vb_algo=5,ramp_ms=0)
        lib.pvb_set_diagnostic_capture(e.h,1);b=T.stereo(x[:16384]);lib.pvb_process(e.h,b.ctypes.data_as(T.FP),len(b))
        buf=np.zeros(ROWS*FIELDS,np.float32)
        assert 0<lib.pvb_copy_harmonic(e.h,buf.ctypes.data_as(T.FP),len(buf))<=ROWS
        assert lib.pvb_copy_harmonic(e.h,buf.ctypes.data_as(T.FP),1)==-2
        lib.pvb_set_diagnostic_capture(e.h,0)
        assert lib.pvb_copy_harmonic(e.h,buf.ctypes.data_as(T.FP),len(buf))==-1
        e.close()
        result['cases'].append(dict(name='trace_invariance_clock_bounds',sample_rate=fs,hops=len(r),ok=True))
        if args.baseline:
            old=T.load_lib(args.baseline)
            for a in range(6):
                e=T.Engine(old,fs,vb_on=1,vb_algo=a,vb_level_db=9,out_db=-18,ramp_ms=0)
                yo=e.process(T.stereo(x),block=1379);e.close()
                yn,_,_=render(lib,x,fs,algo=a,level=9,block=1379)
                assert np.array_equal(yo,yn),(fs,a)
            result['cases'].append(dict(name='test27_bit_exact_all6',sample_rate=fs,ok=True))
    fs=48000;t=np.arange(fs*5)/fs
    signals={
      'steady':.15*np.sin(2*np.pi*55*t),
      'am':.15*(1+.7*np.sin(2*np.pi*7*t))*np.sin(2*np.pi*55*t),
      'vibrato':.15*np.sin(2*np.pi*55*t+.5*np.sin(2*np.pi*5*t)),
      'glide':.15*np.sin(2*np.pi*(45*t+5*t*t)),
      'close_pair':.1*np.sin(2*np.pi*55*t)+.06*np.sin(2*np.pi*58*t+.4),
      'note_change':.15*np.where(t<2.5,np.sin(2*np.pi*55*t),np.sin(2*np.pi*82*t)),
      'note_off':.15*np.sin(2*np.pi*55*t)*(t<2.5),
      'silence':np.zeros_like(t),
    }
    signals['mixed']=signals['am']+.025*np.random.default_rng(20261019).normal(size=len(t))
    for name,x in signals.items():
        b,rb,d=render(lib,x);c,rc,dc=render(lib,x,c1=True)
        assert dc==d and np.isfinite(c).all()
        assert T.true_peak_db(c)<-1+.05
        hs=tracks(rc)[:,:,14:].reshape(-1,12,7,6)
        assert ((hs[:,:,:,2]>=0)&(hs[:,:,:,2]<=1)).all()
        ts=tracks(rc)
        assert np.max(ts[:,:,9])<=13 # six hold + six release, allowing exact endpoint
        if name in ('note_off','silence'):
            assert np.max(np.abs(c[int(3.5*fs):]))<1e-7 # filters allowed1s to decay, no persistent tone
        result['cases'].append(dict(name=name,baseline=summarize(rb),c1=summarize(rc),
            changed=not np.array_equal(b,c),baseline_rms_db=float(T.db(np.sqrt(np.mean(b*b)))),
            c1_rms_db=float(T.db(np.sqrt(np.mean(c*c)))),ok=True))
    if args.audio:
        import soundfile as sf
        x,fs=sf.read(args.audio,dtype='float32',always_2d=True)
        source_fs=fs
        if fs!=48000: x=resample_poly(x,48000//np.gcd(fs,48000),fs//np.gcd(fs,48000),axis=0).astype(np.float32);fs=48000
        b,rb,d=render(lib,x,level=9);c,rc,dc=render(lib,x,c1=True,level=9)
        assert d==dc and np.isfinite(c).all()
        result['audio']={'sha256':hashlib.sha256(Path(args.audio).read_bytes()).hexdigest(),
            'source_sample_rate':source_fs,'processing_sample_rate':fs,'resampler':'scipy.signal.resample_poly default FIR',
            'seconds':len(x)/fs,'baseline':summarize(rb),'c1':summarize(rc),
            'baseline_true_peak_dbfs':T.true_peak_db(b),'c1_true_peak_dbfs':T.true_peak_db(c),
            'note':'Source render uses fixed algo4/+9,out-18,default EQ and zero initial state; not a bit-exact recreation of phone ZIP.'}
        if args.renders:
            out=Path(args.renders);out.mkdir(parents=True,exist_ok=True)
            sf.write(out/'baseline-full.wav',b,fs,subtype='FLOAT');sf.write(out/'c1-full.wav',c,fs,subtype='FLOAT')
    if args.report:
        Path(args.report).parent.mkdir(parents=True,exist_ok=True)
        Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline');p.add_argument('--audio');p.add_argument('--report');p.add_argument('--renders')
    run(p.parse_args())
