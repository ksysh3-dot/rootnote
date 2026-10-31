"""Timing calibration by an amplitude PULSE (x3 for 24 ms, centred at 2.000 s) on an established 100 Hz tone: the LS amplitude A(h) of an
established voice must bump when the analysis window covers the pulse. Compare the bump's centre in the two hop time bases, and the
bump of the layer in latency-aligned output time (dry path alignment verified with a click: delay == reported latency)."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
from scipy.ndimage import uniform_filter1d
FS = X.FS
cand = X.open_lib(X.CAND)
t = np.arange(int(4.0 * FS)) / FS
tp, wp = 2.0, 0.024
pulse = ((t >= tp - wp / 2) & (t < tp + wp / 2)).astype(float)
amp = (1 + 2 * pulse) * 0.1
x = amp * (np.sin(2 * np.pi * 100 * t) + .5 * np.sin(2 * np.pi * 200 * t) + .18 * np.sin(2 * np.pi * 300 * t)) * np.minimum(t / .5, 1)
for cfg in ('A', 'B'):
    r0 = X.render(cand, x, 15, 0.0, out_db=-18.0, cfg=X.CFG[cfg], trace=True)
    rd = X.render(cand, x, 15, -120.0, out_db=-18.0, cfg=X.CFG[cfg])
    lay = X.layer(r0, rd)
    env = np.sqrt(np.maximum(uniform_filter1d(lay ** 2, int(.010 * FS), mode='nearest'), 0))
    dry = X.mono_al(rd); denv = np.sqrt(np.maximum(uniform_filter1d(dry ** 2, int(.010 * FS), mode='nearest'), 0))
    sl = slice(int(1.9 * FS), int(2.2 * FS))
    cen = lambda e: (np.arange(len(e))[sl] / FS * e[sl] ** 2).sum() / (e[sl] ** 2).sum()
    tr = r0['trace']; on = (tr[:, X.F_STATE] == X.ON) & (np.abs(tr[:, X.F_FTR] - 100) < 5)
    hh = {}
    for h, a in zip(tr[on, X.F_HOP], tr[on, X.F_A]):
        hh[h] = max(hh.get(h, 0), a)
    hs = np.array(sorted(hh)); A = np.array([hh[h] for h in hs]); tc1 = (hs - 382) / 3000.0
    base = np.median(A[(tc1 > 1.5) & (tc1 < 1.9)])
    m = (tc1 > 1.9) & (tc1 < 2.3)
    w = np.maximum(A[m] - base, 0) ** 2
    c1 = (tc1[m] * w).sum() / w.sum()
    pk = tc1[m][np.argmax(A[m])]
    # excess-energy centre of the layer and of the dry envelope relative to their own baselines
    def excess_centre(e):
        b = np.median(e[int(1.5 * FS):int(1.9 * FS)])
        ee = np.maximum(e[sl] - b, 0) ** 2
        return (np.arange(len(e))[sl] / FS * ee).sum() / ee.sum()
    print(f'config {cfg}: pulse centre 2.000 s, width 24 ms')
    print(f'   dry (aligned) excess-energy centre {1000*(excess_centre(denv)-tp):+7.2f} ms   layer (aligned) {1000*(excess_centre(env)-tp):+7.2f} ms')
    print(f'   A bump centre: conv1 (hop-382)/3000 {1000*(c1-tp):+7.2f} ms ; conv2 (+1359/48000) {1000*(c1+1359/48000-tp):+7.2f} ms ; peak hop conv1 {1000*(pk-tp):+.1f} / conv2 {1000*(pk+1359/48000-tp):+.1f} ms')
    print('   A(h) around the pulse: ' + ', '.join(f'{1000*(tc1[i]-tp):+.1f}:{A[i]/base:.2f}' for i in np.flatnonzero((tc1 > 1.95) & (tc1 < 2.07))))
