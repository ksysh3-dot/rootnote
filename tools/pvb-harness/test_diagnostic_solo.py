#!/usr/bin/env python3
"""Generated-layer monitor, same-pass stems, state preservation and capture contracts."""
import ctypes
import os
import numpy as np
from test_engine import Engine, FP, load_lib, true_peak_db

HERE = os.path.dirname(os.path.abspath(__file__))
lib = load_lib(os.path.join(HERE, 'build/libpvbcapi.so'))
lib.pvb_set_diagnostic_capture.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.pvb_copy_diagnostic.argtypes = [ctypes.c_void_p, FP, FP, ctypes.c_int, FP, ctypes.c_int]
lib.pvb_copy_diagnostic.restype = ctypes.c_int
FIELDS = 32 + lib.pvb_param_count()
assert FIELDS == 88  # 32 observed + 56 parameters (33 + 14 developer-mode + 9 crosstalk-cancellation values)

def capture(e, x, block=4096):
    lib.pvb_set_diagnostic_capture(e.h, 1)
    outputs=[]; layers=[]; fulls=[]; traces=[]
    for start in range(0,len(x),block):
        a=x[start:start+block]; y=e.process(a,block=block)
        layer=np.empty_like(y); full=np.empty_like(y); tr=np.empty(FIELDS,np.float32)
        assert lib.pvb_copy_diagnostic(e.h,layer.ctypes.data_as(FP),full.ctypes.data_as(FP),y.size,tr.ctypes.data_as(FP),FIELDS)==1
        assert tr[0]==1 and tr[1]==len(a) and np.isfinite(tr).all()
        outputs.append(y); layers.append(layer);fulls.append(full);traces.append(tr)
    return tuple(np.concatenate(v) for v in (outputs,layers,fulls)),np.array(traces)

def signal(sr,seconds,amp=.09):
    t=np.arange(int(sr*seconds))/sr
    return np.column_stack([amp*(np.sin(2*np.pi*55*t)+.6*np.sin(2*np.pi*87*t)+.3*np.sin(2*np.pi*1200*t)),
                           amp*(np.sin(2*np.pi*63*t)+.5*np.sin(2*np.pi*101*t)+.3*np.sin(2*np.pi*1700*t))]).astype(np.float32)

for sr in [44100,48000]:
    x=signal(sr,2.2)
    for algo in range(6):
        kw=dict(vb_on=1,vb_algo=algo,vb_level_db=9,out_db=-18,ramp_ms=0)
        normal=Engine(lib,sr,**kw); solo=Engine(lib,sr,**kw)
        # Warm up identical states; then switch only the monitor.
        assert np.array_equal(normal.process(x[:sr]),solo.process(x[:sr]))
        solo.set(diagnostic_solo=1)
        expected=normal.process(x[sr:])
        (heard,layer,full),tr=capture(solo,x[sr:])
        assert np.array_equal(full,expected),(sr,algo,'full mix changed')
        np.testing.assert_allclose(heard[int(.2*sr):],layer[int(.2*sr):],atol=1e-7,rtol=1e-6)
        assert normal.latency()==solo.latency()
        assert normal.match_db()==solo.match_db()
        assert tr[-1,25]==1 and tr[:,23].max()<.001
        assert np.sqrt(np.mean(layer[int(.2*sr):]**2))>1e-7
        # Return and internal state remain identical.
        solo.set(diagnostic_solo=0)
        exp=normal.process(x[:sr]); got=solo.process(x[:sr])
        assert np.array_equal(exp[int(.11*sr):],got[int(.11*sr):])
        normal.close();solo.close()
print('PASS: all six algorithms, 44.1/48k: hidden full mix and matcher unchanged, solo=actual component, same latency, exact return')

# Independent additive reference: with limiter inactive, full-layer equals level-muted generator path.
x=signal(48000,3,.025)
for algo in [0,1,5]:
    e=Engine(lib,48000,vb_on=1,vb_algo=algo,vb_level_db=9,out_db=-20,ramp_ms=0)
    zero=Engine(lib,48000,vb_on=1,vb_algo=algo,vb_level_db=-120,out_db=-20,ramp_ms=0)
    (heard,layer,full),tr=capture(e,x)
    dry=zero.process(x)
    assert np.array_equal(full,heard)
    np.testing.assert_allclose((full-layer)[24000:],dry[24000:],atol=2e-8,rtol=2e-5)
    e.close();zero.close()
print('PASS: independent sum decomposition and normal-mode capture')

# No raw music leakage in solo when disabled/no generated component, and final mute always wins.
for params in [dict(vb_on=0),dict(vb_on=1,vb_level_db=-120),dict(vb_on=1,enabled=0),dict(vb_on=1,gate_db=-120)]:
    e=Engine(lib,48000,diagnostic_solo=1,ramp_ms=0,**params)
    (y,layer,full),tr=capture(e,x)
    assert np.max(np.abs(y[48000:]))==0,params
    e.close()
print('PASS: no layer/bypass leakage and gate cannot be escaped')

# Stress isolated-layer protection, preserving the full mix exactly at high gain.
x=signal(48000,3,.8)
a=Engine(lib,48000,vb_on=1,vb_algo=5,vb_level_db=12,out_db=12,ramp_ms=0)
b=Engine(lib,48000,vb_on=1,vb_algo=5,vb_level_db=12,out_db=12,ramp_ms=0,diagnostic_solo=1)
y=a.process(x);(solo,layer,full),tr=capture(b,x)
assert np.array_equal(full,y)
assert np.isfinite(solo).all() and true_peak_db(solo[24000:]) < -.8
assert tr[:,22].max()>0
# Strict capacity/ownership protocol: never return stale arrays after disabling/oversize requests.
l=np.empty((10,2),np.float32);f=l.copy();t=np.empty(FIELDS,np.float32)
assert lib.pvb_copy_diagnostic(b.h,l.ctypes.data_as(FP),f.ctypes.data_as(FP),20,t.ctypes.data_as(FP),FIELDS)==0
lib.pvb_set_diagnostic_capture(b.h,0)
assert lib.pvb_copy_diagnostic(b.h,l.ctypes.data_as(FP),f.ctypes.data_as(FP),20,t.ctypes.data_as(FP),FIELDS)==0
a.close();b.close()
print('PASS: limiter stress, finite/true-peak safe output and rejected stale capture')
# A solo-only UI update must not shorten a volume/filter ramp already in flight.
x=signal(48000,1)
a=Engine(lib,48000,vb_on=1,vb_algo=5,out_db=-18,ramp_ms=0)
b=Engine(lib,48000,vb_on=1,vb_algo=5,out_db=-18,ramp_ms=0)
a.process(x);b.process(x)
a.set(out_db=-6,low_db=8,ramp_ms=300);b.set(out_db=-6,low_db=8,ramp_ms=300)
a.process(x[:2400]);b.process(x[:2400])
b.set(diagnostic_solo=1,ramp_ms=20)
y=a.process(x);(_,_,full),_=capture(b,x)
assert np.array_equal(y,full)
a.close();b.close()
print('PASS: monitor change preserves in-flight gain and filter ramps')
