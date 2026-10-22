#!/usr/bin/env python3
"""Host test suite for the PVB speaker engine.

The engine (app/src/main/cpp/libpvb) is built for the host by build_host.sh and driven through a small
C API with ctypes. Every check compares against an independent reference written here with numpy/scipy:
the RBJ biquads of EQ v1.1 (identical maths to the Python reference used in the listening tests) and a
16x oversampled true-peak meter.

    ./build_host.sh && python3 test_engine.py [--album DIR] [--report report.json]
"""
import argparse
import ctypes
import glob
import json
import os
import sys
import time

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt, sosfiltfilt, sosfreqz

HERE = os.path.dirname(os.path.abspath(__file__))

P = dict(ENABLED=0, HP_HZ=1, LOW_HZ=2, LOW_DB=3, LOW_Q=4, HI_HZ=5, HI_DB=6, HI_Q=7, OUT_DB=8,
         CEIL_DB=9, REL_MS=10, RAMP_MS=11, DYN_ON=12, DYN_REF_DB=13, DYN_DOWN_RATIO=14,
         DYN_DOWN_MAX_DB=15, DYN_UP_RATIO=16, DYN_UP_MAX_DB=17, HS_HZ=18, HS_DB=19, GATE_DB=20, TAG=21,
         VB_ON=22, VB_ALGO=23, VB_LEVEL_DB=24, FLAT=25, MATCH_HOLD=26, MATCH_SEED_DB=27, DIAGNOSTIC_SOLO=28)
M = dict(IN_PEAK_DB=0, OUT_PEAK_DB=1, LIM_GR_DB=2, LOW_DB_NOW=3, MIX=4, LOAD_PCT=5, SAMPLE_RATE=6,
         LATENCY=7, BLOCKS=8, NAN_EVENTS=9, EST_LEVEL_DB=10, EST_GR_DB=11, DYN_DB=12, DYN_LEVEL_DB=13, VB=14,
         MATCH_DB=15)

FP = ctypes.POINTER(ctypes.c_float)


def load_lib(path):
    lib = ctypes.CDLL(path)
    lib.pvb_create.restype = ctypes.c_void_p
    lib.pvb_create.argtypes = [ctypes.c_int]
    lib.pvb_destroy.argtypes = [ctypes.c_void_p]
    lib.pvb_set_sample_rate.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.pvb_set_params.argtypes = [ctypes.c_void_p, FP, ctypes.c_int]
    lib.pvb_process.argtypes = [ctypes.c_void_p, FP, ctypes.c_int]
    lib.pvb_process_i16.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_short), ctypes.POINTER(ctypes.c_short), ctypes.c_int]
    lib.pvb_read_meters.argtypes = [ctypes.c_void_p, FP, ctypes.c_int]
    lib.pvb_reset.argtypes = [ctypes.c_void_p]
    lib.pvb_latency.argtypes = [ctypes.c_void_p]
    lib.pvb_latency.restype = ctypes.c_int
    lib.pvb_open_ms.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.pvb_open_ms.restype = ctypes.c_int
    lib.pvb_match_db.argtypes = [ctypes.c_void_p]
    lib.pvb_match_db.restype = ctypes.c_float
    lib.pvb_match_measured.argtypes = [ctypes.c_void_p]
    lib.pvb_match_measured.restype = ctypes.c_int
    DP = ctypes.POINTER(ctypes.c_double)
    lib.pvb_vb_create.restype = ctypes.c_void_p
    lib.pvb_vb_create.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.pvb_vb_destroy.argtypes = [ctypes.c_void_p]
    lib.pvb_vb_latency.argtypes = [ctypes.c_void_p]
    lib.pvb_vb_latency.restype = ctypes.c_int
    lib.pvb_vb_process.argtypes = [ctypes.c_void_p, DP, DP, DP, DP, ctypes.c_int]
    lib.pvb_param_count.restype = ctypes.c_int
    lib.pvb_meter_count.restype = ctypes.c_int
    lib.pvb_default_params.argtypes = [FP]
    lib.pvb_estimate_phone_gr.argtypes = [ctypes.c_double]
    lib.pvb_estimate_phone_gr.restype = ctypes.c_double
    lib.pvb_analyze.argtypes = [ctypes.c_void_p, FP, FP, FP, FP, ctypes.c_int, FP, ctypes.c_int, ctypes.c_double]
    lib.pvb_analyze.restype = ctypes.c_int
    lib.pvb_ana_info_count.restype = ctypes.c_int
    lib.pvb_ana_point_hz.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.pvb_ana_point_hz.restype = ctypes.c_double
    return lib


class Engine:
    def __init__(self, lib, sr, **params):
        self.lib, self.sr = lib, sr
        self.h = lib.pvb_create(sr)
        self.params = np.zeros(lib.pvb_param_count(), np.float32)
        lib.pvb_default_params(self.params.ctypes.data_as(FP))
        if params:
            self.set(**params)

    def set(self, **kw):
        for k, v in kw.items():
            self.params[P[k.upper()]] = v
        self.lib.pvb_set_params(self.h, self.params.ctypes.data_as(FP), len(self.params))

    def process(self, x, block=4096, blocks=None):
        y = np.ascontiguousarray(x, np.float32).copy()
        n = y.shape[0]
        sizes = blocks if blocks is not None else None
        i, k = 0, 0
        while i < n:
            b = sizes[k % len(sizes)] if sizes is not None else block
            b = min(b, n - i)
            chunk = y[i:i + b]
            self.lib.pvb_process(self.h, chunk.ctypes.data_as(FP), b)
            i += b
            k += 1
        return y

    def process_with_meters(self, x, block=4096):
        y = np.ascontiguousarray(x, np.float32).copy()
        rows = []
        for i in range(0, y.shape[0], block):
            chunk = y[i:i + block]
            self.lib.pvb_process(self.h, chunk.ctypes.data_as(FP), chunk.shape[0])
            rows.append(self.meters())
        return y, np.array(rows)

    def meters(self):
        m = np.zeros(self.lib.pvb_meter_count(), np.float32)
        self.lib.pvb_read_meters(self.h, m.ctypes.data_as(FP), len(m))
        return m

    def latency(self):
        return self.lib.pvb_latency(self.h)

    def match_db(self):
        return float(self.lib.pvb_match_db(self.h))

    def match_measured(self):
        return bool(self.lib.pvb_match_measured(self.h))

    def analyze(self, n=240, dt=10.0):
        """Spectrum analysis; dt=10 s turns the display smoothing off (raw values)."""
        a = [np.zeros(n, np.float32) for _ in range(4)]
        info = np.zeros(self.lib.pvb_ana_info_count(), np.float32)
        r = self.lib.pvb_analyze(self.h, *[x.ctypes.data_as(FP) for x in a], n, info.ctypes.data_as(FP), len(info), dt)
        return dict(r=r, inp=a[0], out=a[1], diff=a[2], eq=a[3], info=info)

    def close(self):
        self.lib.pvb_destroy(self.h)


# ---------------------------------------------------------------------------------------- references
def rbj_peak(fs, f, g_db, q):
    A = 10 ** (g_db / 40); w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al / A
    return np.array([(1 + al * A) / a0, -2 * np.cos(w) / a0, (1 - al * A) / a0, 1.0, -2 * np.cos(w) / a0, (1 - al / A) / a0])


def rbj_hp(fs, f, q=1 / np.sqrt(2)):
    w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al; c = np.cos(w)
    return np.array([(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0, 1.0, -2 * c / a0, (1 - al) / a0])


def ref_sos(fs, p):
    return np.vstack([rbj_hp(fs, p['hp_hz']), rbj_hp(fs, p['hp_hz']),
                      rbj_peak(fs, p['low_hz'], p['low_db'], p['low_q']),
                      rbj_peak(fs, p['hi_hz'], p['hi_db'], p['hi_q'])])


V11 = dict(hp_hz=100, low_hz=220, low_db=3, low_q=1, hi_hz=4500, hi_db=-3, hi_q=0.6)


def true_peak_db(x, os_=16, edge=128):
    """Oversampled peak. The first and last `edge` input samples are left out of the oversampled
    search: resample_poly sees a hard cut at the ends of the array, and the ringing of that cut is a
    property of the measurement, not of the signal."""
    x = x[:, None] if x.ndim == 1 else x
    best = float(np.max(np.abs(x))) if len(x) else 0.0
    chunk = 1 << 16  # long signals are measured in overlapping pieces to bound memory
    start = 0
    while start < len(x):
        lo = max(0, start - edge)
        hi = min(len(x), start + chunk + edge)
        up = resample_poly(x[lo:hi], os_, 1, axis=0)
        a = (start - lo) * os_ if lo > 0 else (edge * os_ if hi - lo > 4 * edge else 0)
        b = len(up) - (hi - min(len(x), start + chunk)) * os_ if hi < len(x) else (len(up) - edge * os_ if hi - lo > 4 * edge else len(up))
        if b > a:
            best = max(best, float(np.max(np.abs(up[a:b]))))
        start += chunk
    return 20 * np.log10(max(best, 1e-12))


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-15))


