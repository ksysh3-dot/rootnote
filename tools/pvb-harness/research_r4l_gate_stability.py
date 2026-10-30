"""Would a hold through fit failures (direction (ma)) keep the right pitch? Harmonic trace, P1. For every track between
73.3 and 220 Hz (the R4-L range), over the hops where its fit fails (reason 8): share of those hops with missing > 0,
and |f - f at the track's last passing hop| / f (median, p90, max; share within 1 % and 2 %), plus the share of failed
hops among all hops of such tracks (amplitude-weighted). Inputs: bare bass, bass + pink, Track00060 39-47 s.
Also, on the bare bass, the 300 Hz layer re the input partial for R4c alone (corner only, no level).
Usage: gate_stability.py <lib> <T60 mix>"""
import ctypes as C, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert, resample_poly
import test_engine as T
import research_p1plus as RP
from vb_quality.stage_capture import StageCapture
FS = 48000; FIELDS, HEADER, TRACK, TRACKS, ROWS = 700, 28, 56, 12, 72
lib = RP.api(sys.argv[1])
lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]; lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]
t = np.arange(8 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
rng = np.random.default_rng(1); w = np.fft.irfft(np.fft.rfft(rng.standard_normal(10 * FS)) / np.sqrt(np.maximum(np.fft.rfftfreq(10 * FS, 1 / FS), 20)))
pink = (.03 * w / np.sqrt(np.mean(w ** 2)))[:8 * FS]
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
m, fs = sf.read(sys.argv[2], always_2d=True)
if m.shape[1] == 1: m = np.repeat(m, 2, 1)
m = np.clip(resample_poly(m, 160, 147, axis=0) if fs == 44100 else m, -1, 1).astype(np.float32)[36 * FS:48 * FS]
X = {'bare': np.stack([bass, bass], 1), 'bass+pink': np.stack([bass + pink, bass + pink], 1), 'T60': m}
def trace(x):
    x = np.ascontiguousarray(x, np.float32); e = T.Engine(lib, FS, vb_on=1, vb_algo=6); lib.pvb_set_diagnostic_capture(e.h, 1)
    rows = []; buf = np.empty(ROWS * FIELDS, np.float32)
    for off in range(0, len(x), 256):
        b = x[off:off + 256].copy(); lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
        if n > 0: d = buf[:n * FIELDS].reshape(n, FIELDS).copy(); d[:, 0] += off; rows.append(d)
    e.close(); R = np.vstack(rows); return R, R[:, HEADER:].reshape(-1, TRACKS, TRACK)
for nm, x in X.items():
    R, ts = trace(x); t0 = 3 * FS if nm == 'T60' else FS // 2
    last = {}; dev = []; miss = []; wf = wa = 0.
    for i in np.flatnonzero(R[:, 0] >= t0):
        for j in range(TRACKS):
            st, f, a, rsn, msg = ts[i, j, 1], ts[i, j, 2], ts[i, j, 4], int(ts[i, j, 10]), ts[i, j, 9]
            tid = int(ts[i, j, 0]) + 65536 * int(ts[i, j, 13])
            if st <= 0 or not (73.3 < f < 220): continue
            fail = (rsn & 8) > 0; wa += a
            if not fail: last[tid] = f; continue
            wf += a; miss.append(msg > 0)
            if tid in last: dev.append(abs(f - last[tid]) / last[tid])
    dev = np.array(dev) if dev else np.zeros(1)
    print(f'{nm:9s} failed hops {100 * wf / max(wa, 1e-12):4.1f} % (amplitude-weighted) | missing>0 during failure {100 * np.mean(miss):4.1f} % | '
          f'|df|/f vs last pass: median {100 * np.median(dev):.2f} % p90 {100 * np.percentile(dev, 90):.2f} % max {100 * dev.max():.1f} %, '
          f'within 1 % {100 * np.mean(dev <= .01):.0f} %, 2 % {100 * np.mean(dev <= .02):.0f} % (n {len(dev)})')
def render(x, flags=0, vb=1):
    x = np.ascontiguousarray(x, np.float32); e = T.Engine(lib, FS, vb_on=vb, vb_algo=6)
    cap = StageCapture(lib, e.h, flags, int(len(x) / FS * 3000) + 16) if flags else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:lat + 7 * FS].mean(axis=1)
xb = X['bare']; dry = render(xb, vb=0); sos3 = butter(4, (285, 315), btype='band', fs=FS, output='sos')
cyc = lambda y: (np.abs(hilbert(sosfiltfilt(sos3, y))) ** 2)[:14 * FS // 2].reshape(14, -1)[1:].mean(axis=0).reshape(-1, 960).mean(axis=1)
cd = cyc(dry)
for nm, fl in (('P1', 0), ('R4c only', 16777216)):
    c = cyc(render(xb, fl) - dry)
    print(f'bare {nm:8s} 300 Hz layer re input per 20 ms: ' + ' '.join(f'{10 * np.log10(c[i] / cd[i]):+.0f}' for i in range(25)))
