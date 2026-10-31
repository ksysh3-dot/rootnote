import numpy as np
import research_core_xcheck as X
FS = X.FS
cand = X.open_lib(X.CAND)
xs = X.read_excerpt(X.SLAKH / 'Track00060' / 'mix.flac', 30.0, 5.0)[:, 0]
a = X.render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, 15, 6])['y'].astype(np.float64)
b = X.render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, 14, 6])['y'].astype(np.float64)
n = len(xs) // 3
d = np.abs(a - b)
for lo, hi in ((0, .02), (.02, .05), (.05, .1), (.1, .2), (.2, .5), (.5, 1.0), (1.0, 1.66)):
    print(f'6-15-6 vs 6-14-6, {lo}-{hi} s after the switch back: max|diff| {d[2*n+int(lo*FS):2*n+int(hi*FS)].max():.3g}')
print('middle segment first 20 ms after the first switch (15 vs 14 differ by design):', d[n:n + int(.02 * FS)].max())
# which sample is the first one that differs in the last segment, and in the middle segment
last = np.flatnonzero(d[2 * n:] > 0)
print('first differing sample after the switch back:', (last[0] / FS if len(last) else None), 's; last differing sample:', (last[-1] / FS if len(last) else None))
