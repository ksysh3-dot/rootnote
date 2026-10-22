#!/usr/bin/env python3
"""Experimental shared-phase budget gates; no perceptual-quality claims."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

from quality import FS
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE.parent/'vb51'))
import test_engine as T
import test_port52 as R


def run():
    with tempfile.TemporaryDirectory() as folder:
        binary=str(Path(folder)/'policy')
        subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
                        '-I'+str(HERE.parents[2]/'app/src/main/cpp/libpvb'),
                        str(HERE/'test_upper_policy.cpp'),'-o',binary],check=True)
        subprocess.run([binary],check=True)
    lib=T.load_lib(str(HERE.parent/'build/libpvbcapi.so'))
    for fs in (44100,48000):
        t=np.arange(5*fs)/fs
        harmonic=sum(.08/k*np.sin(2*np.pi*55*k*t+.4*k) for k in range(1,9))
        strong,_,d,_=T.vb_layer(lib,4,fs,harmonic,harmonic)
        # Use the published fixed port weights; testing the attenuation does
        # not require recomputing the original measured phone calibration.
        lookup=R.P.V.lookup
        try:
            R.P.V.lookup=R.R.lookup
            want=R.reference(harmonic,fs,rolloff_db=24)
        finally:
            R.P.V.lookup=lookup
        err=T.rel_db(strong,want)
        T.check(f'fixed24: independent reference @ {fs}',err < -120,rel_db=err)
        adaptive,_,da,_=T.vb_layer(lib,5,fs,harmonic,harmonic)
        gentle,_,dg,_=T.vb_layer(lib,3,fs,harmonic,harmonic)
        sl=slice(2*fs+d,4*fs+d)
        exact=np.array_equal(adaptive[sl],gentle[sl])
        err=None if exact else T.rel_db(adaptive[sl],gentle[sl])
        T.check(f'adaptive: settled stationary note equals gentle12 @ {fs}',(exact or err < -120) and d==da==dg,rel_db=err,bit_exact=exact)
        # Resolved distinct low components should lead to the stronger budget.
        poly=harmonic+.09*np.sin(2*np.pi*82.41*t+.3)
        ya,_,_,_=T.vb_layer(lib,5,fs,poly,poly)
        ys,_,_,_=T.vb_layer(lib,4,fs,poly,poly)
        exact=np.array_equal(ya[sl],ys[sl])
        err=None if exact else T.rel_db(ya[sl],ys[sl])
        T.check(f'adaptive: settled complex source equals fixed24 @ {fs}',exact or err < -120,rel_db=err,bit_exact=exact)
        # Both budgets retain the lower partials at the same phase.
        errors={}
        for f in (165,220):
            ph=np.exp(-2j*np.pi*f*np.arange(2*fs,4*fs)/fs)
            errors[f]=float(20*np.log10(abs(np.mean(strong[sl]*ph))/abs(np.mean(gentle[sl]*ph))))
        T.check(f'fixed24: lower partial levels retained @ {fs}',max(abs(z) for z in errors.values())<.03,error_db=errors)
        audio=T.stereo(np.where(t<2.5,harmonic,poly)).astype(np.float32)
        e=T.Engine(lib,fs,vb_on=1,vb_algo=5,vb_level_db=6,ramp_ms=0)
        lib.pvb_reset(e.h);a=e.process(audio,blocks=[1,17,256,1023]);m=e.meters();e.close()
        e=T.Engine(lib,fs,vb_on=1,vb_algo=5,vb_level_db=6,ramp_ms=0)
        lib.pvb_reset(e.h);b=e.process(audio,blocks=[4096]);e.close()
        T.check(f'adaptive: block invariant waveform @ {fs}',np.array_equal(a,b))
        T.check(f'adaptive: actual controls and transitions published @ {fs}',
                0<=m[21]<=1 and m[22] in (0,1) and m[23]>=2,blend=float(m[21]),target=float(m[22]),transitions=float(m[23]))
        for algo in (4,5):
            for level in (0,6,9):
                e=T.Engine(lib,fs,vb_on=1,vb_algo=algo,vb_level_db=level,ramp_ms=0)
                lib.pvb_reset(e.h);out=e.process(audio*15);lat=e.latency()
                tp=T.true_peak_db(out)
                T.check(f'budget{algo}: +{level} output ceiling @ {fs}',np.isfinite(out).all() and tp<=-.95,dbtp=tp)
                if level==6:
                    e.set(enabled=0,flat=1);e.process(audio[:fs]);before=e.latency()
                    e.set(gate_db=-90);mute=e.process(audio[:fs])
                    T.check(f'budget{algo}: matched bypass alignment/mute @ {fs}',before==lat and np.max(abs(mute[fs//2:]))==0)
                e.close()
        tone=T.stereo(.08*np.sin(2*np.pi*1000*np.arange(fs)/fs))
        e=T.Engine(lib,fs,vb_on=1,vb_algo=3,ramp_ms=0);e.process(tone)
        outputs=[]
        for algo in (4,5,3,1,5):
            e.set(vb_algo=algo);outputs.append(e.process(tone))
        jump=float(np.max(abs(np.diff(np.concatenate(outputs)[:,0]))))
        T.check(f'adaptive: manual algorithm transitions @ {fs}',jump<.02 and e.meters()[T.M['VB']]==6,largest_step=jump)
        e.close()


def song(path, algos=(3,4,5)):
    x,sr=sf.read(path,dtype='float64',always_2d=True)
    if sr==44100:x=resample_poly(x,160,147,axis=0)
    elif sr!=FS:raise ValueError('unexpected sample rate')
    source_duration=len(x)/FS
    x=np.pad(x.astype(np.float32),((0,FS),(0,0))) # flush latency/filter tails
    lib=T.load_lib(str(HERE.parent/'build/libpvbcapi.so'))
    rows=[]
    for algo in algos:
        for level in (0,6,9):
            e=T.Engine(lib,FS,vb_on=1,vb_algo=algo,vb_level_db=level,ramp_ms=0)
            lib.pvb_reset(e.h)
            out=np.empty_like(x)
            observations=[]
            for start in range(0,len(x),FS):
                out[start:start+FS]=e.process(x[start:start+FS])
                m=e.meters()
                observations.append(dict(source_second=start//FS,scene=int(m[16]),strong_weight=float(m[21]),transitions=int(m[23])))
            d=e.latency();m=e.meters();e.close()
            peak=T.true_peak_db(out)
            T.check(f'full song budget{algo} +{level}',np.isfinite(out).all() and peak<=-.95,dbtp=peak)
            rows.append(dict(algo=algo,level_db=level,dbtp=peak,latency_frames=d,
                             transitions=int(m[23]),observations=observations if level==6 else None))
    return dict(source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),duration_s=source_duration,flush_s=1.,
                note='Native full-song numerical checks. 1-second snapshots are not per-frame occupancy or perceptual scores. No new listening result.',rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True)
    p.add_argument('--audio')
    p.add_argument('--song-algos',default='3,4,5')
    a=p.parse_args();run()
    report=dict(checks=T.RESULTS)
    algos=tuple(int(s) for s in a.song_algos.split(','))
    if any(z not in (3,4,5) for z in algos):raise ValueError('unknown song algorithm')
    if a.audio:report['song']=song(a.audio,algos)
    Path(a.report).write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    raise SystemExit(any(not x['ok'] for x in T.RESULTS))
