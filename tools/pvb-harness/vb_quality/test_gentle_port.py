#!/usr/bin/env python3
"""Release gates for gentle128: independent reference, both rates and switching.

These are numerical/engineering gates, not a new listening-quality result.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.signal import resample_poly, sosfilt
import soundfile as sf

from quality import CANDIDATES, FS, layer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent/'vb51'))
import test_engine as T
import test_port52 as R52

ALGO = 3


def run():
    lib = T.load_lib(str(HERE.parent/'build/libpvbcapi.so'))
    sr=48000
    t=np.arange(5*sr)/sr
    x=sum(.09/k*np.sin(2*np.pi*55*k*t+.4*k) for k in range(1,9))
    x+=.05*np.sin(2*np.pi*65.41*t+.7)*(t>1)*(t<2)
    x*=((t>.2)&(t<4.3))
    for fs in (44100,48000):
        mono=resample_poly(x,147,160) if fs==44100 else x
        got,right,d,_=T.vb_layer(lib,ALGO,fs,mono,mono)
        want=R52.reference(mono,fs,rolloff_db=12)
        err=T.rel_db(got,want)
        T.check(f'gentle: independent layer reference @ {fs}',
                err < -120 and np.array_equal(got,right) and d==R52.R.latency_frames(fs),
                rel_db=err, latency_frames=d)
        audio=T.stereo(mono)
        eq={k:float(np.float32(v)) for k,v in dict(T.V11,hp_hz=160.,low_db=4.2,low_q=1.06).items()}
        e=T.Engine(lib,fs,vb_on=1,vb_algo=ALGO,vb_level_db=6,ramp_ms=0,**eq)
        lib.pvb_reset(e.h)
        actual=e.process(audio,blocks=[1,17,256,1023])
        meters=e.meters();total=e.latency();lim=total-d
        a=audio.astype(float)
        h=R52.reference(a.mean(1),fs,eq,rolloff_db=12)
        dry=np.pad(a,((d,0),(0,0)))[:len(a)]
        expected=(sosfilt(T.ref_sos(fs,eq),dry,axis=0)+h[:,None]*10**(6/20))*10**(-5/20)
        err=T.rel_db(actual[lim+fs:],expected[fs:-lim])
        T.check(f'gentle: full engine custom EQ +6 @ {fs}',err < -100 and meters[T.M['VB']]==4,
                rel_db=err,latency_frames=total)
        observed=meters[17:21]
        T.check(f'gentle: research observations available @ {fs}',
                np.isfinite(observed).all() and np.sum(observed)>100 and
                np.sum(observed)==round(len(mono)*3000/fs/16-23),
                scene_counts=observed.tolist())
        e.set(flat=1,enabled=0)
        e.process(audio[:fs])
        T.check(f'gentle: matched bypass preserves latency @ {fs}',e.latency()==total)
        e.set(gate_db=-90)
        muted=e.process(audio[:fs])
        T.check(f'gentle: matched bypass obeys final mute @ {fs}',np.max(abs(muted[fs//2:]))==0)
        e.close()
        hot=T.stereo(mono*20)
        for level in (0,6,9):
            e=T.Engine(lib,fs,vb_on=1,vb_algo=ALGO,vb_level_db=level,ramp_ms=0)
            lib.pvb_reset(e.h);out=e.process(hot);e.close()
            tp=T.true_peak_db(out)
            T.check(f'gentle: hot +{level} true peak @ {fs}',np.isfinite(out).all() and tp<=-.95,dbtp=tp)
        # Switch under actual continuous content, including equal and unequal delays.
        tone=T.stereo(.08*np.sin(2*np.pi*1000*np.arange(fs)/fs))
        e=T.Engine(lib,fs,vb_on=1,vb_algo=2,ramp_ms=0)
        e.process(tone)
        chunks=[]
        for algo in (3,2,3,1,3):
            e.set(vb_algo=algo);chunks.append(e.process(tone))
        jump=float(np.max(abs(np.diff(np.concatenate(chunks)[:,0]))))
        T.check(f'gentle: algorithm switch @ {fs}',jump<.02 and e.meters()[T.M['VB']]==4,largest_step=jump)
        e.set(vb_algo=2);e.process(tone)
        m=e.meters()
        T.check(f'gentle: observations cleared after leaving mode @ {fs}',np.sum(m[17:21])==0)
        e.close()

    # Check actual spectral attenuation, not only whole-waveform similarity.
    tt=np.arange(4*FS)/FS
    harmonic=sum(.08/k*np.sin(2*np.pi*55*k*tt+.4*k) for k in range(1,9))
    original,_,d,_=T.vb_layer(lib,2,FS,harmonic,harmonic)
    gentle,_,_,_=T.vb_layer(lib,3,FS,harmonic,harmonic)
    errors={}
    for f in (165,220,275,330):
        phasor=np.exp(-2j*np.pi*f*np.arange(FS,3*FS)/FS)
        actual=20*np.log10(abs(np.mean(gentle[FS+d:3*FS+d]*phasor))/
                          abs(np.mean(original[FS+d:3*FS+d]*phasor)))
        errors[f]=float(actual+12*max(np.log2(f/220),0))
    T.check('gentle: lower partials retained and upper partials attenuated',
            max(abs(v) for v in errors.values())<.03,error_db=errors)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True)
    a=p.parse_args()
    run()
    Path(a.report).write_text(json.dumps(T.RESULTS,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    raise SystemExit(any(not r['ok'] for r in T.RESULTS))
