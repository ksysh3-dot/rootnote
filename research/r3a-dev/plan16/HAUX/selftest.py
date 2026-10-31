"""unit test of haux_lib on synthetic signals (not a result)"""
import time
import numpy as np
import haux_lib as H
fs = 48000
rng = np.random.default_rng(1)
n = np.arange(fs)
f0 = 61.3
x = sum((1.0 / k) * np.sin(2 * np.pi * k * f0 * n / fs + k) for k in range(1, 15)) + 0.05 * rng.standard_normal(fs)
# second source
x2 = x + 0.3 * np.sin(2 * np.pi * 247.0 * n / fs)
for Lms in (40, 85):
    L = H.WINLEN[Lms]; w = H.hann(L)
    seg = H.segment(x, 24000, L)
    t0 = time.time()
    for _ in range(20):
        E, Ei, a = H.comb_fit(seg, w, f0)
    dt = (time.time() - t0) / 20
    print(Lms, 'ms: a_k est', np.round(a[:8], 3), 'true', np.round([1 / k for k in range(1, 9)], 3), 'time/fit ms', round(dt * 1e3, 2))
    print('  Hsal12', round(H.hsal(E, Ei, 12), 1), 'Hsal6', round(H.hsal(E, Ei, 6), 1), 'nhit', H.nhit(E, Ei))
    for f_wrong in (f0 * 1.5, 47.0, 83.0, f0 * 0.5):
        E, Ei, a = H.comb_fit(seg, w, f_wrong)
        print('  wrong f', round(f_wrong, 1), 'Hsal12', round(H.hsal(E, Ei, 12), 1), 'Hsal6', round(H.hsal(E, Ei, 6), 1), 'nhit', H.nhit(E, Ei))
    X = H.spec_amp(seg, w)
    for off in (-60, -20, 0, 35, 80):
        fh, sc = H.comb_f0(X, f0 * 2 ** (off / 1200))
        print('  comb f0 from', round(f0 * 2 ** (off / 1200), 3), '->', round(fh, 3), 'err cent', round(1200 * np.log2(fh / f0), 2))