def stereo(m):
    return np.repeat(np.asarray(m, np.float32)[:, None], 2, axis=1)


# ---------------------------------------------------------------------------------------- tests
RESULTS = []


def check(name, ok, **info):
    RESULTS.append(dict(test=name, ok=bool(ok), **{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}))
    flag = 'PASS' if ok else 'FAIL'
    detail = ', '.join(f'{k}={v:.4g}' if isinstance(v, (float, np.floating)) else f'{k}={v}' for k, v in info.items())
    print(f'[{flag}] {name}: {detail}', flush=True)


def impulse_response(lib, sr, params, n=1 << 17, amp=0.5):
    e = Engine(lib, sr, out_db=0.0, ceil_db=0.0, ramp_ms=0.0, **params)
    x = np.zeros((n, 2), np.float32); x[0, :] = amp
    y = e.process(x)
    lat = e.latency()
    e.close()
    return y[lat:, 0].astype(np.float64) / amp, lat


def t_response(lib):
    cases = [('EQ v1.1', V11),
             ('other', dict(hp_hz=60, low_hz=150, low_db=6, low_q=2.0, hi_hz=8000, hi_db=2, hi_q=1.5)),
             ('cut', dict(hp_hz=100, low_hz=220, low_db=0, low_q=1, hi_hz=4500, hi_db=-3, hi_q=0.6))]
    for sr in (44100, 48000):
        for label, p in cases:
            h, _ = impulse_response(lib, sr, p)
            n = len(h)
            H = np.fft.rfft(h, n)
            f = np.fft.rfftfreq(n, 1 / sr)
            sel = (f >= 20) & (f <= 20000)
            _, Hr = sosfreqz(ref_sos(sr, p), worN=f[sel], fs=sr)
            err = np.max(np.abs(db(H[sel]) - db(Hr)))
            check(f'response {label} @ {sr}', err <= 0.05, max_err_db=err)


