"""R4 zero-code probe: the app chain's layer (P1 output - layer-off output) for sines at 45/55/100/125/150 Hz
(-12 dBFS), at the app defaults and with developer values: sustained upper roll-off offset (P_D_ROLLOFF_DB_OCT, model
24 dB/oct above 220 Hz; -12 -> 12 dB/oct, -24 -> flat) and the output low-pass edge (P_D_OUT_HI_HZ 600 / 800).
Prints the layer's k = 2..8 levels re the input fundamental. Usage: probe_rolloff.py <lib>"""
import sys
import numpy as np
import test_engine as T
T.P.update(dict(DEV_ON=33, D_OUT_HI_HZ=37, D_ROLLOFF_DB_OCT=42))
FS = 48000; t = np.arange(4 * FS) / FS; lib = T.load_lib(sys.argv[1])
def lv(y, f):
    seg = y[2 * FS:3 * FS]; S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fr = np.fft.rfftfreq(len(seg), 1 / FS)
    return 10 * np.log10(S[np.abs(fr - f) <= 2].sum() + 1e-30)
def run(x2, **kw):
    e = T.Engine(lib, FS, **kw); y = e.process(x2.copy(), block=256); l = e.latency(); e.close(); return y.astype(float).mean(axis=1), l
VAR = [('default', dict()), ('dev on, same', dict(dev_on=1)), ('12 dB/oct', dict(dev_on=1, d_rolloff_db_oct=-12)),
       ('flat', dict(dev_on=1, d_rolloff_db_oct=-24)), ('12 dB/oct + LP 800', dict(dev_on=1, d_rolloff_db_oct=-12, d_out_hi_hz=800))]
for f0 in (45, 55, 100, 125, 150):
    x = (10 ** (-12 / 20) * np.sin(2 * np.pi * f0 * t)).astype(np.float32); x2 = np.stack([x, x], 1); ref = lv(x.astype(float), f0)
    y0, l0 = run(x2, vb_on=0)
    print(f'== f0 {f0} Hz: layer k2..k8 dB re input k1 (Hz: {[f0 * k for k in range(2, 9)]})')
    for name, kw in VAR:
        y1, l1 = run(x2, vb_on=1, vb_algo=6, **kw); lay = y1[l1:] - y0[l0:][:len(y1) - l1]
        print(f'  {name:20s}', [round(max(lv(lay, f0 * k) - ref, -99), 1) for k in range(2, 9)])
