"""R4 build checks. (1) Default path bit-identical to the tag library (app chain, no capture; and research render with
stage flags 0) on LOGOFF 30-50 s and a 100 Hz sine. (2) Register corner below 73 Hz: 45 Hz sine stem identical with
16777216. (3) Sines 45/100/125/150 Hz (-12 dBFS): layer k2..k6 re input k1 (research stem + 7 dB = app scale) for P1,
R4c (16777216) and R4cp (| 33554432). (4) Pluck 100 Hz every 0.5 s: k3 level 0-60 ms after each onset vs 200-400 ms
(shows the onset protection). Usage: r4_check.py <new lib> <tag lib> <logoff>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as P
import test_engine as T
new, old, song = sys.argv[1:4]; FS = 48000
x, fs = sf.read(song, always_2d=True)
xs = np.clip(resample_poly(x, 160, 147, axis=0), -1, 1)[30 * FS:50 * FS].astype(np.float32)
t = np.arange(4 * FS) / FS
sine = lambda f: np.stack([10 ** (-12 / 20) * np.sin(2 * np.pi * f * t)] * 2, 1).astype(np.float32)
def app(lib, x):
    e = T.Engine(T.load_lib(lib), FS, vb_on=1, vb_algo=6); y = e.process(x.copy(), block=256); e.close(); return y
print('1 app chain identical  LOGOFF', np.array_equal(app(new, xs), app(old, xs)), ' sine100', np.array_equal(app(new, sine(100)), app(old, sine(100))))
Ln, Lo = P.api(new), P.api(old)
st = lambda lib, x, fl: P.render(lib, x, FS, 0, stage_flags=fl)['stem']
print('1 research stem identical (flags 0)  LOGOFF', np.array_equal(st(Ln, xs, 0), st(Lo, xs, 0)))
print('2 45 Hz sine, register corner = P1:', np.array_equal(st(Ln, sine(45), 16777216), st(Ln, sine(45), 0)),
      ' LOGOFF 30-50 s max |diff| / rms', float(np.abs(st(Ln, xs, 16777216) - st(Ln, xs, 0)).max() / np.sqrt(np.mean(st(Ln, xs, 0) ** 2))))
def lv(y, f, a=2 * FS, b=3 * FS):
    seg = y[a:b]; S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fr = np.fft.rfftfreq(len(seg), 1 / FS)
    return 10 * np.log10(S[np.abs(fr - f) <= 2].sum() + 1e-30)
for f0 in (45, 100, 125, 150):
    x = sine(f0); ref = lv(x[:, 0].astype(float), f0)
    for nm, fl in (('P1', 0), ('R4c', 16777216), ('R4cp', 16777216 | 33554432)):
        r = P.render(Ln, x, FS, 0, stage_flags=fl); y = r['stem'][r['latency']:].astype(float).mean(axis=1)
        print(f'3 f0 {f0:3d} {nm:5s} k2..k6', [round(max(lv(y, f0 * k) - ref + 7, -99), 1) for k in range(2, 7)])
u = t % .5; pl = np.minimum(u / .008, 1) * np.exp(-u / .35) * np.sin(2 * np.pi * 100 * t); xp = np.stack([.25 * pl] * 2, 1).astype(np.float32)
for nm, fl in (('P1', 0), ('R4c', 16777216), ('R4cp', 16777216 | 33554432)):
    r = P.render(Ln, xp, FS, 0, stage_flags=fl); y = r['stem'][r['latency']:].astype(float).mean(axis=1)
    early = np.mean([lv(y, 300, int((n * .5 + .005) * FS), int((n * .5 + .065) * FS)) for n in range(2, 7)])
    late = np.mean([lv(y, 300, int((n * .5 + .2) * FS), int((n * .5 + .4) * FS)) for n in range(2, 7)])
    k2e = np.mean([lv(y, 200, int((n * .5 + .005) * FS), int((n * .5 + .065) * FS)) for n in range(2, 7)])
    k2l = np.mean([lv(y, 200, int((n * .5 + .2) * FS), int((n * .5 + .4) * FS)) for n in range(2, 7)])
    print(f'4 pluck100 {nm:5s} k3-k2 early (5-65 ms) {early - k2e:+.1f} dB, late (200-400 ms) {late - k2l:+.1f} dB')
