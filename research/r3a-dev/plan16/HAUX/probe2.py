"""orientation only: counts of voice-hops per song and class (no feature, no metric)"""
import sys, time
import numpy as np
import kcommon as K
from kcommon import *
tot = 0
for key in SONGS:
    t0 = time.time()
    ctx = K.SongCtx(key, probe_nobass=False)
    n = np.zeros((3, 8), int)   # cls x (comp: 0,1,2, causes 3..7)
    nh = 0
    for v in ctx.voices:
        if not v['ok']:
            continue
        for i in range(len(v['T'])):
            if v['A'][i] <= 0:
                continue
            j = int(np.clip(round(v['T'][i] * FSC) - v['i0'], 0, len(v['comp']) - 1))
            n[v['cls'], int(v['comp'][j])] += 1; nh += 1
    tot += nh
    print(key, 'nobass' if ctx.nobass else 'bass', 'voices', len(ctx.voices), 'voice-hops(amp>0)', nh, 'hops', len(ctx.tc), round(time.time() - t0, 1))
    print('  cls x comp', n.tolist())
print('total', tot)