def t_latency(lib):
    for sr in (44100, 48000):
        e = Engine(lib, sr, enabled=0.0, ramp_ms=0.0)
        e.process(np.zeros((sr // 5, 2), np.float32))  # let the 50 ms bypass fade finish
        x = np.zeros((4096, 2), np.float32); x[10, :] = 0.5
        y = e.process(x)
        pos = int(np.argmax(np.abs(y[:, 0])))
        lat = e.latency()
        e.close()
        check(f'latency @ {sr}', pos - 10 == lat and abs(y[pos, 0] - 0.5) < 1e-7, frames=lat, ms=1000.0 * lat / sr)


def t_against_reference_waveform(lib, x, sr):
    """Whole chain vs scipy reference while the limiter is idle (quiet input)."""
    e = Engine(lib, sr, **V11)
    y = e.process(x)
    lat = e.latency()
    e.close()
    ref = sosfilt(ref_sos(sr, V11), x.astype(np.float64), axis=0) * 10 ** (-5 / 20)
    d = y[lat:].astype(np.float64) - ref[:len(y) - lat]
    rel = 20 * np.log10(np.sqrt(np.mean(d ** 2)) / np.sqrt(np.mean(ref ** 2)))
    check('waveform vs reference (limiter idle)', rel < -100, residual_db=rel)


def t_clicks(lib, sr=48000):
    rng = np.random.default_rng(7)
    t = np.arange(10 * sr) / sr
    x = stereo(0.1 * np.sin(2 * np.pi * 100 * t))
    hp = butter(8, 2000, 'high', fs=sr, output='sos')
    res = {}
    for label, ramp in (('ramped 20 ms', 20.0), ('abrupt', 0.0)):
        e = Engine(lib, sr, **V11)
        out = []
        blk = sr // 10  # new values every 100 ms
        for i in range(0, len(x), blk):
            e.set(ramp_ms=ramp, low_db=rng.uniform(-6, 6), low_hz=rng.uniform(150, 350), hi_db=rng.uniform(-6, 3),
                  hp_hz=rng.uniform(60, 150), out_db=rng.uniform(-8, 0), low_q=rng.uniform(0.7, 2))
            out.append(e.process(x[i:i + blk]))
        e.close()
        y = np.concatenate(out)[sr // 2:]
        res[label] = np.max(np.abs(sosfiltfilt(hp, y[:, 0])))
    hf_r, hf_a = db(res['ramped 20 ms']), db(res['abrupt'])
    check('no clicks on parameter changes (HF > 2 kHz from a 100 Hz tone)', hf_r < -90 and hf_a - hf_r > 30,
          ramped_dbfs=hf_r, abrupt_dbfs=hf_a)


def t_true_peak(lib, sr=48000):
    t = np.arange(4 * sr) / sr
    flat = dict(hp_hz=20, low_db=0, hi_db=0, out_db=0)
    sigs = {
        'fs/4 sine, +3 dB between samples': stereo(0.99 * np.sin(2 * np.pi * (sr / 4) * t + np.pi / 4)),
        'full-scale 1 kHz square': stereo(np.sign(np.sin(2 * np.pi * 1000 * t)) * 0.999),
        'noise +12 dB into the limiter': stereo(np.clip(np.random.default_rng(1).normal(0, 0.3, len(t)), -1, 1)),
        'huge values (1e6)': stereo(1e6 * np.sin(2 * np.pi * 440 * t)),
    }
    for label, x in sigs.items():
        p = dict(flat)
        if 'noise' in label:
            p['out_db'] = 12
        e = Engine(lib, sr, ramp_ms=0, **p)
        y = e.process(x)
        e.close()
        tp = true_peak_db(y[sr // 10:])
        check(f'true peak <= -1 dBTP: {label}', tp <= -1.0 + 0.05 and np.all(np.isfinite(y)), dbtp=tp)


def t_edges(lib, sr=48000):
    # silence stays exact zero
    e = Engine(lib, sr)
    y = e.process(np.zeros((sr, 2), np.float32))
    check('silence -> exact zeros', np.all(y == 0))
    # DC is removed, nothing explodes
    y = e.process(np.full((2 * sr, 2), 0.5, np.float32))
    check('DC removed', np.max(np.abs(y[-sr // 2:])) < 1e-4 and np.all(np.isfinite(y)), tail_peak=float(np.max(np.abs(y[-sr // 2:]))))
    # NaN / Inf in the input
    x = (0.1 * np.sin(2 * np.pi * 300 * np.arange(sr) / sr)).astype(np.float32)
    x = stereo(x)
    x[1000, 0] = np.nan; x[2000, 1] = np.inf; x[3000, 0] = -np.inf
    m0 = e.meters()
    y = e.process(x)
    m1 = e.meters()
    check('NaN/Inf input -> finite output, counted', np.all(np.isfinite(y)) and m1[M['NAN_EVENTS']] > m0[M['NAN_EVENTS']],
          nan_events=float(m1[M['NAN_EVENTS']]))
    # denormal input
    y = e.process(np.full((sr, 2), 1e-40, np.float32))
    check('denormal input -> finite output', np.all(np.isfinite(y)))
    e.close()
    # block-size invariance: same output for 4096-frame blocks and random block sizes (1..5000)
    rng = np.random.default_rng(3)
    x = stereo(rng.normal(0, 0.1, 3 * sr))
    a = Engine(lib, sr); ya = a.process(x, block=4096); a.close()
    b = Engine(lib, sr); yb = b.process(x, blocks=list(rng.integers(1, 5000, 400))); b.close()
    check('block-size invariance (bit exact)', np.array_equal(ya, yb), max_diff=float(np.max(np.abs(ya - yb))))
    # sample-rate switch while running
    e = Engine(lib, 44100)
    y1 = e.process(x[:sr])
    e.lib.pvb_set_sample_rate(e.h, 48000)
    y2 = e.process(x[sr:2 * sr])
    m = e.meters()
    e.close()
    check('sample-rate switch 44.1 -> 48 kHz', np.all(np.isfinite(y1)) and np.all(np.isfinite(y2)) and m[M['SAMPLE_RATE']] == 48000,
          rate=float(m[M['SAMPLE_RATE']]))
    # out-of-range parameters are clamped, not trusted
    e = Engine(lib, sr, hp_hz=1e9, low_hz=-5, low_q=0, hi_hz=np.nan, out_db=500, ceil_db=50)
    y = e.process(x[:sr])
    e.close()
    check('absurd parameters are clamped', np.all(np.isfinite(y)) and true_peak_db(y) <= 0.05, dbtp=true_peak_db(y))


def t_bypass(lib, sr=48000):
    for fq in (1000, 100):
        t = np.arange(3 * sr) / sr
        x = stereo(0.1 * np.sin(2 * np.pi * fq * t))
        e = Engine(lib, sr, **V11)
        y0 = e.process(x[:sr])
        e.set(enabled=0)
        y1 = e.process(x[sr:2 * sr])
        e.set(enabled=1)
        y2 = e.process(x[2 * sr:])
        e.close()
        y = np.concatenate([y0, y1, y2])[:, 0].astype(np.float64)
        per = int(round(sr / fq))
        env = np.array([np.max(np.abs(y[i:i + per])) for i in range(0, len(y) - per, per)])
        wet = db(np.median(env[int(0.5 * sr / per):int(0.9 * sr / per)]))
        dry = db(np.median(env[int(1.5 * sr / per):int(1.9 * sr / per)]))
        trans = np.r_[env[int(0.95 * sr / per):int(1.15 * sr / per)], env[int(1.95 * sr / per):int(2.15 * sr / per)]]
        lo, hi = db(np.min(trans)), db(np.max(trans))
        ok = (hi <= max(wet, dry) + 0.5) and (lo >= min(wet, dry) - 0.5 if fq == 1000 else True)
        check(f'bypass crossfade {fq} Hz', ok, wet_db=wet, dry_db=dry, min_db=lo, max_db=hi)


def t_int16(lib, sr=48000):
    rng = np.random.default_rng(5)
    xf = stereo(rng.normal(0, 0.1, sr)).clip(-1, 1)
    xi = np.round(xf * 32767).astype(np.int16)
    e1 = Engine(lib, sr); yf = e1.process((xi / 32768.0).astype(np.float32)); e1.close()
    e2 = Engine(lib, sr)
    yi = np.zeros_like(xi)
    xc = np.ascontiguousarray(xi)
    lib.pvb_process_i16(e2.h, xc.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), yi.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), len(xi))
    e2.close()
    diff = np.max(np.abs(yi.astype(np.float64) - np.round(yf * 32768)))
    check('int16 path matches float path', diff <= 1, max_lsb=diff)


def t_meters(lib, sr=48000):
    t = np.arange(2 * sr) / sr
    x = stereo(0.5 * np.sin(2 * np.pi * 1000 * t))
    e = Engine(lib, sr, low_db=4.0)
    _, rows = e.process_with_meters(x)
    lat = e.latency()
    e.close()
    last = rows[-1]
    check('meters: low gain, mix, rate, latency', abs(last[M['LOW_DB_NOW']] - 4.0) < 1e-4 and last[M['MIX']] == 1.0
          and last[M['SAMPLE_RATE']] == sr and last[M['LATENCY']] == lat,
          low_db=float(last[M['LOW_DB_NOW']]), latency=float(last[M['LATENCY']]))
    pts = [(-40, 0.0), (-34, 0.0), (-25, 1.19), (-16, 6.02), (-13, 10.19), (-1, 19.9)]
    err = max(abs(lib.pvb_estimate_phone_gr(l) - g) for l, g in pts)
    check('phone processor static curve hits the measured points', err < 1e-9, max_err=err)


def rbj_high_shelf(fs, f, g, q=1 / np.sqrt(2)):
    A = 10 ** (g / 40); w = 2 * np.pi * f / fs; c = np.cos(w); al = np.sin(w) / (2 * q); sA = 2 * np.sqrt(A) * al
    b0 = A * ((A + 1) + (A - 1) * c + sA); b1 = -2 * A * ((A - 1) + (A + 1) * c); b2 = A * ((A + 1) + (A - 1) * c - sA)
    a0 = (A + 1) - (A - 1) * c + sA; a1 = 2 * ((A - 1) - (A + 1) * c); a2 = (A + 1) - (A - 1) * c - sA
    return np.array([b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0])


def t_high_shelf(lib, sr=48000):
    """Treble tilt stage: response equals the RBJ high shelf, in the audio path and in the analysis curve."""
    n = 240
    f = ana_freqs(lib, n)
    errs = []
    for g in (-6.0, -3.0, 4.0):
        p = dict(V11)
        e = Engine(lib, sr, hs_hz=2500, hs_db=g)
        e.process(np.zeros((4800, 2), np.float32))  # new settings glide in over 20 ms
        sos = np.vstack([ref_sos(sr, p), rbj_high_shelf(sr, 2500, g)[None, :]])
        _, h = sosfreqz(sos, worN=f, fs=sr)
        a = e.analyze(n)
        errs.append(float(np.max(np.abs(a['eq'] - 20 * np.log10(np.abs(h))))))
        # audio path: impulse response vs reference, limiter idle
        imp = np.zeros((1 << 15, 2), np.float32); imp[0] = 0.25
        y = e.process(imp)[:, 0]
        lat = e.latency()
        H = np.fft.rfft(y[lat:lat + (1 << 14)] / 0.25 / 10 ** (-5 / 20))
        fr = np.fft.rfftfreq(1 << 14, 1 / sr)
        _, h2 = sosfreqz(sos, worN=fr, fs=sr)
        band = (fr > 200) & (fr < 16000)
        errs.append(float(np.max(np.abs(20 * np.log10(np.abs(H[band]) + 1e-12) - 20 * np.log10(np.abs(h2[band]))))))
        e.close()
    check('high shelf = RBJ (analysis curve and audio path, -6/-3/+4 dB)', max(errs) < 0.02, max_err_db=max(errs))


def t_phone_model(lib, sr=48000):
    """The phone-processor estimate (display) behaves like the fitted model ('octx'): own band and cross-band ducking."""
    m = np.zeros(lib.pvb_meter_count(), np.float32)
    def gr_after(x, rate=sr):
        e = Engine(lib, rate, enabled=0)        # bypass: the estimate then sees the input itself
        e.process(x)
        lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); e.close()
        return float(m[M['EST_GR_DB']]), float(m[M['EST_LEVEL_DB']])
    t = np.arange(sr) / sr
    own, own_lvl = gr_after(stereo(10 ** (-13 / 20) * np.sin(2 * np.pi * 250 * t)))
    quiet, _ = gr_after(stereo(10 ** (-40 / 20) * np.sin(2 * np.pi * 250 * t)))
    cross, _ = gr_after(stereo(10 ** (-1 / 20) * np.sin(2 * np.pi * 2000 * t)))
    cross8, _ = gr_after(stereo(10 ** (-8 / 20) * np.sin(2 * np.pi * 2000 * t)))
    low, _ = gr_after(stereo(10 ** (-1 / 20) * np.sin(2 * np.pi * 63 * t)))
    t44 = np.arange(44100) / 44100
    own44, _ = gr_after(stereo(10 ** (-13 / 20) * np.sin(2 * np.pi * 250 * t44)), 44100)
    # model: own band -13 dBFS -> 10.19 dB (level read as -13); 2 kHz masker -> 250 Hz band exp(-3/3) x cross curve:
    # 19.9 x 0.368 = 7.3 dB at -1 dBFS, 4.5 x 0.368 = 1.7 dB at -8 dBFS
    check('phone estimate: own band 10.2 dB at -13 dBFS (48 and 44.1 kHz), quiet 0, 2 kHz ducks 250 Hz 7.3 / 1.7 dB',
          abs(own - 10.19) < 0.4 and abs(own_lvl + 13) < 0.3 and abs(own44 - 10.19) < 0.4 and quiet == 0.0
          and abs(cross - 7.3) < 1.0 and abs(cross8 - 1.66) < 0.6 and low < cross,
          own_db=own, level_db=own_lvl, own_44k_db=own44, quiet_db=quiet, cross_db=cross, cross_m8_db=cross8, from_63hz_db=low)


def t_mute(lib, sr=48000):
    """Output gain reaches -90 dB (the blind comparison mutes with it) and glides there without a click."""
    t = np.arange(sr) / sr
    x = stereo(0.5 * np.sin(2 * np.pi * 300 * t))
    e = Engine(lib, sr, out_db=-90)
    y = e.process(x)
    e.close()

    def run(mute):
        e = Engine(lib, sr)
        a = e.process(x[:sr // 2])
        if mute:
            e.set(out_db=-90, ramp_ms=150)
        b = e.process(x[sr // 2:])
        e.close()
        return np.concatenate([a, b])
    z, ref = run(True), run(False)
    tail = db(np.max(np.abs(z[int(0.8 * sr):])))
    sos = butter(8, 3000, 'hp', fs=sr, output='sos')
    hf = db(np.max(np.abs(sosfilt(sos, z[:, 0])[sr // 4:])))
    hf_ref = db(np.max(np.abs(sosfilt(sos, ref[:, 0])[sr // 4:])))
    check('mute: -90 dB output, 150 ms glide without a click', db(np.max(np.abs(y[sr // 2:]))) < -88 and tail < -88
          and hf < max(hf_ref + 3, -100), muted_db=db(np.max(np.abs(y[sr // 2:]))), after_glide_db=tail, hf_db=hf, hf_steady_db=hf_ref)


def t_gate(lib, sr=48000):
    """Review F04: the blind-comparison mute and headroom sit in a final gate after the dry/wet mix, so a bypass
    (route change with 'speaker only') cannot let unattenuated audio through."""
    t = np.arange(sr) / sr
    x = stereo(0.1 * np.sin(2 * np.pi * 1000 * t))
    def rms_tail(**kw):
        e = Engine(lib, sr, ramp_ms=0, **kw)
        y = e.process(x)
        e.close()
        return db(np.sqrt(np.mean(y[sr // 2:].astype(np.float64) ** 2)))
    old_mute_bypass = rms_tail(out_db=-90, enabled=0)       # what the review measured: the old mute is gone (-23 dBFS)
    muted_bypass = rms_tail(gate_db=-90, enabled=0)
    muted = rms_tail(gate_db=-90)
    dry = rms_tail(enabled=0)
    head_bypass = rms_tail(gate_db=-10, enabled=0)
    check('gate: mute after the mix holds through a bypass (old out-gain mute did not)', old_mute_bypass > -30
          and muted_bypass < -200 and muted < -200 and abs(head_bypass - (dry - 10)) < 0.01,
          old_mute_bypass_dbfs=old_mute_bypass, gate_mute_bypass_dbfs=muted_bypass, gate_mute_dbfs=muted,
          headroom_bypass_minus_dry_db=head_bypass - dry)

    # Glide: muting through the gate takes RAMP_MS without a click (same as the old out-gain mute).
    e = Engine(lib, sr)
    a = e.process(x[:sr // 2])
    e.set(gate_db=-90, ramp_ms=150)
    b = e.process(x[sr // 2:])
    e.close()
    z = np.concatenate([a, b])
    sos = butter(8, 3000, 'hp', fs=sr, output='sos')
    hf = db(np.max(np.abs(sosfilt(sos, z[:, 0])[sr // 4:])))
    tail = db(np.max(np.abs(z[int(0.8 * sr):])))
    check('gate: 150 ms glide to silence without a click', hf < -90 and tail < -200, hf_db=hf, after_glide_db=tail)


def t_open_ms(lib, sr=48000):
    """Review F04: 'heard' needs audio actually processed with that condition while audible."""
    t = np.arange(sr) / sr
    x = stereo(0.1 * np.sin(2 * np.pi * 300 * t))
    e = Engine(lib, sr, tag=7, ramp_ms=0)
    e.process(x[:sr // 2])
    open_half = lib.pvb_open_ms(e.h, 7)
    other = lib.pvb_open_ms(e.h, 8)
    e.set(tag=8, gate_db=-90)                    # new condition, muted: nothing counts
    e.process(x[:sr // 2])
    muted = lib.pvb_open_ms(e.h, 8)
    gone = lib.pvb_open_ms(e.h, 7)
    e.set(gate_db=-10, enabled=0)                # audible but bypassed (route change): does not count
    e.process(x[:sr // 4])
    bypassed = lib.pvb_open_ms(e.h, 8)
    e.set(enabled=1)
    e.process(np.zeros((sr // 4, 2), np.float32))  # processed but the music is silent: does not count
    silent = lib.pvb_open_ms(e.h, 8)
    e.process(x[:sr // 4])                       # 50 ms bypass fade back, then audible
    back = lib.pvb_open_ms(e.h, 8)
    e.close()
    check('open time: counts only audible, processed, non-silent audio of the active tag', 495 <= open_half <= 500
          and other == -1 and muted == 0 and gone == -1 and bypassed == 0 and silent == 0 and 150 <= back <= 250,
          tag7_ms=open_half, other_tag=other, muted_ms=muted, bypassed_ms=bypassed, silent_ms=silent, after_unbypass_ms=back)


def t_phone_stereo(lib, sr=48000):
    """Review F07: the phone estimate uses left and right powers, so R = -L is not read as silence."""
    m = np.zeros(lib.pvb_meter_count(), np.float32)
    t = np.arange(sr) / sr
    s = 10 ** (-13 / 20) * np.sin(2 * np.pi * 1000 * t)
    res = {}
    for label, sign in (('same', 1.0), ('opposite', -1.0)):
        x = np.stack([s, sign * s], 1).astype(np.float32)
        e = Engine(lib, sr, enabled=0)
        e.process(x)
        lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m))
        e.close()
        res[label] = (float(m[M['EST_LEVEL_DB']]), float(m[M['EST_GR_DB']]))
    one = np.stack([s, np.zeros_like(s)], 1).astype(np.float32)
    e = Engine(lib, sr, enabled=0); e.process(one); lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); e.close()
    single = float(m[M['EST_LEVEL_DB']])
    check('phone estimate: R = -L reads like R = L (per-channel power), one channel 3 dB lower',
          abs(res['same'][0] - res['opposite'][0]) < 1e-6 and abs(res['same'][1] - res['opposite'][1]) < 1e-6
          and abs(res['same'][0] + 13) < 0.3 and abs(single - (res['same'][0] - 3.01)) < 0.1,
          level_same_db=res['same'][0], level_opposite_db=res['opposite'][0], level_one_channel_db=single,
          gr_same_db=res['same'][1], gr_opposite_db=res['opposite'][1])


def t_analysis_concurrent(lib, sr=48000):
    """Review F11: analysis on another thread while audio runs (ctypes releases the GIL): every result is a clean
    1 kHz picture (no torn windows), and a copy overtaken by the audio thread is dropped, not shown."""
    import threading
    n = 240
    f = ana_freqs(lib, n)
    i1k = int(np.argmin(np.abs(f - 1000)))
    t = np.arange(4096) / sr
    blk = stereo(0.25 * np.sin(2 * np.pi * 1000 * t))     # whole periods: blocks join without a seam
    e = Engine(lib, sr, hp_hz=20, low_db=0, hi_db=0, out_db=0)
    e.process(np.tile(blk, (4, 1)))
    stop = threading.Event()
    def audio():
        buf = np.ascontiguousarray(blk.copy())
        while not stop.is_set():
            buf[:] = blk
            lib.pvb_process(e.h, buf.ctypes.data_as(FP), len(buf))
    th = threading.Thread(target=audio); th.start()
    bad = 0; fresh = 0; calls = 0
    t0 = time.time()
    while time.time() - t0 < 1.5:
        a = e.analyze(n, dt=10.0)
        calls += 1
        if a['info'][A['FRESH']] == 1:
            fresh += 1
            peak_bin = int(np.nanargmax(a['out']))
            if abs(peak_bin - i1k) > 1 or not np.isfinite(a['out'][i1k]):
                bad += 1
    stop.set(); th.join()
    e.close()
    check('analysis concurrent with audio: no torn windows', bad == 0 and fresh > 10, fresh_calls=fresh, calls=calls, bad=bad)


def t_silent_snap(lib, sr=48000):
    """While the output is muted, a new setting lands at once; the fade-in that follows carries no glide."""
    n = 240
    f = ana_freqs(lib, n)
    i220 = int(np.argmin(np.abs(f - 220)))
    x = pink(sr, sr, -20, seed=40)
    def after_change(start_out_db):
        e = Engine(lib, sr, out_db=start_out_db, low_db=3)
        e.process(x[:sr // 2])
        e.set(out_db=-5, low_db=9, ramp_ms=150)          # unmute (or stay) and change the bell in one push
        e.process(x[sr // 2:sr // 2 + 480])               # 10 ms later
        a = e.analyze(n)
        e.close()
        return float(a['eq'][i220])
    snapped, glide = after_change(-90), after_change(-5)
    e = Engine(lib, sr, low_db=9)
    e.process(x[:4800])                                   # past the 20 ms glide from the defaults
    target = float(e.analyze(n)['eq'][i220])
    e.close()
    check('muted: new setting applied at once; audible: it glides (150 ms)', abs(snapped - target) < 0.01
          and abs(glide - target) > 1.0, eq220_muted=snapped, eq220_audible=glide, eq220_target=target)


def t_reset(lib, sr=48000):
    """Re-entering the signal path: old audio is dropped and the output fades in from silence."""
    t = np.arange(sr) / sr
    x = stereo(0.3 * np.sin(2 * np.pi * 300 * t))
    e = Engine(lib, sr)
    e.process(x)
    lib.pvb_reset(e.h)
    y = e.process(x[:4800])
    e.close()
    first = np.max(np.abs(y[:10]))
    later = np.max(np.abs(y[3000:]))
    check('reset: fade in from silence, no stale audio', first < 1e-3 and later > 0.05 and np.all(np.isfinite(y)),
          first_10_peak=float(first), after_60ms_peak=float(later))


A = dict(FRESH=0, LIM_GR_DB=1, EST_GR_DB=2, LOW_DB_NOW=3, MIX=4, OUT_DB=5, SAMPLE_RATE=6, DYN_DB=7)


def pink(n, sr, rms_db, seed=5):
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2), np.float32)
    for c in range(2):
        W = np.fft.rfft(rng.standard_normal(n))
        f = np.fft.rfftfreq(n, 1 / sr)
        W[1:] /= np.sqrt(f[1:])
        W[0] = 0
        x = np.fft.irfft(W, n)
        out[:, c] = x / np.sqrt(np.mean(x ** 2)) * 10 ** (rms_db / 20)
    return out


def ana_freqs(lib, n=240):
    return np.array([lib.pvb_ana_point_hz(i, n) for i in range(n)])


def collect(e, x, every, start, n=240):
    """Process x block by block and analyze (raw) every `every` frames from `start` on."""
    rows = []
    i = 0
    y = np.ascontiguousarray(x, np.float32).copy()
    while i < len(y):
        b = min(every, len(y) - i)
        chunk = y[i:i + b]
        e.lib.pvb_process(e.h, chunk.ctypes.data_as(FP), b)
        i += b
        if i >= start:
            rows.append(e.analyze(n))
    return rows


def pow_mean_db(rows, key):
    v = np.array([r[key] for r in rows], np.float64)
    return 10 * np.log10(np.mean(10 ** (v / 10), axis=0))


def t_analysis(lib):
    n = 240
    f = ana_freqs(lib, n)

    # Nothing played yet: floor values, no measured change, exact filter curve.
    for sr in (48000, 44100):
        e = Engine(lib, sr)
        a = e.analyze(n)
        _, h = sosfreqz(ref_sos(sr, V11), worN=f, fs=sr)
        ref = 20 * np.log10(np.abs(h))
        ok = np.isfinite(a['eq'])
        err = float(np.max(np.abs(a['eq'][ok] - ref[ok])))
        check(f'analysis {sr // 1000 if sr % 1000 == 0 else sr / 1000} kHz: EQ curve = RBJ reference (no audio yet)',
              a['r'] == n and ok.all() and err < 0.01 and a['info'][A['FRESH']] == 0 and np.all(a['inp'] <= -150)
              and np.all(np.isnan(a['diff'])), max_err_db=err)
        e.close()

    # Points above Nyquist are left out.
    e = Engine(lib, 32000)
    a = e.analyze(n)
    check('analysis 32 kHz: points above Nyquist are NaN', np.all(np.isnan(a['eq'][f >= 0.499 * 32000]))
          and np.all(np.isfinite(a['eq'][f < 15000])), nan_points=int(np.sum(np.isnan(a['eq']))))
    e.close()

    # The curve follows a glide in progress (volume-linked low-mid change, 300 ms).
    sr = 48000
    e = Engine(lib, sr)
    e.process(np.zeros((sr // 10, 2), np.float32))
    e.set(low_db=9, ramp_ms=300)
    e.process(np.zeros((int(0.15 * sr), 2), np.float32), block=480)
    mid = e.analyze(n)
    e.process(np.zeros((int(0.3 * sr), 2), np.float32), block=480)
    end = e.analyze(n)
    i220 = int(np.argmin(np.abs(f - 220)))
    p = dict(V11, low_db=9)
    _, h = sosfreqz(ref_sos(sr, p), worN=f, fs=sr)
    err = float(np.max(np.abs(end['eq'] - 20 * np.log10(np.abs(h)))))
    check('analysis: EQ curve follows a glide, then lands on the new setting',
          3.5 < mid['eq'][i220] < 8.5 and abs(mid['info'][A['LOW_DB_NOW']] - 6) < 1.5 and err < 0.01,
          mid_220hz_db=float(mid['eq'][i220]), low_db_now=float(mid['info'][A['LOW_DB_NOW']]), end_err_db=err)
    e.close()

    # A sine shows up at its frequency, and 20 dB less input reads 20 dB less.
    t = np.arange(sr // 2) / sr
    levels = []
    for amp in (0.5, 0.05):
        e = Engine(lib, sr, enabled=0)
        e.process(stereo(amp * np.sin(2 * np.pi * 1000 * t)))
        a = e.analyze(n)
        levels.append(float(np.max(a['inp'])))
        peak_f = float(f[int(np.argmax(a['inp']))])
        e.close()
    check('analysis: 1 kHz sine peaks at 1 kHz, level is linear', abs(np.log2(peak_f / 1000)) <= 1 / 12
          and abs((levels[0] - levels[1]) - 20) < 0.05, peak_hz=peak_f, step_db=levels[0] - levels[1])

    # Pink noise is flat after the +3 dB/octave display tilt (30 s average: narrow low bands hold only
    # one or two FFT bins, so a single frame scatters by about +-2 dB there).
    e = Engine(lib, sr, enabled=0)
    rows = collect(e, pink(30 * sr, sr, -20), sr // 5, sr)
    m = pow_mean_db(rows, 'inp') + 3 * np.log2(f / 1000)
    band = (f >= 100) & (f <= 10000)
    spread = float(np.max(m[band]) - np.min(m[band]))
    octs = [float(np.mean(m[(f >= lo) & (f < lo * 2)])) for lo in (100, 200, 400, 800, 1600, 3200, 6400)]
    tilt_err = float(max(octs) - min(octs))
    bypass_diff = float(np.nanmax(np.abs(np.nanmean([r['diff'] for r in rows], axis=0)[band])))
    check('analysis: pink noise flat with +3 dB/oct tilt; bypass shows no change',
          spread < 1.5 and tilt_err < 0.3 and bypass_diff < 0.1,
          spread_db=spread, octave_means_spread_db=tilt_err, bypass_change_db=bypass_diff)
    e.close()

    # Measured change (output - input, output gain removed) equals the EQ curve while the limiter idles.
    e = Engine(lib, sr)
    rows = collect(e, pink(5 * sr, sr, -24, seed=7), sr // 5, sr)
    d = np.nanmean([r['diff'] for r in rows], axis=0)
    eq = rows[-1]['eq']
    band = (f >= 150) & (f <= 12000)
    err = float(np.max(np.abs(d[band] - eq[band])))
    gr = max(float(r['info'][A['LIM_GR_DB']]) for r in rows)
    check('analysis: measured change = EQ curve (limiter idle, 150 Hz - 12 kHz)', err < 0.5 and gr < 0.01,
          max_err_db=err, limiter_gr_db=gr, out_db=float(rows[-1]['info'][A['OUT_DB']]))
    e.close()

    # Loud input: the limiter shows up in the info and pulls the measured change below the curve.
    e = Engine(lib, sr, out_db=6)
    rows = collect(e, pink(4 * sr, sr, -8, seed=9), sr // 5, sr)
    d = np.nanmean([r['diff'] for r in rows], axis=0)
    gr = max(float(r['info'][A['LIM_GR_DB']]) for r in rows)
    below = float(np.mean((d - rows[-1]['eq'])[band]))
    check('analysis: limiter reduction reported, measured change drops below the curve', gr > 1.0 and below < -0.5,
          limiter_gr_db=gr, mean_below_curve_db=below)
    e.close()

    # Fresh flag, display fall rate, large blocks, cost.
    e = Engine(lib, sr, enabled=0)
    e.process(stereo(0.5 * np.sin(2 * np.pi * 1000 * t)))
    a1 = e.analyze(n)
    a2 = e.analyze(n, dt=0.033)
    e.process(np.zeros((sr // 2, 2), np.float32))
    a3 = e.analyze(n, dt=0.1)
    k = int(np.argmax(a1['inp']))
    fall = float(a1['inp'][k] - a3['inp'][k])
    big = Engine(lib, sr)
    ybig = big.process(pink(4 * sr, sr, -20, seed=3), block=8192)
    ab = big.analyze(n)
    t0 = time.perf_counter()
    for _ in range(100):
        big.analyze(n, dt=0.033)
    ms = (time.perf_counter() - t0) * 10
    check('analysis: fresh flag, 30 dB/s fall, 8192-frame blocks, cost per call',
          a1['info'][A['FRESH']] == 1 and a2['info'][A['FRESH']] == 0 and np.array_equal(a1['inp'], a2['inp'])
          and abs(fall - 3.0) < 0.01 and np.all(np.isfinite(ab['inp'][f < 20000])) and np.all(np.isfinite(ybig)),
          fall_db_in_100ms=fall, ms_per_call_unchanged_audio=ms)
    e.close()
    big.close()

    # Clock mode: the display time step is the time since the previous call that had new audio, so polling
    # faster than the audio blocks arrive does not slow the fall (review finding on build-5).
    e = Engine(lib, sr, enabled=0)
    e.process(stereo(0.5 * np.sin(2 * np.pi * 1000 * t)))
    c1 = e.analyze(n, dt=-1.0)
    t_fresh = time.perf_counter()
    for _ in range(6):
        time.sleep(0.02)
        e.analyze(n, dt=-1.0)  # nothing new
    e.process(np.zeros((sr // 2, 2), np.float32))
    c2 = e.analyze(n, dt=-1.0)
    elapsed = time.perf_counter() - t_fresh
    k = int(np.argmax(c1['inp']))
    fall = float(c1['inp'][k] - c2['inp'][k])
    check("analysis: clock-mode fall follows the time since the last new audio", abs(fall - 30 * elapsed) < 1.0,
          fall_db=fall, expected_db=30 * elapsed)
    e.close()

    # Analysis cost with new audio every call (two 8192-point FFTs).
    e = Engine(lib, sr)
    x = pink(sr, sr, -20, seed=4)
    t0 = time.perf_counter()
    for i in range(30):
        chunk = np.ascontiguousarray(x[i * 1600:(i + 1) * 1600])
        e.lib.pvb_process(e.h, chunk.ctypes.data_as(FP), 1600)
        e.analyze(n, dt=0.033)
    ms = (time.perf_counter() - t0) / 30 * 1000
    check('analysis: cost per frame on the host (process 33 ms + analyze)', ms < 10, ms_per_frame=ms)
    e.close()


def t_dynamic(lib, sr=48000):
    """Slow dynamic low-mid: less boost on loud passages (phone limiter), a little more on quiet ones."""
    n = 240
    f = ana_freqs(lib, n)
    i220 = int(np.argmin(np.abs(f - 220)))
    eq220_static = 2.619  # grid point next to 220 Hz with EQ v1.1 (HP contribution included)
    m = np.zeros(lib.pvb_meter_count(), np.float32)

    def run(x, **kw):
        kw = dict(dict(dyn_ref_db=-24, dyn_down_max_db=4), **kw)  # the full A+B variant (experimental)
        e = Engine(lib, sr, dyn_on=1, **kw)
        y = e.process(x)
        lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m))
        a = e.analyze(n)
        e.close()
        return y, float(m[M['DYN_DB']]), float(a['eq'][i220]), float(a['info'][A['DYN_DB']]), float(m[M['LOW_DB_NOW']])

    # Default off: bit-identical to the static EQ.
    x = pink(2 * sr, sr, -14, seed=20)
    a = Engine(lib, sr); ya = a.process(x); a.close()
    b = Engine(lib, sr, dyn_on=0); yb = b.process(x); b.close()
    check('dynamic: off = static EQ (bit exact)', np.array_equal(ya, yb))

    # Loud: boost taken back, at most 4 dB; shows in the curve, meters and analysis info.
    _, dl, eql, il, lowl = run(pink(6 * sr, sr, -10, seed=22))
    _, dm, eqm, _, _ = run(pink(6 * sr, sr, -16, seed=23))
    check('dynamic: loud takes boost back (capped 4 dB, louder takes more)',
          -4.0 - 1e-6 <= dl < -3.0 and dl < dm < -0.5 and abs(eql - (eq220_static + dl)) < 0.3 and il == dl
          and abs(lowl - (3 + dl)) < 1e-4, loud_db=dl, medium_db=dm, eq220_loud=eql)

    # Quiet: a little more (at most +2 dB); near silence holds (no boost of noise).
    _, dq, eqq, _, _ = run(pink(6 * sr, sr, -42, seed=24))
    yv, dv, _, _, _ = run(pink(3 * sr, sr, -85, seed=25))
    check('dynamic: quiet adds up to +2 dB, near silence holds', abs(dq - 2.0) < 1e-6 and abs(eqq - (eq220_static + 2)) < 0.3
          and dv == 0.0, quiet_db=dq, silence_db=dv)

    # Slow: 0.1 s after a jump from quiet to loud the change has barely started; after 4 s it is complete.
    e = Engine(lib, sr, dyn_on=1, dyn_ref_db=-24, dyn_down_max_db=4)
    e.process(pink(6 * sr, sr, -42, seed=26))
    e.process(pink(sr // 10, sr, -10, seed=27))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); early = float(m[M['DYN_DB']])
    e.process(pink(4 * sr, sr, -10, seed=28))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); late = float(m[M['DYN_DB']])
    e.set(dyn_on=0)
    e.process(pink(sr // 2, sr, -10, seed=29))
    an = e.analyze(n)
    e.close()
    check('dynamic: moves slowly (0.5 s rise); switching off restores the curve', early > 0.5 and -4.0 - 1e-6 <= late < -3.0
          and abs(an['eq'][i220] - eq220_static) < 0.05 and an['info'][A['DYN_DB']] == 0, after_100ms=early, after_4s=late)

    # Default (headroom only): loud music untouched, quiet music gets up to +2 dB.
    e = Engine(lib, sr, dyn_on=1); e.process(pink(6 * sr, sr, -10, seed=30))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); dl = float(m[M['DYN_DB']]); e.close()
    e = Engine(lib, sr, dyn_on=1); e.process(pink(6 * sr, sr, -42, seed=31))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); dq = float(m[M['DYN_DB']]); e.close()
    check('dynamic default (headroom only): loud untouched, quiet +2 dB', dl == 0.0 and abs(dq - 2.0) < 1e-6,
          loud_db=dl, quiet_db=dq)
    # The level the stage compares with its reference is reported (pink -42 dBFS RMS: >200 Hz part, -5 dB out gain).
    e = Engine(lib, sr, dyn_on=1); e.process(pink(6 * sr, sr, -42, seed=31))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); lq = float(m[M['DYN_LEVEL_DB']]); e.close()
    e = Engine(lib, sr, dyn_on=1); e.process(pink(6 * sr, sr, -10, seed=30))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); ll = float(m[M['DYN_LEVEL_DB']]); e.close()
    e = Engine(lib, sr); e.process(pink(sr, sr, -10, seed=30))
    lib.pvb_read_meters(e.h, m.ctypes.data_as(FP), len(m)); loff = float(m[M['DYN_LEVEL_DB']]); e.close()
    check('dynamic: level meter follows the stage (quiet ~-46, loud ~-14 dBFS; off -120)', -50 < lq < -42 and -18 < ll < -10
          and abs(ll - lq - 32) < 1.5 and loff == -120.0, quiet_level_db=lq, loud_level_db=ll, off_db=loff)

    # Bursts: gain moves without clicks, true peak still held.
    t = np.arange(6 * sr) / sr
    env = np.where((t % 2.0) < 1.0, 1.0, 0.03)
    x = stereo(0.9 * env * np.sin(2 * np.pi * 220 * t))
    y, _, _, _, _ = run(x)
    e2 = Engine(lib, sr); y2 = e2.process(x); e2.close()
    sos = butter(8, 2000, 'hp', fs=sr, output='sos')
    hf = db(np.max(np.abs(sosfilt(sos, y[:, 0])[sr:])))
    hf_ref = db(np.max(np.abs(sosfilt(sos, y2[:, 0])[sr:])))
    tp = true_peak_db(y)
    check('dynamic: no clicks on 220 Hz bursts, true peak held', hf - hf_ref < 3 and tp <= -1.0 + 0.05,
          hf_db=hf, hf_static_db=hf_ref, dbtp=tp)


# ---------------------------------------------------------------------------------------- virtual bass
VB_HPV, VB_BANKSTOWN = 0, 1
sys.path.insert(0, os.path.join(HERE, 'vb_port'))


def vb_layer(lib, algo, fs, left, right):
    """The C++ module alone (pvb_vb.cpp): layer for both channels, its latency, seconds of CPU."""
    DP = ctypes.POINTER(ctypes.c_double)
    m = lib.pvb_vb_create(algo, fs)
    if not m:
        return None, None, 0, 0.0
    a = np.ascontiguousarray(left, np.float64); b = np.ascontiguousarray(right, np.float64)
    oa = np.zeros_like(a); ob = np.zeros_like(a)
    t0 = time.perf_counter()
    lib.pvb_vb_process(m, a.ctypes.data_as(DP), b.ctypes.data_as(DP), oa.ctypes.data_as(DP), ob.ctypes.data_as(DP), len(a))
    dt = time.perf_counter() - t0
    lat = lib.pvb_vb_latency(m)
    lib.pvb_vb_destroy(m)
    return oa, ob, lat, dt


def rel_db(a, b):
    return float(20 * np.log10(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)) / max(np.sqrt(np.mean(np.asarray(b) ** 2)), 1e-30)))


def vb_signals(fs):
    """Deterministic test signals: single tone, two-note fifth, kick drum + bass line."""
    t = np.arange(int(4 * fs)) / fs
    tone = 0.3 * np.sin(2 * np.pi * 55 * t)
    fifth = 0.3 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 82.5 * t)
    kb = np.zeros(len(t))
    for st in np.arange(0, 4.0, 0.5):
        i0 = int(st * fs); m = min(len(t) - i0, int(0.3 * fs)); tt = np.arange(m) / fs
        kb[i0:i0 + m] += 0.5 * np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-tt / 0.02)) / fs) * np.exp(-tt / 0.12)
    for k, f0 in enumerate([41.2, 41.2, 55.0, 49.0]):
        a, b = int(k * fs), int((k + 1) * fs)
        kb[a:b] += 0.25 * sum(np.sin(2 * np.pi * f0 * h * t[a:b]) / h for h in range(1, 5))
    return dict(tone=tone, fifth=fifth, kick_bass=kb)


def t_vb_reference(lib, album=None):
    """C++ virtual bass modules vs the Python reference (vb_port/hpv_ref.py = vbcore.layer_hpv + causal shift)."""
    import hpv_ref as R
    # the frozen reference still equals the research code (when vb5 is there)
    try:
        sys.path.insert(0, os.path.join(HERE, 'vb5'))
        import vbcore as V
        V._TAB['lo'] = (R.FG, R.W, R.G)          # the exported tables (vbcore would rebuild them from measurement files)
        x = vb_signals(48000)['fifth'][:3 * 48000]
        a, _ = V.layer_hpv(x)
        e = rel_db(R.layer_like_vbcore(x), a)
        check('virtual bass: frozen reference (vb_port) == vbcore.layer_hpv', e < -200, rel_db=e)
    except ImportError as ex:
        print(f'[SKIP] vbcore not importable ({ex})')
    worst = -999.0
    rows = {}
    for fs in (48000, 44100):
        for name, x in vb_signals(fs).items():
            y, _, lat, _ = vb_layer(lib, VB_HPV, fs, x, x)
            e = rel_db(y, R.layer_rt(x, fs))
            rows[f'{name}@{fs}'] = e
            worst = max(worst, e)
        check(f'virtual bass hpv latency @ {fs}', lat == R.latency_frames(fs), frames=lat, ms=1000 * lat / fs)
    check('virtual bass hpv: C++ == Python reference (tone, fifth, kick+bass; 44.1 and 48 kHz)', worst < -150,
          worst_rel_db=worst, **{k.replace('@', '_'): v for k, v in rows.items()})
    # 44.1 kHz runs the same 3 kHz core: its layer, resampled to 48 kHz, matches the 48 kHz layer
    from scipy.signal import resample_poly
    x48 = vb_signals(48000)['fifth']
    x44 = resample_poly(x48, 147, 160)
    y48, _, _, _ = vb_layer(lib, VB_HPV, 48000, x48, x48)
    y44, _, _, _ = vb_layer(lib, VB_HPV, 44100, x44, x44)
    up = resample_poly(y44, 160, 147)[:len(y48)]
    sl = slice(48000, len(up) - 24000)
    e = rel_db(up[sl], y48[sl])
    check('virtual bass hpv: 44.1 kHz layer == 48 kHz layer (same 3 kHz core)', e < -50, rel_db=e)
    # Bankstown: per channel, formula reference
    for fs in (48000, 44100):
        x = vb_signals(fs)['kick_bass']; xr = vb_signals(fs)['fifth']
        yl, yr, lat, _ = vb_layer(lib, VB_BANKSTOWN, fs, x, xr)
        el, er = rel_db(yl, R.bankstown_layer(x, fs)), rel_db(yr, R.bankstown_layer(xr, fs))
        check(f'Bankstown: C++ == formula reference, per channel, no latency @ {fs}', max(el, er) < -150 and lat == 0,
              left_rel_db=el, right_rel_db=er, latency=lat)
    # music excerpt (album, local runs only)
    if album:
        import soundfile as sf
        files = sorted(glob.glob(os.path.join(glob.escape(album), '*.flac')))
        if files:
            x44, fs0 = sf.read(files[1], start=60 * 44100, frames=10 * 44100, dtype='float64', always_2d=True)
            res = {}
            for fs, x in ((44100, x44), (48000, resample_poly(x44, 160, 147, axis=0))):
                y, _, _, dt = vb_layer(lib, VB_HPV, fs, x[:, 0], x[:, 1])
                res[fs] = rel_db(y, R.layer_rt((x[:, 0] + x[:, 1]) / 2.0, fs))
            check(f'virtual bass hpv: C++ == Python reference on 10 s of music ({os.path.basename(files[1])[:30]})',
                  max(res.values()) < -150, rel_db_44k=res[44100], rel_db_48k=res[48000])


def t_vb_engine(lib):
    """Virtual bass inside the engine: insertion point, latency meter, switching without clicks or time jumps."""
    import hpv_ref as R
    sr = 48000
    lat_lim = 88
    rng = np.random.default_rng(21)
    t = np.arange(3 * sr) / sr
    x = np.stack([0.1 * np.sin(2 * np.pi * 55 * t) + 0.01 * rng.standard_normal(len(t)),
                  0.08 * np.sin(2 * np.pi * 55 * t + 0.4) + 0.01 * rng.standard_normal(len(t))], 1).astype(np.float32)
    x64 = x.astype(np.float64)
    # full chain with hpv at -3 dB: EQ v1.1 on the input delayed by D, + layer (both channels), x output gain
    e = Engine(lib, sr, vb_on=1, vb_algo=VB_HPV, vb_level_db=-3, ramp_ms=0)
    lib.pvb_reset(e.h)        # entering the signal path: silent start, so the module starts at frame 0 like the reference
    y = e.process(x)
    m = e.meters()
    e.close()
    D = R.latency_frames(sr)
    xd = np.r_[np.zeros((D, 2)), x64[:-D]]
    lay = R.layer_rt(x64.mean(1), sr) * 10 ** (-3 / 20)
    ref = (sosfilt(ref_sos(sr, V11), xd, axis=0) + lay[:, None]) * 10 ** (-5 / 20)
    yl = y[lat_lim:].astype(np.float64)
    err = rel_db(yl[sr // 2:], ref[sr // 2:len(yl)])
    # the highest level the app offers (+9 dB) passes unclamped
    e = Engine(lib, sr, vb_on=1, vb_algo=VB_HPV, vb_level_db=9, ramp_ms=0)
    lib.pvb_reset(e.h)
    y9 = e.process(x)
    e.close()
    ref9 = (sosfilt(ref_sos(sr, V11), xd, axis=0) + lay[:, None] * 10 ** (12 / 20)) * 10 ** (-5 / 20)
    err9 = rel_db(y9[lat_lim:].astype(np.float64)[sr // 2:], ref9[sr // 2:len(y9) - lat_lim])
    check('virtual bass in the engine: EQ(input delayed) + layer, before output gain (limiter idle) @ 48 kHz, -3 and +9 dB',
          err < -100 and err9 < -100 and m[M['LATENCY']] == lat_lim + D and m[M['VB']] == 1 + VB_HPV,
          rel_db=err, rel_db_plus9=err9, latency_frames=float(m[M['LATENCY']]),
          latency_ms=1000 * float(m[M['LATENCY']]) / sr)
    # Bankstown in the engine: no latency, per channel, on the EQ output: out = eq + layer(eq), then output gain
    e = Engine(lib, sr, vb_on=1, vb_algo=VB_BANKSTOWN, vb_level_db=0, ramp_ms=0)
    lib.pvb_reset(e.h)
    y = e.process(x)
    m = e.meters()
    e.close()
    eqx = sosfilt(ref_sos(sr, V11), x64, axis=0)
    lay2 = np.stack([R.bankstown_layer(eqx[:, c], sr) for c in range(2)], 1)
    ref2 = (eqx + lay2) * 10 ** (-5 / 20)
    yl = y[lat_lim:].astype(np.float64)
    err2 = rel_db(yl[sr // 2:], ref2[sr // 2:len(yl)])
    check('Bankstown in the engine: EQ out + layer(EQ out) per channel, latency unchanged', err2 < -100 and m[M['LATENCY']] == lat_lim
          and m[M['VB']] == 1 + VB_BANKSTOWN, rel_db=err2, latency_frames=float(m[M['LATENCY']]))
    e = Engine(lib, 44100, vb_on=1, vb_algo=VB_HPV)
    e.process(np.zeros((4410, 2), np.float32))
    m44 = e.meters(); e.close()
    check('latency meter @ 44.1 kHz with hpv', m44[M['LATENCY']] == 82 + R.latency_frames(44100),
          latency_frames=float(m44[M['LATENCY']]), latency_ms=1000 * float(m44[M['LATENCY']]) / 44100)

    # Switching while audible: fade out 30 ms, silent for the added latency, fade in; the music continues where it
    # stopped (no repeat, no jump) and there is no click. A 220 Hz tone with a slow amplitude ramp marks the time.
    n = 4 * sr
    tt = np.arange(n) / sr
    env = 0.05 + 0.1 * tt / tt[-1]
    s = (env * np.sin(2 * np.pi * 220 * tt)).astype(np.float32)
    xs = np.stack([s, s], 1)
    e = Engine(lib, sr, vb_level_db=-120)          # layer silent: only the latency path shows
    a = e.process(xs[:sr])
    e.set(vb_on=1, vb_algo=VB_HPV)
    b = e.process(xs[sr:3 * sr])
    e.set(vb_on=0)
    c = e.process(xs[3 * sr:])
    e.close()
    out = np.concatenate([a, b, c])[:, 0].astype(np.float64)
    blk = int(0.005 * sr)
    rms = np.sqrt(np.mean(out[:len(out) // blk * blk].reshape(-1, blk) ** 2, axis=1))
    silent = rms < 1e-4
    # silent stretch after the switch on (starts ~30 ms after 1 s)
    on_blocks = np.where(silent[int(1.0 / 0.005):int(1.5 / 0.005)])[0]
    gap_on_ms = len(on_blocks) * 5.0
    # where does the music continue? correlate the output after the gap with the input
    k0 = int(1.25 * sr)
    seg = out[k0:k0 + 2400]
    ref_eq = sosfilt(ref_sos(sr, V11), s.astype(np.float64)) * 10 ** (-5 / 20)
    lags = np.arange(D - 400, D + 400)
    errs = [np.max(np.abs(seg - ref_eq[k0 - lat_lim - L:k0 - lat_lim - L + 2400])) for L in lags]
    best = int(lags[int(np.argmin(errs))])
    sos = butter(8, 2000, 'high', fs=sr, output='sos')
    hf = db(np.max(np.abs(sosfilt(sos, out)[sr // 2:])))
    hf_steady = db(np.max(np.abs(sosfilt(sos, out)[sr // 2:sr - 100])))
    off_blocks = np.where(silent[int(3.0 / 0.005):int(3.3 / 0.005)])[0]
    check('virtual bass switch: on = fade, silence for the added latency, fade in, aligned; off = short dip; no click',
          abs(gap_on_ms - 1000 * D / sr) <= 40 and best == D and len(off_blocks) <= 6 and hf < -60,
          silent_after_on_ms=gap_on_ms, added_latency_ms=1000 * D / sr, delay_after_switch=best,
          silent_after_off_ms=len(off_blocks) * 5.0, hf_db=hf, hf_steady_db=hf_steady)

    # Switching while muted (blind comparison): immediate, no hold; unmuted output already aligned.
    e = Engine(lib, sr, vb_level_db=-120)
    e.process(xs[:sr])
    e.set(gate_db=-90, ramp_ms=150)
    e.process(xs[sr:sr + sr // 4])
    e.set(vb_on=1, vb_algo=VB_HPV)                 # while muted
    e.process(xs[sr + sr // 4:sr + sr // 2])
    e.set(gate_db=0, ramp_ms=150)
    z = e.process(xs[sr + sr // 2:2 * sr + sr // 2])
    m = e.meters()
    e.close()
    zz = z[:, 0].astype(np.float64)[sr // 4:]
    k0 = sr + sr // 2 + sr // 4
    errs = [np.max(np.abs(zz[:2400] - ref_eq[k0 - lat_lim - L:k0 - lat_lim - L + 2400])) for L in lags]
    best_m = int(lags[int(np.argmin(errs))])
    check('virtual bass switch while muted: immediate, aligned when the sound returns', best_m == D
          and m[M['VB']] == 1 + VB_HPV and np.min(errs) < 1e-6, delay=best_m, max_err=float(np.min(errs)))

    # Level change glides (no click), e.g. -3 -> +3 dB.
    e = Engine(lib, sr, vb_on=1, vb_algo=VB_HPV, vb_level_db=-3)
    k = vb_signals(sr)['kick_bass'].astype(np.float32) * 0.5
    xk = np.stack([k, k], 1)
    p1 = e.process(xk[:2 * sr])
    e.set(vb_level_db=3, ramp_ms=20)
    p2 = e.process(xk[2 * sr:])
    e.close()
    pk = np.concatenate([p1, p2])[:, 0].astype(np.float64)
    hp = butter(8, 4000, 'high', fs=sr, output='sos')
    around = np.abs(sosfilt(hp, pk))
    jump = db(np.max(around[2 * sr - 480:2 * sr + 2400]))
    base = db(np.max(around[sr:2 * sr - 960]))
    check('virtual bass level change: 20 ms glide, no click', jump < base + 3, hf_at_change_db=jump, hf_before_db=base)

    # CPU on the host
    xc = np.stack([vb_signals(sr)['fifth']] * 2, 1).astype(np.float32)
    xc = np.tile(xc, (15, 1))[:60 * sr]
    res = {}
    for label, kw in (('off', dict()), ('hpv', dict(vb_on=1, vb_algo=VB_HPV)), ('bankstown', dict(vb_on=1, vb_algo=VB_BANKSTOWN))):
        e = Engine(lib, sr, **kw)
        t0 = time.perf_counter(); e.process(xc, block=4096); res[label] = time.perf_counter() - t0
        e.close()
    check('virtual bass CPU (host, 60 s stereo @ 48 kHz, whole engine)', res['hpv'] < 20 and res['bankstown'] < 10,
          off_ms_per_s=1000 * res['off'] / 60, hpv_ms_per_s=1000 * res['hpv'] / 60,
          bankstown_ms_per_s=1000 * res['bankstown'] / 60)


def t_performance(lib, sr=48000):
    x = stereo(np.random.default_rng(2).normal(0, 0.1, 60 * sr))
    e = Engine(lib, sr)
    t0 = time.perf_counter()
    e.process(x, block=4096)
    dt = time.perf_counter() - t0
    e.close()
    check('speed (host, 60 s stereo @ 48 kHz)', dt < 6.0, seconds=dt, realtime_pct=100 * dt / 60)


def t_album(lib, album):
    import soundfile as sf
    files = sorted(glob.glob(os.path.join(glob.escape(album), '*.flac')))
    if not files:
        print('[SKIP] album: no files')
        return
    rows = []
    for fn in files:
        x, sr = sf.read(fn, dtype='float32', always_2d=True)
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        x = x[:, :2]
        e = Engine(lib, sr)
        y = e.process(x)
        lat = e.latency()
        e.close()
        ref = (sosfilt(ref_sos(sr, V11), x.astype(np.float64), axis=0) * 10 ** (-5 / 20))
        yl = y[lat:].astype(np.float64)
        rl = ref[:len(yl)]
        # 10 ms blocks where the limiter changed the level by more than 0.1 dB
        blk = int(0.01 * sr)
        nb = len(yl) // blk
        ey = np.sqrt(np.mean(yl[:nb * blk].reshape(nb, blk, 2) ** 2, axis=(1, 2)) + 1e-20)
        er = np.sqrt(np.mean(rl[:nb * blk].reshape(nb, blk, 2) ** 2, axis=(1, 2)) + 1e-20)
        active = np.mean(np.abs(20 * np.log10(ey / er)) > 0.1) * 100
        # the same track with the virtual bass at its highest level (+9 dB): still held at the ceiling
        e = Engine(lib, sr, vb_on=1, vb_algo=VB_HPV, vb_level_db=9)
        y9 = e.process(x)
        lat9 = e.latency()
        e.close()
        rows.append(dict(track=os.path.basename(fn), in_tp=true_peak_db(x, 4), ref_tp=true_peak_db(rl, 4),
                         out_tp=true_peak_db(yl, 16), limiter_active_pct=active, vb9_tp=true_peak_db(y9[lat9:], 8)))
        print(f"   {rows[-1]['track'][:40]:40s} in {rows[-1]['in_tp']:+6.2f}  eq-only {rows[-1]['ref_tp']:+6.2f}  "
              f"out {rows[-1]['out_tp']:+6.2f} dBTP  limiter active {active:5.2f}% of 10 ms blocks", flush=True)
    worst = max(r['out_tp'] for r in rows)
    check(f'album: {len(rows)} tracks <= -1 dBTP', worst <= -1.0 + 0.05, worst_dbtp=worst,
          median_limiter_active_pct=float(np.median([r['limiter_active_pct'] for r in rows])))
    worst9 = max(r['vb9_tp'] for r in rows)
    check(f'album with virtual bass hpv +9 dB: {len(rows)} tracks <= -1 dBTP', worst9 <= -1.0 + 0.05, worst_dbtp=worst9)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(HERE, 'build', 'libpvbcapi.so'))
    ap.add_argument('--album', default=None)
    ap.add_argument('--report', default=None)
    a = ap.parse_args()
    lib = load_lib(a.lib)

    t_response(lib)
    t_latency(lib)
    rng = np.random.default_rng(11)
    t_against_reference_waveform(lib, stereo(rng.normal(0, 0.02, 3 * 48000)), 48000)
    t_clicks(lib)
    t_true_peak(lib)
    t_edges(lib)
    t_bypass(lib)
    t_int16(lib)
    t_meters(lib)
    t_reset(lib)
    t_analysis(lib)
    t_dynamic(lib)
    t_high_shelf(lib)
    t_phone_model(lib)
    t_mute(lib)
    t_gate(lib)
    t_open_ms(lib)
    t_phone_stereo(lib)
    t_analysis_concurrent(lib)
    t_silent_snap(lib)
    t_vb_reference(lib, a.album)
    t_vb_engine(lib)
    t_performance(lib)
    album = t_album(lib, a.album) if a.album else None

    n_fail = sum(not r['ok'] for r in RESULTS)
    print(f'\n{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed')
    if a.report:
        json.dump(dict(results=RESULTS, album=album), open(a.report, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()

