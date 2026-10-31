import sys,time
sys.path.insert(0,'/home/ksysh/r3a-dev/plan16/B1')
import numpy as np, ctypes as C
import api084 as CA
import test_engine as T
from pathlib import Path
x=(np.random.randn(48000*10)*0.05).astype(np.float32)
for d in ('build_core','build_core16a'):
    lib=CA.load(Path(d)/'libpvbcapi.so')
    t=time.time()
    e=T.Engine(lib,48000,vb_on=1,vb_algo=15,ramp_ms=0)
    try:
        CA.set_resultant(lib,e)
    except Exception as ex: print(d,'18 params fail',ex)
    y=np.stack([x,x],1).copy()
    for i in range(0,len(y),256):
        b=y[i:i+256]; lib.pvb_process(e.h,b.ctypes.data_as(T.FP),len(b))
    print(d,'10s in',time.time()-t, 'params', lib.pvb_param_count())
