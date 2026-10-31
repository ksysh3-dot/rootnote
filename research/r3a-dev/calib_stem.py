"""Scale of research_p1plus.render's 'stem' against the app chain at its defaults: a 100 Hz sine (-12 dBFS, 4 s).
Prints the layer's harmonic levels k = 2..6 relative to the input fundamental, from (a) the research stem and (b) the
app chain (P1 output - layer-off output, same time axis). Their difference is the offset to add to stem-based
layer/native ratios to read them at app defaults. Usage: calib_stem.py <lib>"""
import sys
import numpy as np
import research_p1plus as P
import test_engine as T
FS = 48000; t = np.arange(4 * FS) / FS
x = (10 ** (-12 / 20) * np.sin(2 * np.pi * 100 * t)).astype(np.float32); x2 = np.stack([x, x], 1)
lib = P.api(sys.argv[1])
def lv(y, f):
    seg = y[2 * FS:3 * FS]; S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fr = np.fft.rfftfreq(len(seg), 1 / FS)
    return 10 * np.log10(S[np.abs(fr - f) <= 2].sum() + 1e-30)
ref = lv(x.astype(float), 100)
r = P.render(lib, x2, FS, 0, stage_flags=0); st = r['stem'][r['latency']:].astype(float).mean(axis=1)
print('stem  k2..6 re input k1:', [round(lv(st, 100 * k) - ref, 1) for k in range(2, 7)])
tl = T.load_lib(sys.argv[1])
def run(**kw):
    e = T.Engine(tl, FS, **kw); y = e.process(x2.copy(), block=256); l = e.latency(); e.close(); return y.astype(float).mean(axis=1), l
y0, l0 = run(vb_on=0); y1, l1 = run(vb_on=1, vb_algo=6)
lay = y1[l1:] - y0[l0:][:len(y1) - l1]
print('app   k2..6 re input k1:', [round(lv(lay, 100 * k) - ref, 1) for k in range(2, 7)])
print('app dry k1 re input k1:', round(lv(y0[l0:], 100) - ref, 1))
