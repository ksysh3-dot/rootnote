import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import time
t0 = time.time()
sig = Sig('Track00040')
print('load', time.time() - t0, sig.nhop, len(sig.bh), len(sig.core_tc), sig.core_tc[:3], sig.tc1[:3])
d = sig.core_d
for k in ('voice', 'track', 'state', 'coast', 'ftr', 'fosc', 'A', 'c', 'sig', 'snr', 'sub', 'a2', 'a3'):
    a = d[k]; print(k, a.shape, np.unique(a)[:10] if k in ('voice', 'state', 'coast', 'sub', 'track') else (a.min(), a.max()))
print(sig.ts.shape)
import research_core_xcheck as X
print(X.F_HOP, X.F_VOICE, X.F_STATE, X.F_COAST, X.F_FTR, X.F_FOSC, X.F_A, X.F_C, X.F_SIG, X.F_SNR, X.F_SUB, X.F_A2, X.F_A3, X.F_TRACK)
print(X.ON, X.REL, X.CAND_ if hasattr(X, 'CAND_') else None)
st = d['state']
print({s: int((st == s).sum()) for s in range(5)})
# example hop rows
h = 600
print(d['state'][h], d['voice'][h], d['fosc'][h], d['A'][h], d['c'][h], d['coast'][h])
print(sig.ts[h][:, :8])
import inspect
print(inspect.getsource(X.hop_time))
