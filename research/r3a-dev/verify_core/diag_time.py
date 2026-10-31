"""Which time base is right for the voice trace: tc = (hop-382)/3000 s or the harmonic-trace header tc (= that + 1359/48000 s)?
Calibrate against the physical layer output (latency-aligned, sample index = input time): the trace amplitude A(h) is what the
oscillator is scaled with in the interval ending at C_h, so the layer envelope must rise when A rises, in the same time base."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
from scipy.ndimage import uniform_filter1d
FS = X.FS
cand = X.open_lib(X.CAND)
t = np.arange(int(3.5 * FS)) / FS
x = np.zeros_like(t)
t0 = 0.5; m = t >= t0; u = t[m] - t0
ph = lambda f: 2 * np.pi * f * u
x[m] = (np.sin(ph(100)) + .5 * np.sin(ph(200)) + .18 * np.sin(ph(300))) * np.minimum(u / .008, 1) * 0.25 / 1.4
for cfg in ('A', 'B'):
    r0 = X.render(cand, x, 15, 0.0, out_db=-18.0, cfg=X.CFG[cfg], trace=True)
    rd = X.render(cand, x, 15, -120.0, out_db=-18.0, cfg=X.CFG[cfg])
    lay = X.layer(r0, rd)
    env = np.sqrt(uniform_filter1d(lay ** 2, int(.005 * FS), mode='nearest'))
    st = env[int(2.0 * FS):int(2.5 * FS)].mean()
    def cross(frac):
        k = np.flatnonzero((np.arange(len(env)) / FS > 0.45) & (env >= frac * st))[0]
        return k / FS
    tr = r0['trace']; on = (tr[:, X.F_STATE] == X.ON) & (np.abs(tr[:, X.F_FTR] - 100) < 5)
    hh = {}
    for h, a in zip(tr[on, X.F_HOP], tr[on, X.F_A]):
        hh[h] = max(hh.get(h, 0), a)
    hs = np.array(sorted(hh)); A = np.array([hh[h] for h in hs])
    A_st = np.median(A[(hs - 382) / 3000 > 2.0][:90])
    print(f'--- config {cfg}: lat {r0["lat"]}  layer steady {st:.4g}; A steady {A_st:.4g}')
    for frac in (.1, .5, .9):
        tl = cross(frac)
        k = np.flatnonzero(A >= frac * A_st)[0]
        t_a1 = (hs[k] - 382) / 3000.0; t_a2 = t_a1 + 1359 / 48000.0
        print(f'  {int(frac*100):2d}%: layer(aligned out) {1000*(tl-t0):7.2f} ms after onset | A rise, conv1 (hop-382)/3000: {1000*(t_a1-t0):7.2f} ms | conv2 (+1359/48000): {1000*(t_a2-t0):7.2f} ms')
    # input onset in the same units: 50 % of the tone envelope at 4 ms after t0
    print('  (input attack: linear 8 ms, so the input is at 50 % at 4 ms)')
