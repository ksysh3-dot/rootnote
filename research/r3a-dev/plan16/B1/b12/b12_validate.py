import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12model import *
np.set_printoptions(linewidth=200, precision=4, suppress=True)
tr = {k: v.astype(float) for k, v in np.load(TMP / 'app_v15_trace.npz').items()}
st = tr['state']; A = tr['A']; c = tr['c']; sg = tr['sigma']; fo = tr['f_osc']
act = (st >= 1)
base = A * c * sg
m = act & (base > 1e-6) & (fo > 0)
print('active slot-hops', m.sum(), 'state counts', [(s, int((st == s).sum())) for s in range(4)])
# validate a_2, a_3 vs the trace
for gentle, blend in ((False, 0), (True, 0), (True, 1)):
    a = amplitudes(fo, base, gentle, blend)
    for kk, key in ((0, 'a_2'), (1, 'a_3')):
        t = tr[key][m]; p = a[kk][m]
        sel = (t > 1e-6)
        print(f'gentle={gentle} blend={blend} {key}: n={sel.sum()}  median ratio model/trace {np.median(p[sel] / t[sel]):.4f}  p5/p95 {np.percentile(p[sel] / t[sel], 5):.3f}/{np.percentile(p[sel] / t[sel], 95):.3f}  zero-trace but model>0: {(p[~sel] > 1e-6).sum()}')
# split by k f > 220
a = amplitudes(fo, base, True, 0)
for kk, key in ((0, 'a_2'), (1, 'a_3')):
    t = tr[key]; p = a[kk]; sel = m & (t > 1e-6)
    for lo, hi in ((0, 220), (220, 450), (450, 800)):
        s2 = sel & ((kk + 2) * fo > lo) & ((kk + 2) * fo <= hi)
        if s2.sum(): print(key, f'k f in ({lo},{hi}]: n={s2.sum()} median model/trace blend0 {np.median(p[s2] / t[s2]):.4f}')
a1 = amplitudes(fo, base, True, 1)
for kk, key in ((0, 'a_2'), (1, 'a_3')):
    t = tr[key]; p = a1[kk]; sel = m & (t > 1e-6)
    for lo, hi in ((220, 450), (450, 800)):
        s2 = sel & ((kk + 2) * fo > lo) & ((kk + 2) * fo <= hi)
        if s2.sum(): print(key, f'k f in ({lo},{hi}]: n={s2.sum()} median model/trace blend1 {np.median(p[s2] / t[s2]):.4f}')
