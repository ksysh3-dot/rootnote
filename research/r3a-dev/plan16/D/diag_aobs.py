"""INFO diagnostic (not part of any decision): noise of the causal A_obs (32-sample LS) on a steady tone, vs longer windows."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import det as DT
from dcommon import *
for key in ('steady8', 'gapbkp', 'bkp_0'):
    sig = Sig(key); S = DT.SongData(sig)
    r = max(S.runs, key=lambda r: len(r['hs']))
    on = np.flatnonzero(r['st'] == 2)[40:-5]
    j = np.rint(r['jj']).astype(int); f = r['f']
    res = {}
    for N in (32, 64, 96):
        a2, _ = DT.ls_feat(S.x, j[on], f[on], N)
        d = DT.DB(np.sqrt(a2))
        res[N] = (round(float(np.std(d - np.median(d))), 2), round(float(np.percentile(d, 5) - np.median(d)), 2))
    trace = DT.DB(r['amp'][on])
    print(key, 'longest run hops', len(r['hs']), 'f median', round(float(np.median(f[on])), 1), 'std / p5-median of A_obs dB by window N:', res, '| trace A std dB', round(float(np.std(trace - np.median(trace))), 2))
