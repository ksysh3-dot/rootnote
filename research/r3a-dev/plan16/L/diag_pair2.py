"""Plan16 L: pair 2 (Track00025, 21-30 s) listener note 'late low notes come ~0.5 s early vs the other side'.
Prints a 100 ms timeline of the low band (40-250 Hz) for core v1.5, P1, their difference, and core silent-voice wrong energy.
Run from tools/pvb-harness with PYTHONPATH=.:study"""
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt
import test_engine as T
import research_core_api as CA
import research_core_xcheck as X

FS = 48000
L = Path('/home/ksysh/r3a-dev/plan16/L')
lib = CA.load(Path('build_core/libpvbcapi.so').resolve())
Z = np.load(L / 'sil_series.npz')


def render(x, algo):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    try:
        if algo == 15:
            CA.set_resultant(lib, e)
        y = np.ascontiguousarray(np.stack([x, x], 1) if x.ndim == 1 else x, np.float32).copy()
        for i in range(0, len(y), 256):
            b = y[i:i + 256]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        lat = int(lib.pvb_latency(e.h))
    finally:
        e.close()
    return y[lat:lat + 30 * FS].astype(np.float64).mean(1)


key = 'Track00025'
x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
xin = (x.mean(1) if x.ndim == 2 else x)[:30 * FS].astype(np.float64)
c, p = render(x, 15), render(x, 6)
sos = butter(4, [40, 250], btype='band', fs=FS, output='sos')
sos_in = butter(4, [30, 120], btype='band', fs=FS, output='sos')
lc, lp, ld, li = (sosfiltfilt(sos, c), sosfiltfilt(sos, p), sosfiltfilt(sos, c - p), sosfiltfilt(sos_in, xin))
ysil = Z[key + '_ysil']


def db(v):
    return 20 * np.log10(max(v, 1e-9))


fr = int(0.1 * FS)
ref = np.sqrt(np.mean(lp[21 * FS:30 * FS] ** 2))
print('t_song  t_inA | in30-120 | P1 40-250 | core 40-250 | core-P1 | core sil-voice (re P1 band rms)')
for k in range(int(21 / 0.1), int(30 / 0.1)):
    s = k * fr
    r = lambda a: np.sqrt(np.mean(a[s:s + fr] ** 2))
    zs = ysil[int(k * 0.1 * 3000):int((k + 1) * 0.1 * 3000)]
    zv = np.sqrt(np.mean(zs ** 2)) if len(zs) else 0.0
    print(f'{k*0.1:5.1f} {k*0.1-21:5.1f} | {db(r(li)/ref):6.1f} | {db(r(lp)/ref):6.1f} | {db(r(lc)/ref):6.1f} | {db(r(ld)/ref):6.1f} | {db(zv):7.1f}')
