import sys
sys.path.insert(0,'/home/ksysh/r3a-dev/plan16/D')
import dsig
from dcommon import *
import time
t0=time.time()
sig=Sig('Track00025')
print('sig',time.time()-t0)
print(X.F_FTR,X.F_FOSC,X.F_PROM,X.F_TRACK,X.F_NP)
print(sig.core_raw.shape, sig.core_hop[:5], sig.core_tc[:3], sig.bh.shape, sig.det.shape, sig.nhop)
x=DATA.audio('Track00025'); print(x.shape,x.dtype)
print([k for k in dir(X) if k.startswith('F_')])
d=sig.core_d; print(d.keys())
cv=R.voices_core(sig); print(len(cv), cv[0].keys())
print(LAG, I_MIN, FSC, HOP_S)
import numpy as np
print(sig.core_hop[100:105]-sig.core_hop[99:104], sig.tc1[:3])
print(np.unique(d['state']))
v=cv[100]; print(v['t'][:4], v['amp'][:6], v['state'][:6])
