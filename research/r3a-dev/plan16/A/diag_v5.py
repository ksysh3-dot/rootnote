"""Information: where do the V5a drops of R2/R3 (T60 36-48 s) sit?  (V5a is the only condition on which R3 fails.)
Reimplements metrics.v5a with per-bin output, from the cached ladder layers."""
import sys, pickle, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import metrics as MT, rows as R
import ladder as Ld

y3s = pickle.load(open(Ld.OUTD / 'cache' / 'ladder_y3.pkl', 'rb'))
segs, rf = Ld.segments('t60_36_48')
bounds = np.array(sorted({s['s'] for s in segs} | {s['e'] for s in segs}))
S_ = MT.v5_setup(); B, K, i0 = S_['B'], S_['K'], S_['i0']
idx, tcen = S_['idx'], S_['tcen']
out = {}
for rn in ('P1', 'R0', 'R1', 'R2', 'R3', 'R2s'):
    y = R.up48(y3s[('t60_36_48', rn)]); n = int(12.3 * FS); y = np.pad(y, (0, max(0, n - len(y))))[:n]
    lay = MT.X.band_fft(y[:min(len(y), 12 * FS + 1000)], 150, 600)
    lay = np.pad(lay, (0, max(0, i0 + K * B - len(lay))))
    el = np.array([np.sum(lay[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    ratio = 10 * np.log10(el + 1e-20) - S_['es_db']
    drops = []
    for i in idx:
        m = idx[np.abs(tcen[idx] - tcen[i]) <= .25]
        if ratio[i] < np.median(ratio[m]) - 6:
            drops.append(i)
    drops = np.array(drops, int)
    # bin centre in excerpt time: bin k covers the layer at (i0 + k B)/FS ... + B/FS ; the v5 'tcen' is song-time-relative (39 + ...) -> excerpt time = 3 + tcen_rel
    t_ex = 3.0 + tcen[drops]
    dist = np.array([np.min(np.abs(bounds - t)) for t in t_ex]) if len(drops) else np.array([])
    out[rn] = dict(n=int(len(idx)), drops=int(len(drops)), within50ms_of_boundary=int((dist < 0.05).sum()) if len(dist) else 0,
                   median_drop_ratio_db=float(np.median(ratio[drops] - np.array([np.median(ratio[idx[np.abs(tcen[idx] - tcen[i]) <= .25]]) for i in drops]))) if len(drops) else None)
print(json.dumps(out, indent=1))
json.dump(out, open(Ld.OUTD / 'diag_v5.json', 'w'), indent=1)
