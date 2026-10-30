"""After R4-L v2: what still modulates the boosted layer? Harmonic trace, P1 (the gate is the same), per input: for the
track nearest 100 Hz, per note (0.5 s): hops with a failed fit (reason 8), number of fail/pass switches, fade minimum
and the hops with fade < 0.5. Inputs: bare bass, bass + pink noise (no kick), bass + kick + pink. Then on Track00060
39-47 s: (v2 - P1) 150-600 Hz energy per 0.5 s re P1 there (the "late surge" near the end?).
Usage: gate_flicker.py <lib> <T60 mix>"""
import ctypes as C, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, resample_poly
import test_engine as T
import research_p1plus as RP
from vb_quality.stage_capture import StageCapture
FS = 48000; FIELDS, HEADER, TRACK, TRACKS, ROWS = 700, 28, 56, 12, 72
lib = RP.api(sys.argv[1])
lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]; lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]; lib.pvb_set_r4_reentry.argtypes = [C.c_void_p, C.c_double]
t = np.arange(8 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
rng = np.random.default_rng(1); w = np.fft.irfft(np.fft.rfft(rng.standard_normal(10 * FS)) / np.sqrt(np.maximum(np.fft.rfftfreq(10 * FS, 1 / FS), 20)))
pink = (.03 * w / np.sqrt(np.mean(w ** 2)))[:8 * FS]
kick = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-u / .02)) / FS)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
X = {'bare': bass, 'bass+pink': bass + pink, 'bass+kick+pink': bass + .2 * kick + pink}
for nm, x in X.items():
    x = np.ascontiguousarray(np.stack([x, x], 1), np.float32)
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6); lib.pvb_set_diagnostic_capture(e.h, 1)
    rows = []; buf = np.empty(ROWS * FIELDS, np.float32)
    for off in range(0, len(x), 256):
        b = x[off:off + 256].copy(); lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
        if n > 0: d = buf[:n * FIELDS].reshape(n, FIELDS).copy(); d[:, 0] += off; rows.append(d)
    e.close(); R = np.vstack(rows); ts = R[:, HEADER:].reshape(-1, TRACKS, TRACK)
    fails, sw, fmin, low = [], [], [], []
    for c in range(2, 16):
        sel = np.flatnonzero((R[:, 0] >= c * FS // 2) & (R[:, 0] < (c + 1) * FS // 2))
        fit, fade = [], []
        for i in sel:
            v = np.flatnonzero((ts[i, :, 1] > 0) & (np.abs(ts[i, :, 2] - 100) < 5))
            if len(v): j = v[0]; fit.append((int(ts[i, j, 10]) & 8) > 0); fade.append(ts[i, j, 7])
            else: fit.append(True); fade.append(0.)
        fit = np.array(fit); fade = np.array(fade)
        fails.append(fit.sum()); sw.append(int(np.sum(fit[1:] != fit[:-1]))); fmin.append(fade.min()); low.append(int(np.sum(fade < .5)))
    print(f'{nm:15s} per note (14 notes): fail hops {np.mean(fails):5.1f} (min {min(fails)}, max {max(fails)}) | fail/pass switches '
          f'{np.mean(sw):4.1f} (max {max(sw)}) | fade<0.5 hops {np.mean(low):5.1f} (max {max(low)}) | of {len(sel)} hops')
m, fs = sf.read(sys.argv[2], always_2d=True)
if m.shape[1] == 1: m = np.repeat(m, 2, 1)
m = np.clip(resample_poly(m, 160, 147, axis=0) if fs == 44100 else m, -1, 1).astype(np.float32)[36 * FS:48 * FS]
def render(x, v2=False):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
    if v2:
        assert lib.pvb_set_r4_level(e.h, 6.) == 1 and lib.pvb_set_r4_reentry(e.h, 250.) == 1
        cap = StageCapture(lib, e.h, 16777216 | 67108864 | 134217728, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat + 3 * FS:lat + 11 * FS].mean(axis=1)
p, v = render(m), render(m, True); bb = butter(4, [150, 600], btype='band', fs=FS, output='sos')
dp, dv = sosfiltfilt(bb, p), sosfiltfilt(bb, v); H = FS // 2
print('T60 39-47 s, v2 re P1 150-600 Hz per 0.5 s (dB): ' + ' '.join(f'{10 * np.log10(np.sum(dv[i:i + H] ** 2) / np.sum(dp[i:i + H] ** 2)):+.1f}' for i in range(0, 8 * FS, H)))
