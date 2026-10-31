import sys, time
import numpy as np
import kcommon as K
from kcommon import *
t0 = time.time()
ctx = K.SongCtx('Track00060', probe_nobass=False)
print('init', time.time() - t0, len(ctx.voices), ctx.dur, ctx.n)
v = ctx.voices[0]
print({k: (type(x).__name__, getattr(x, 'shape', None)) for k, x in v.items()})
print('tc0', ctx.tc[:3], 'LAG', LAG, 'HOP_S', HOP_S)
x = DATA.audio('Track00060'); print(x.shape, x.dtype, np.abs(x).max())
sig = ctx.sig
print(sig.core_tc[:3], sig.core_hop[:3], len(sig.core_tc))
cls = [vv.get('cls') for vv in ctx.voices]
print('cls counts', np.bincount(cls))
import collections
print(collections.Counter(len(vv['T']) for vv in ctx.voices).most_common(5))
