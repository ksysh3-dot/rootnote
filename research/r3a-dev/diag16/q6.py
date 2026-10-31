"""Q6: is anything of the P1 render state frozen while algorithm 15 runs and replayed on the switch back to 6?  Empirical companion to the code reading:
compare the last segment of 6->15->6 with 6->14->6, 6->13->6, 6->12->6, 6->11->6 (all switches go through Engine::vbApply -> setAlpha2Profile -> VbHpv::reset())."""
import numpy as np
import common16 as C
import research_core_xcheck as X

FS = X.FS
cand = X.open_lib(X.CAND)
xs = X.read_excerpt(X.SLAKH / 'Track00060' / 'mix.flac', 30.0, 5.0)
xs = xs[:, 0] if xs.ndim == 2 else xs
res = {}
for mid in (15, 14, 13, 12, 11):
    r = X.render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, mid, 6])
    res[mid] = r['y'].astype(np.float64)
rc = X.render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0)['y'].astype(np.float64)
n = len(xs) // 3
print('segments: [0,n) algo 6, [n,2n) algo mid, [2n,3n) algo 6 again; n =', n, 'samples =', n / FS, 's')
for mid in (14, 13, 12, 11):
    seg = np.abs(res[15][2 * n:] - res[mid][2 * n:])
    print(f'last segment of 6-15-6 vs 6-{mid}-6: max|diff| = {seg.max():.3g}')
seg = np.abs(res[15][2 * n:] - rc[2 * n:])
print(f'last segment of 6-15-6 vs continuous 6: max|diff| = {seg.max():.3g}; by time after the switch back (s): ' +
      ', '.join(f'{a}-{b}: {seg[int(a*FS):int(b*FS)].max():.2g}' for a, b in ((0, .1), (.1, .2), (.2, .5), (.5, 1.0), (1.0, 1.66))))
seg = np.abs(res[14][2 * n:] - rc[2 * n:])
print(f'last segment of 6-14-6 vs continuous 6: max|diff| = {seg.max():.3g}; by time: ' + ', '.join(f'{a}-{b}: {seg[int(a*FS):int(b*FS)].max():.2g}' for a, b in ((0, .1), (.1, .2), (.2, .5), (.5, 1.0), (1.0, 1.66))))
# 6 -> 15 -> 6 versus 6 -> 6 -> 6 with a profile re-apply is not constructible through the API; instead: a switch 6 -> 15 -> 6 with a very short 15 segment vs a long one
for parts in ([6, 15, 6, 6, 6], [6, 6, 15, 6, 6]):
    r = X.render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=parts)
    m = len(xs) // len(parts)
    k = parts.index(15)
    last = r['y'][(k + 1) * m:(k + 2) * m].astype(np.float64)
    print(f'seq {parts}: first segment after 15: max|diff| vs continuous 6 = {np.abs(last - rc[(k+1)*m:(k+2)*m]).max():.3g}')
