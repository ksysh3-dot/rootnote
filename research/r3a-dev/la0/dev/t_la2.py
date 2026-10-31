import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import pipeline as P

for L in (0, 64, 217):
    t0 = time.time()
    p = P.compute_la(('Track00060', 'bh', L, 191))
    d = P.load_la('Track00060', 'bh', L, 191)
    res = d['res']
    n = len(res['ivs'])
    dur = np.array([(iv['j_off'] - iv['j_on']) / 3.0 for iv in res['ivs']])
    print(f'L={L}: {time.time()-t0:.1f}s chunks {len(res["chunks"])} intervals {n}  dur ms median {np.median(dur):.0f} mean {dur.mean():.0f}  ratios n={len(res["ratios"])} p95 {np.percentile(res["ratios"][:,0],95) if len(res["ratios"]) else 0:.2f}')
    W = d['W']; print('   weight right frac', d['Wr'].sum() / (d['Wr'].sum() + d['Ww'].sum()), 'label right', d['label'].mean(), 'F finite', np.isfinite(d['F']).all())
