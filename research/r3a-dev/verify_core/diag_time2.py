"""Clean timing calibration: amplitude STEP (x2) at t=2.0 s on an established steady 100 Hz tone (phase continuous). No voice birth involved.
Compare the 50 % crossing of (i) A(h) in the two candidate hop time bases, (ii) the layer amplitude envelope (latency-aligned output),
(iii) the dry path (the engine's dry output at vb_level -120), which must cross at exactly 2.000 s if the alignment is right."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
from scipy.ndimage import uniform_filter1d
FS = X.FS
cand = X.open_lib(X.CAND); ref = X.open_lib(X.REF)
t = np.arange(int(4.0 * FS)) / FS
amp = np.where(t < 2.0, 1.0, 2.0) * 0.1
x = amp * (np.sin(2 * np.pi * 100 * t) + .5 * np.sin(2 * np.pi * 200 * t) + .18 * np.sin(2 * np.pi * 300 * t)) * np.minimum(t / .5, 1)
for cfg in ('A', 'B'):
    r0 = X.render(cand, x, 15, 0.0, out_db=-18.0, cfg=X.CFG[cfg], trace=True)
    rd = X.render(cand, x, 15, -120.0, out_db=-18.0, cfg=X.CFG[cfg])
    lay = X.layer(r0, rd)
    env = np.sqrt(np.maximum(uniform_filter1d(lay ** 2, int(.010 * FS), mode='nearest'), 0))
    dry = X.mono_al(rd); denv = np.sqrt(np.maximum(uniform_filter1d(dry ** 2, int(.010 * FS), mode='nearest'), 0))
    def cross(e, lo_win, hi_win):
        lo = e[int(lo_win[0] * FS):int(lo_win[1] * FS)].mean(); hi = e[int(hi_win[0] * FS):int(hi_win[1] * FS)].mean()
        mid = (lo + hi) / 2
        k = np.flatnonzero((np.arange(len(e)) / FS > 1.9) & (e >= mid))[0]
        return k / FS, lo, hi
    tl, lo, hi = cross(env, (1.5, 1.9), (2.6, 3.0))
    td, dlo, dhi = cross(denv, (1.5, 1.9), (2.6, 3.0))
    tr = r0['trace']; on = (tr[:, X.F_STATE] == X.ON) & (np.abs(tr[:, X.F_FTR] - 100) < 5)
    hh = {}
    for h, a in zip(tr[on, X.F_HOP], tr[on, X.F_A]):
        hh[h] = max(hh.get(h, 0), a)
    hs = np.array(sorted(hh)); A = np.array([hh[h] for h in hs])
    tcA = (hs - 382) / 3000.0
    alo = A[(tcA > 1.5) & (tcA < 1.9)].mean(); ahi = A[(tcA > 2.7) & (tcA < 3.1)].mean(); amid = (alo + ahi) / 2
    k = np.flatnonzero((tcA > 1.9) & (A >= amid))[0]
    t1 = tcA[k]; t2 = t1 + 1359 / 48000.0
    print(f'config {cfg}: layer step ratio {hi/lo:.2f} (expect 2); A ratio {ahi/alo:.2f}')
    print(f'   dry path crosses 50 % at {1000*(td-2.0):+7.2f} ms re 2.000 s  (alignment check; envelope 4 ms boxcar)')
    print(f'   layer (aligned output) crosses 50 % at {1000*(tl-2.0):+7.2f} ms')
    print(f'   A crosses 50 %: conv1 (hop-382)/3000 -> {1000*(t1-2.0):+7.2f} ms ; conv2 (+1359/48000, harmonic header) -> {1000*(t2-2.0):+7.2f} ms')
    # Also the A series around the step in both conventions (first hops where A moves)
    i0 = np.flatnonzero(tcA > 1.97)[0]
    print('   A around the step (conv1 time re 2.0 s ms : A/alo):', ', '.join(f'{1000*(tcA[i]-2.0):+.1f}:{A[i]/alo:.2f}' for i in range(i0, i0 + 14)))
