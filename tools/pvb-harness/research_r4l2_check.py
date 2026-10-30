"""R4-L v2 (StageReentrySlow) checks. (1) Bit identity with the R4-L build: flags off, and R4c+R4-L 6 dB without the new
flag, on Track00060 39-47 s and the bare 100 Hz bass. (2) The bare bass: 150-600 Hz and 400 Hz cycle peak times and the
300 Hz layer re the input partial over the note, P1 / L6 / L6v2 (tau 250). (3) The 150-600 Hz gain re P1 (whole
excerpt, phone model) on the bare bass and Track00060. Usage: r4l2_check.py <new lib> <r4l lib> <T60 mix>"""
import ctypes as C, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert, resample_poly, firwin2, fftconvolve
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000
def api(p):
    lib = RP.api(p); lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
    if hasattr(lib, 'pvb_set_r4_reentry'): lib.pvb_set_r4_reentry.argtypes = [C.c_void_p, C.c_double]
    return lib
NEW, OLD = api(sys.argv[1]), api(sys.argv[2])
def render(lib, x, flags=0, level=6., tau=None, vb=1):
    e = T.Engine(lib, FS, vb_on=vb, vb_algo=6); cap = None
    if flags:
        assert lib.pvb_set_r4_level(e.h, level) == 1
        if tau is not None: assert lib.pvb_set_r4_reentry(e.h, tau) == 1
        cap = StageCapture(lib, e.h, flags, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:].mean(axis=1)
t = np.arange(9 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
xb = np.ascontiguousarray(np.stack([bass, bass], 1), np.float32)
m, fs = sf.read(sys.argv[3], always_2d=True)
if m.shape[1] == 1: m = np.repeat(m, 2, 1)
m = resample_poly(m, 160, 147, axis=0) if fs == 44100 else m
xt = np.clip(m[37 * FS:47 * FS], -1, 1).astype(np.float32)
R4L, V2 = 16777216 | 67108864, 16777216 | 67108864 | 134217728
print('== bit identity vs R4-L build')
for nm, x in (('T60', xt), ('bass', xb)):
    for fl in (0, R4L):
        a, b = render(NEW, x, fl), render(OLD, x, fl)
        print(f'  {nm} flags {fl}: max |diff| {np.abs(a - b).max():.3g}')
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
bb = butter(4, [150, 600], btype='band', fs=FS, output='sos')
E = lambda y: np.sum(sosfiltfilt(bb, y) ** 2)
Cy = FS // 2
def cyc(y, band):
    z = sosfiltfilt(butter(4, band, btype='band', fs=FS, output='sos'), y)
    c = (np.abs(hilbert(z)) ** 2)[:16 * Cy].reshape(16, Cy)[1:].mean(axis=0); return np.convolve(c, np.ones(48) / 48, 'same')[::48]
print('== bare bass timing')
dry = render(NEW, xb, vb=0)[:8 * FS]
S = {'p1': render(NEW, xb)[:8 * FS], 'l6': render(NEW, xb, R4L)[:8 * FS], 'v2': render(NEW, xb, V2, tau=250.)[:8 * FS]}
for v, y in S.items():
    c1, c4 = cyc(y, (150, 600)), cyc(y, (385, 415))
    lay = cyc(y - dry, (285, 315)); inp = cyc(dry, (285, 315))
    rel = [10 * np.log10(lay[i:i + 20].sum() / inp[i:i + 20].sum()) for i in range(0, 500, 20)]
    print(f'  {v}: 150-600 peak {np.argmax(c1[:450])} ms, 400 Hz peak {np.argmax(c4[:450])} ms | 300 Hz layer re input per 20 ms: ' +
          ' '.join(f'{r:+.0f}' for r in rel))
print('== 150-600 Hz gain re P1 after the phone model')
for nm, x in (('bass', xb), ('T60', xt)):
    p = phone(render(NEW, x)); l6 = phone(render(NEW, x, R4L)); v2 = phone(render(NEW, x, V2, tau=250.))
    print(f'  {nm}: L6 {10 * np.log10(E(l6) / E(p)):+.2f} dB, v2 {10 * np.log10(E(v2) / E(p)):+.2f} dB')
