"""R4-L checks (app chain at defaults, StageCapture attached when flags are set).
(1) New build vs the R4 v2 build: flags off and R4c (16777216) bit-identical on LOGOFF 40-48 s and Track00040 40-48 s.
(2) R4-L (16777216|67108864) on a 45 Hz sine equals P1; on LOGOFF and Track00040 the change re P1 (max |diff| / rms).
(3) Sines 60/80/100/125/150/200 Hz at -12 dBFS: output k1-k4 levels (dB re input) for P1, R4c, R4-L 6 / 12 dB.
Usage: r4l_check.py <new lib> <r4b lib> <logoff> <track00040 mix>"""
import ctypes as C, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
FS = 48000
Ln, Lo = RP.api(sys.argv[1]), RP.api(sys.argv[2])
Ln.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
def load(p, t0):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    x = resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x
    return np.clip(x[int(t0 * FS):int((t0 + 8) * FS)], -1, 1).astype(np.float32)
def run(lib, x, flags=0, level=None):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6)
    if level is not None: assert lib.pvb_set_r4_level(e.h, level) == 1
    cap = StageCapture(lib, e.h, flags, int(len(x) / FS * 3000) + 16) if flags else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[lat:].astype(float)
songs = {'LOGOFF': load(sys.argv[3], 40.), 'Track00040': load(sys.argv[4], 40.)}
for nm, x in songs.items():
    for fl in (0, 16777216):
        print(f'1 {nm} flags {fl}: new == r4b', np.array_equal(run(Ln, x, fl), run(Lo, x, fl)))
def sine(f, dur=4.):
    t = np.arange(int(dur * FS)) / FS; s = (10 ** (-12 / 20) * np.sin(2 * np.pi * f * t)).astype(np.float32)
    return np.stack([s, s], 1)
RL = 16777216 | 67108864
print('2 45 Hz sine R4-L == P1', np.array_equal(run(Ln, sine(45), RL), run(Ln, sine(45), 0)))
for nm, x in songs.items():
    p = run(Ln, x); r = run(Ln, x, RL)
    print(f'2 {nm} R4-L 6 dB vs P1: max|diff|/rms', round(float(np.abs(r - p).max() / np.sqrt(np.mean(p ** 2))), 4))
def harm(y, f):
    z = y.mean(axis=1)[FS:]; t = np.arange(len(z)) / FS
    return [20 * np.log10(2 * abs(np.mean(z * np.exp(-2j * np.pi * k * f * t))) / 10 ** (-12 / 20) + 1e-12) for k in (1, 2, 3, 4)]
for f in (60, 80, 100, 125, 150, 200):
    row = {nm: [round(v, 1) for v in harm(run(Ln, sine(f), fl, lv), f)] for nm, fl, lv in
           (('P1', 0, None), ('R4c', 16777216, None), ('R4L6', RL, 6.), ('R4L12', RL, 12.))}
    print(f'3 {f} Hz k1..k4 dB re input', row)
