#!/usr/bin/env python3
"""Independent cross-check of the Resultant core acceptance metrics (written by the acceptance verifier, not by the
implementer or the author of research_core_metrics.py). Spec: docs/RESULTANT_CORE.md v1.5 section 7 + v1.4 fixed
interpretations. This file does NOT import research_core_metrics, research_core_signals or research_core_api; the only
shared code is test_engine (library loading, the Engine parameter block, process()).

Run from tools/pvb-harness:
    PYTHONPATH=.:study python research_core_xcheck.py --parts v3b,v4,v0 --out ~/r3a-dev/verify_core/xcheck_v3b_v4_v0.json
Parts: v3b v4 v5 v0 v3c sanity v7d v6
"""
import argparse
import ctypes as C
import json
import re
import struct
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt, sosfiltfilt

import test_engine as T

FS = 48000
HOME = Path.home()
CAND = str((Path(__file__).resolve().parent / 'build_core/libpvbcapi.so'))
REF = str(HOME / 'r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so')
SLAKH = HOME / 'datasets/slakh2100/train'                 # train only
SLAKH_MIDI = HOME / 'datasets/slakh2100_midi/train'
LOGOFF = HOME / 'r3a-dev/songs/logoff.mp3'
DP = C.POINTER(C.c_double)
# spec 5.8 order and defaults (index 4 reserved in v1.3)
PNAMES = ['voicing', 'levelDb', 'ampSource', 'snrOnDb', 'reserved', 'snrOffDb', 'tauOnMs', 'tauOffMs', 'betaMin', 'betaMax',
          'kappa', 'nMin', 'nFuture', 'psiSlew', 'crest', 'maxDfdtBirth']
PDEF = [0, 0, 0, 15, 22, 6, 8, 30, .2, .9, 1.0, 30, 24, .12, 0, 200]
CFG = {'A': dict(voicing=0, ampSource=0), 'B': dict(voicing=0, ampSource=1),
       'C': dict(voicing=1, levelDb=6, ampSource=0), 'D': dict(voicing=1, levelDb=9, ampSource=0)}
# voice trace fields (spec 4.2)
(F_HOP, F_VOICE, F_TRACK, F_STATE, F_COAST, F_FTR, F_FOSC, F_DFDT, F_A, F_C, F_SIG, F_NP, F_SNR, F_PROM, F_RAW, F_RES, F_SUB,
 F_THETA, F_PSI2, F_PSI3, F_A2, F_A3) = range(22)
EMPTY, CAND_, ON, REL = 0, 1, 2, 3
OUT = {}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------------------------------ engine access
_libs = {}


def open_lib(path):
    path = str(Path(path).resolve())
    if path not in _libs:
        lib = T.load_lib(path)
        if hasattr(lib, 'pvb_set_resultant'):
            lib.pvb_set_resultant.argtypes = [C.c_void_p, DP, C.c_int]; lib.pvb_set_resultant.restype = C.c_int
            lib.pvb_resultant_trace_enable.argtypes = [C.c_void_p, C.c_int]; lib.pvb_resultant_trace_enable.restype = C.c_int
            lib.pvb_resultant_trace_copy.argtypes = [C.c_void_p, DP, C.c_int]; lib.pvb_resultant_trace_copy.restype = C.c_int
        _libs[path] = lib
    return _libs[path]


def render(lib, x, algo, level=0.0, out_db=-5.0, cfg=None, block=256, sr=FS, tail_s=0.5, trace=False, seq=None):
    """x mono (n,) or stereo (n,2) float. Returns dict(y float32 (n+tail,2), lat frames, trace rows (m,22) or None, meters).
    seq: optional list of algorithms; the signal is cut into len(seq) equal pieces and the algorithm is switched between them."""
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    assert x.ndim == 2 and x.shape[1] == 2, x.shape        # interleaved stereo only
    x = np.ascontiguousarray(np.concatenate([x, np.zeros((int(tail_s * sr), 2), np.float32)]))
    e = T.Engine(lib, sr, vb_on=1, vb_algo=(seq[0] if seq else algo), vb_level_db=level, out_db=out_db, ramp_ms=0)
    try:
        if algo == 15 or (seq and 15 in seq):
            v = np.array([(cfg or {}).get(n, d) for n, d in zip(PNAMES, PDEF)], np.float64)
            if lib.pvb_set_resultant(e.h, v.ctypes.data_as(DP), len(v)) != 1:
                raise RuntimeError('pvb_set_resultant refused')
        hops = 0
        if trace:
            hops = int(len(x) * 3000 / sr / 16) + 64
            if lib.pvb_resultant_trace_enable(e.h, hops) != 1:
                raise RuntimeError('trace enable refused')
        y = x.copy()
        if seq:
            n = len(y) // len(seq)
            for i, a in enumerate(seq):
                if i:
                    e.set(vb_algo=a)
                seg = y[i * n:(i + 1) * n if i < len(seq) - 1 else len(y)]
                for o in range(0, len(seg), block):
                    b = seg[o:o + block]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        else:
            for i in range(0, len(y), block):
                b = y[i:i + block]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        lat = int(e.latency()); meters = np.array(e.meters(), float)
        tr = None
        if trace:
            buf = np.empty(hops * 8 * 22, np.float64)
            n = lib.pvb_resultant_trace_copy(e.h, buf.ctypes.data_as(DP), buf.size)
            if n < 0:
                raise RuntimeError(f'trace copy returned {n}')
            tr = buf[:n * 22].reshape(n, 22).copy()
    finally:
        e.close()
    return dict(y=y, lat=lat, trace=tr, meters=meters)


def hop_time(hop):
    """Input time (s) of the analysis centre of the hop whose core index is `hop` (trace field 0 = i_h).
    Spec 3: c_h = i_h - 382 core samples; the core clock lags the 48 kHz input timeline by 1359 host samples (the decimator
    delay that the P1 harmonic-trace header [9] contains). Established empirically by an amplitude-pulse calibration on an
    established tone (diag_time3.py): in this base the LS amplitude A(h) bumps centred on the pulse and the latency-aligned
    layer envelope bumps at the same time; without the 1359 the bump would lead the pulse by 20-26 ms (acausal)."""
    return (np.asarray(hop, float) - 382) / 3000.0 + 1359 / 48000.0


def mono_al(r):
    """engine output (mono mean), shifted by the engine latency so that sample index = input time."""
    return np.asarray(r['y'], float).mean(axis=1)[r['lat']:]


def layer(r_on, r_off):
    a, b = mono_al(r_on), mono_al(r_off)
    m = min(len(a), len(b))
    return a[:m] - b[:m]


# ------------------------------------------------------------------------------------------------ signals (spec / original scripts)
def pink_gf(seconds, rms=0.03, seed=1):
    """research_r4l_gate_flicker.py recipe: 10 s of 1/f-power noise scaled to rms over the 10 s, then cut."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(10 * FS, 1 / FS)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(10 * FS)) / np.sqrt(np.maximum(f, 20)))
    return (rms * w / np.sqrt(np.mean(w ** 2)))[:int(round(seconds * FS))]


def bass_sig(seconds):
    t = np.arange(int(round(seconds * FS))) / FS; u = t % .5
    env = np.minimum(u / .008, 1) * np.exp(-u / .35)
    b = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1.0), (2, .5), (3, .18)))
    scale = .25 / np.abs(b).max()
    return scale * b, scale, u


def kick_sig(seconds):
    t = np.arange(int(round(seconds * FS))) / FS; u = t % .5
    return np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-u / .02)) / FS)


def tone_power(x, f, starts, N):
    """Rectangular-window single-frequency projection, |sum x e^{-jwn}|^2 / N^2, window = N samples from each start index
    (a unit-amplitude sine gives 0.25). NaN where the window leaves the signal."""
    n = np.arange(len(x))
    c = np.concatenate([[0], np.cumsum(x * np.exp(-2j * np.pi * f * n / FS))])
    s = np.asarray(starts, int); out = np.full(len(s), np.nan); ok = (s >= 0) & (s + N <= len(x))
    out[ok] = np.abs(c[s[ok] + N] - c[s[ok]]) ** 2 / N ** 2
    return out


def tone_power_w(x, f, starts, N, win):
    """Same as tone_power with an arbitrary window `win` (length N): |sum win*x*e^{-jwn}|^2 / (sum win)^2."""
    s = np.asarray(starts, int); idx = s[:, None] + np.arange(N)[None]
    ok = (s >= 0) & (s + N <= len(x)); out = np.full(len(s), np.nan)
    ph = np.exp(-2j * np.pi * f * np.arange(N) / FS)
    z = (x[np.where(ok[:, None], idx, 0)] * (win * ph)[None]).sum(1)
    out[ok] = (np.abs(z[ok]) / win.sum()) ** 2
    return out


def legacy_bins(x, lo, hi, starts, N):
    """Hilbert-envelope power of the band lo..hi (4th-order Butterworth, zero phase), mean over N samples from each start."""
    from scipy.signal import hilbert
    z = sosfiltfilt(butter(4, [lo, hi], btype='band', fs=FS, output='sos'), x)
    p = np.abs(hilbert(z)) ** 2; c = np.concatenate([[0], np.cumsum(p)])
    s = np.asarray(starts, int); return (c[s + N] - c[s]) / N


def dbr(a, b, floor=-100.0):
    return np.maximum(10 * np.log10((np.asarray(a) + 1e-30) / (np.asarray(b) + 1e-30)), floor)


# ------------------------------------------------------------------------------------------------ V3b
def v3b(lib, algo, cfg, tag):
    x, _, _ = bass_sig(9.0)
    r0 = render(lib, x, algo, 0.0, cfg=cfg); rd = render(lib, x, algo, -120.0, cfg=cfg)
    assert r0['lat'] == rd['lat'], (r0['lat'], rd['lat'])
    lay = layer(r0, rd); N = 960; notes = range(1, 16)
    st = lambda n: [int(round((0.5 * n + 0.040 + 0.020 * j) * FS)) for j in range(20)]
    PL = np.array([tone_power(lay, 300.0, st(n), N) for n in notes]); PI = np.array([tone_power(x, 300.0, st(n), N) for n in notes])
    pooled = dbr(PL.mean(0), PI.mean(0))                       # power-averaged over notes (cycle average), like the pre-registered recipe
    per = dbr(PL, PI)                                           # per note
    per_note_range = per.max(1) - per.min(1)
    return dict(tag=tag, lat=r0['lat'], range_pooled_db=float(pooled.max() - pooled.min()), ratio_pooled_db=pooled.round(3).tolist(),
                per_note_range_median_db=float(np.median(per_note_range)), per_note_range_max_db=float(per_note_range.max()),
                mean_ratio_db=float(pooled.mean()))


# ------------------------------------------------------------------------------------------------ V4
def v4(lib, algo, cfg, tag):
    bass, scale, _ = bass_sig(8.0); pk = pink_gf(8.0); kick = kick_sig(8.0)
    a1 = scale * 1.0                                            # true fundamental peak amplitude at the note maximum (before the decay)
    res = {}
    for nm, x in (('bass+pink', bass + pk), ('bass+kick+pink', bass + .2 * kick + pk)):
        r0 = render(lib, x, algo, 0.0, cfg=cfg, trace=(algo == 15)); rd = render(lib, x, algo, -120.0, cfg=cfg)
        lay = layer(r0, rd); N = 960
        notes = range(2, 16)
        PL = np.array([tone_power(lay, 300.0, [int(round((0.5 * n + 0.040 + 0.020 * j) * FS)) for j in range(20)], N) for n in notes])
        PI = np.array([tone_power(bass, 300.0, [int(round((0.5 * n + 0.040 + 0.020 * j) * FS)) for j in range(20)], N) for n in notes])
        r = dbr(PL, PI, -80.0)                                  # (14, 20) dB
        means = r.mean(1); med = np.median(r, axis=1, keepdims=True)
        out = dict(per_note_mean_db=means.round(3).tolist(), a_std_between_notes_db=float(np.std(means, ddof=1)),
                   b_low_bins=int((r < med - 6).sum()), b_low_frac=float((r < med - 6).sum() / r.size),
                   n_bins=int(r.size))
        # (b) window-shape sensitivity of "20 ms bins": rect (above), Hann-20 (the pre-registered suite's choice), legacy band+Hilbert boxes
        var = {}
        stl = lambda n, off: [int(round((0.5 * n + 0.040 + off + 0.020 * j) * FS)) for j in range(20)]
        hann = np.hanning(N)
        for nm_v, fn in (('rect20', lambda xx, s: tone_power(xx, 300.0, s, N)),
                         ('hann20', lambda xx, s: tone_power_w(xx, 300.0, s, N, hann)),
                         ('legacy_hilbert', lambda xx, s: legacy_bins(xx, 285.0, 315.0, s, N))):
            for off_ms in (0, 5, 10):                              # bin grid shifted by 0 / 5 / 10 ms inside the 40-440 ms span
                if nm_v == 'rect20' and off_ms == 0:
                    pass
                rr = dbr(np.array([fn(lay, stl(n, off_ms / 1000.0)) for n in notes]), np.array([fn(bass, stl(n, off_ms / 1000.0)) for n in notes]), -80.0)
                mm = np.median(rr, axis=1, keepdims=True)
                var[f'{nm_v}@+{off_ms}ms'] = int((rr < mm - 6).sum())
        out['b_variants_low_bins_of_280'] = var
        if algo == 15:
            tr = r0['trace']; hop = tr[:, F_HOP]
            sel = (tr[:, F_STATE] == ON) & (np.abs(tr[:, F_FTR] - 100.0) < 5.0) & (tr[:, F_A] > 0)
            # per hop the largest A among ON voices near 100 Hz
            hh = {}
            for h, a in zip(hop[sel], tr[sel, F_A]):
                hh[h] = max(hh.get(h, 0.0), a)
            hs = np.array(sorted(hh)); A = np.array([hh[h] for h in hs]); tch = hop_time(hs)
            res_all, per_note = [], []
            true_off = []
            for n in notes:
                t0 = 0.5 * n; m = (tch >= t0 + 0.040) & (tch < t0 + 0.450)
                if m.sum() < 5:
                    continue
                u = tch[m] - t0
                rr = 20 * np.log10(A[m]) + 20 * np.log10(np.e) * u / 0.35
                res_all.append(rr); per_note.append(rr.mean())
                true_off.append(float(np.mean(20 * np.log10(A[m] / (a1 * np.exp(-u / 0.35))))))
            allr = np.concatenate(res_all)
            pooled_global = float(np.std(allr))                                    # remainder std about ONE mean over all notes
            pooled_pernote = float(np.std(np.concatenate([q - q.mean() for q in res_all])))
            out.update(c_std_global_mean_db=pooled_global, c_std_per_note_mean_removed_db=pooled_pernote,
                       c_note_mean_spread_db=float(np.std(per_note, ddof=1)), c_abs_offset_vs_true_db=float(np.mean(true_off)),
                       c_missing_hops=int(14 * 77 - len(allr)))
        res[nm] = out
    return dict(tag=tag, lat=r0['lat'], signals=res)


# ------------------------------------------------------------------------------------------------ V0
def proc(lib, sr, algo, x, block):
    """One engine, one pass, engine destroyed afterwards (no leaked instances)."""
    x = np.ascontiguousarray(x, np.float32)
    assert x.ndim == 2 and x.shape[1] == 2, x.shape        # the engine API is interleaved stereo; (n,1) would read out of bounds
    e = T.Engine(lib, sr, vb_on=1, vb_algo=algo, ramp_ms=0)
    try:
        return e.process(x.copy(), block=block)
    finally:
        e.close()


def v0_subset(cand, ref):
    rng = np.random.default_rng(7)
    bass, _, _ = bass_sig(3.0)
    sigs = {'bass+kick+pink(3s)': bass + .2 * kick_sig(3.0) + pink_gf(3.0)}
    sigs['Track00060 30-35s'] = read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 30.0, 5.0)     # the Slakh mix is mono: duplicated to stereo there
    out = {}
    for nm, x in sigs.items():
        xs = np.asarray(x, np.float32)
        xs = np.stack([xs, xs], 1) if xs.ndim == 1 else xs
        md = {}
        for a in range(0, 15):
            log('v0 algo', a, nm)
            ya = proc(ref, FS, a, xs, 256)
            yb = proc(cand, FS, a, xs, 256)
            md[a] = float(np.max(np.abs(ya.astype(np.float64) - yb.astype(np.float64))))
        out[nm] = md
    # extra: block sizes 1, 64, 480, 4096 and 44.1 kHz on the short bass signal for algos 6, 14 (the algorithms the core touches most)
    short = np.stack([bass[:int(1.2 * FS)]] * 2, 1).astype(np.float32); extra = {}
    for blk in (1, 64, 480, 4096):
        for a in (6, 14):
            log('v0 extra block', blk, 'algo', a)
            ya = proc(ref, FS, a, short, blk)
            yb = proc(cand, FS, a, short, blk)
            extra[f'48k/b{blk}/algo{a}'] = float(np.max(np.abs(ya.astype(np.float64) - yb.astype(np.float64))))
    s44 = np.ascontiguousarray(resample_poly(short, 147, 160, axis=0), np.float32)
    for a in (6, 14):
        log('v0 extra 44.1k algo', a)
        ya = proc(ref, 44100, a, s44, 256)
        yb = proc(cand, 44100, a, s44, 256)
        extra[f'44.1k/b256/algo{a}'] = float(np.max(np.abs(ya.astype(np.float64) - yb.astype(np.float64))))
    out['extra_blocks'] = extra
    # switch 6 -> 14 -> 6 old vs new, and 6 -> 15 -> 6 (new) against the continuous 6: time-resolved
    xs = np.stack([np.asarray(sigs['Track00060 30-35s'], np.float32)] * 1, 0)[0]
    sw = {}
    ro = render(ref, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, 14, 6]); rn = render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, 14, 6])
    sw['6-14-6 old vs new maxdiff'] = float(np.max(np.abs(ro['y'].astype(np.float64) - rn['y'])))
    r3 = render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0, seq=[6, 15, 6]); rc = render(cand, xs, 6, 0.0, out_db=-5.0, tail_s=0.0)
    n = len(xs) // 3
    d = np.abs(r3['y'].astype(np.float64) - rc['y'])[:, 0]
    seg = d[2 * n:]
    bins = [(0, .1), (.1, .2), (.2, .5), (.5, 1.0), (1.0, 1.7)]
    sw['6-15-6 last segment vs continuous 6: max|diff|'] = float(seg.max())
    sw['6-15-6 diff by time after switch back (s: max|diff|)'] = {f'{a}-{b}': float(seg[int(a * FS):int(b * FS)].max()) for a, b in bins if int(a * FS) < len(seg)}
    sw['6-15-6 first 2/3 (6 then 15) vs continuous 6 max|diff| (algo 15 differs by design)'] = float(d[:2 * n].max())
    sw['6-15-6 first third (6 before the switch) max|diff|'] = float(d[:n].max())
    last = np.flatnonzero(seg > 0); sw['6-15-6 last sample with any difference after the switch back (s)'] = float(last[-1] / FS) if len(last) else None
    sw['peak of continuous 6 output'] = float(np.abs(rc['y']).max())
    out['switch'] = sw
    return out


# ------------------------------------------------------------------------------------------------ data access (own)
def band_fft(x, lo, hi):
    X_ = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / FS); X_[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X_, len(x))


def read_excerpt(path, start_s, dur_s, pad_s=0.3):
    """Stereo float32 at 48 kHz of [start_s, start_s + dur_s), clipped to +-1 (polyphase resampling of a padded segment)."""
    p = str(path)
    assert not re.search(r'slakh2100/(validation|test)(/|$)', p), 'refusing validation/test'
    info = sf.info(p); fs = info.samplerate
    s0 = max(0, int(round((start_s - pad_s) * fs))); s1 = min(info.frames, int(round((start_s + dur_s + pad_s) * fs)))
    try:
        x, _ = sf.read(p, start=s0, frames=s1 - s0, always_2d=True, dtype='float64')
    except Exception:
        x, _ = sf.read(p, always_2d=True, dtype='float64'); x = x[s0:s1]
    x = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, 1)
    if fs != FS:
        g = np.gcd(fs, FS); x = resample_poly(x, FS // g, fs // g, axis=0)
    off = int(round((start_s - s0 / fs) * FS))
    return np.clip(x[off:off + int(round(dur_s * FS))], -1, 1).astype(np.float32)


def read_midi(path):
    """Standard MIDI File -> [(start_s, end_s, pitch)] (format 0/1, PPQ, tempo map from every track)."""
    d = Path(path).read_bytes()
    assert d[:4] == b'MThd'
    hlen = struct.unpack('>I', d[4:8])[0]; fmt, ntrk, div = struct.unpack('>HHH', d[8:14]); assert not div & 0x8000
    pos = 8 + hlen; tempos = []; ev = []

    def vl(p):
        v = 0
        while True:
            b = d[p]; p += 1; v = (v << 7) | (b & 0x7F)
            if not b & 0x80:
                return v, p
    for _ in range(ntrk):
        assert d[pos:pos + 4] == b'MTrk'
        ln = struct.unpack('>I', d[pos + 4:pos + 8])[0]; p = pos + 8; end = p + ln; pos = end; tick = 0; status = 0
        while p < end:
            dt, p = vl(p); tick += dt; b = d[p]
            if b == 0xFF:
                typ = d[p + 1]; n, p = vl(p + 2)
                if typ == 0x51:
                    tempos.append((tick, int.from_bytes(d[p:p + 3], 'big')))
                p += n
            elif b in (0xF0, 0xF7):
                n, p = vl(p + 1); p += n
            else:
                if b & 0x80:
                    status = b; p += 1
                kind = status & 0xF0
                if kind in (0x80, 0x90):
                    ev.append((tick, kind == 0x90 and d[p + 1] > 0, status & 0x0F, d[p])); p += 2
                elif kind in (0xC0, 0xD0):
                    p += 1
                else:
                    p += 2
    td = {0: 500000}                                           # default 120 bpm until the first explicit tempo; an explicit one at tick 0 replaces it
    for tk, mu in tempos:
        td[tk] = mu
    tempos = sorted(td.items())
    ticks = np.array([t for t, _ in tempos], float); mus = np.array([m for _, m in tempos], float)
    secs = np.concatenate([[0], np.cumsum(np.diff(ticks) * mus[:-1] / (div * 1e6))])

    def t2s(tk):
        i = max(int(np.searchsorted(ticks, tk, side='right')) - 1, 0)
        return secs[i] + (tk - ticks[i]) * mus[i] / (div * 1e6)
    on = {}; notes = []
    for tk, is_on, ch, nt in sorted(ev, key=lambda e: (e[0], e[1])):
        if is_on:
            on.setdefault((ch, nt), []).append(tk)
        elif on.get((ch, nt)):
            t_on = on[(ch, nt)].pop(0); notes.append((t2s(t_on), t2s(tk), nt))
    return notes


def bass_stems_and_notes(track):
    tdir = SLAKH / track
    meta = (tdir / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
    stems, notes = [], []
    for sid in ids:
        p = next((q for q in (tdir / 'stems' / f'{sid}.flac', tdir / 'stems' / f'{sid}.wav') if q.exists()), None)
        if p is None:
            continue
        s, fs_ = sf.read(str(p), always_2d=True); s = s.mean(1)
        if fs_ != FS:
            g = np.gcd(fs_, FS); s = resample_poly(s, FS // g, fs_ // g)
        stems.append(s); notes += read_midi(tdir / 'MIDI' / f'{sid}.mid')
    n = max(len(s) for s in stems)
    return sum(np.pad(s, (0, n - len(s))) for s in stems), notes


def hops_of(tr):
    """voice trace rows (8 per hop) -> dict of arrays shaped (hops, 8) + hop core index (hops,) + hop input time."""
    t = tr.reshape(-1, 8, 22)
    assert np.all(t[:, :, F_HOP] == t[:, :1, F_HOP]), 'trace rows of one hop disagree'
    d = {k: t[:, :, i] for k, i in dict(voice=F_VOICE, track=F_TRACK, state=F_STATE, coast=F_COAST, ftr=F_FTR, fosc=F_FOSC, A=F_A, c=F_C,
                                        sig=F_SIG, snr=F_SNR, sub=F_SUB, a2=F_A2, a3=F_A3).items()}
    hop = t[:, 0, F_HOP]
    return d, hop, hop_time(hop)


# ------------------------------------------------------------------------------------------------ V5
def part_v5(cand, ref, cfgs):
    bz, notes = bass_stems_and_notes('Track00060')
    lo = band_fft(bz, 40, 220); B = 960; nb = len(lo) // B
    lev = 10 * np.log10(np.mean(lo[:nb * B].reshape(nb, B) ** 2, axis=1) + 1e-20); p95 = float(np.percentile(lev, 95))
    K = 400; k0 = int(round(39.0 / 0.02)); cen = 39.0 + 0.02 * (np.arange(K) + 0.5)
    ns = np.array([n[0] for n in notes]); ne = np.array([n[1] for n in notes])
    sounding = np.array([bool(np.any((ns <= c) & (c < ne))) for c in cen])
    present = sounding & (lev[k0:k0 + K] > p95 - 20)
    x = read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 36.0, 12.0)
    es_sig = band_fft(bz[36 * FS:49 * FS], 150, 600)
    i0 = 3 * FS
    es = np.array([np.sum(es_sig[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    idx = np.flatnonzero(present); tcen = (np.arange(K) + .5) * .02
    res = dict(n_present=int(present.sum()), n_sounding=int(sounding.sum()), p95_db=p95, n_notes=len(notes),
               allowed_drops_at_5pct=int(np.floor(.05 * present.sum())))
    layers = {}

    def one(lib, algo, cfg):
        r0 = render(lib, x, algo, 0.0, out_db=-5.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-5.0, cfg=cfg)
        lay = band_fft(layer(r0, rd), 150, 600)
        el = np.array([np.sum(lay[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
        return 10 * np.log10(el + 1e-20)
    layers['P1'] = one(ref, 6, None)
    for c in cfgs:
        layers[c] = one(cand, 15, CFG[c])
    es_db = 10 * np.log10(es + 1e-20)
    out = {}
    for nm, ldb in layers.items():
        ratio = ldb - es_db
        d_present = 0; d_all = 0; d_present_tight = 0; ok_localmax = np.zeros(K, bool)
        for i in idx:
            m = idx[np.abs(tcen[idx] - tcen[i]) <= .25]
            if ratio[i] < np.median(ratio[m]) - 6:
                d_present += 1
            ma = np.flatnonzero(np.abs(tcen - tcen[i]) <= .25)
            if ratio[i] < np.median(ratio[ma]) - 6:
                d_all += 1
            if ldb[i] >= np.max(ldb[m]) - 3:
                ok_localmax[i] = True
        out[nm] = dict(drops_local_present=d_present, frac_local_present=d_present / len(idx), drops_local_allbins=d_all,
                       frac_local_allbins=d_all / len(idx), layer_db=ldb, ok_localmax=ok_localmax)
    P1 = out['P1']
    for nm in out:
        if nm == 'P1':
            continue
        sel = np.flatnonzero(present & P1['ok_localmax'])
        d = out[nm]['layer_db'][sel] - P1['layer_db'][sel]
        out[nm]['v5b_median_db'] = float(np.median(d)); out[nm]['v5b_n'] = int(len(sel))
    for nm in out:
        out[nm].pop('layer_db'); out[nm].pop('ok_localmax')
    res.update(out)
    return res


# ------------------------------------------------------------------------------------------------ V3c
STEP_NOTES = [98.0, 104.0] * 10 + [98.0, 110.0] * 10
STEP_DUR = 0.125


def step_line(snr_db):
    ph = np.linspace(0, 2 * np.pi, 400001)
    tpk = float(np.abs(np.sin(ph) + .5 * np.sin(2 * ph) + .18 * np.sin(3 * ph)).max())
    scale = .25 / tpk
    n_notes = len(STEP_NOTES); m = int(round(STEP_DUR * FS)); clean = np.zeros(n_notes * m)
    for i, f in enumerate(STEP_NOTES):
        k = np.arange(m); u = k / FS
        env = np.clip(np.minimum(np.minimum(k / (.008 * FS), 1.0), (m - k) / (.008 * FS)), 0, 1)
        clean[i * m:(i + 1) * m] = scale * env * (np.sin(2 * np.pi * f * u) + .5 * np.sin(2 * np.pi * 2 * f * u) + .18 * np.sin(2 * np.pi * 3 * f * u))
    n = max(10 * FS, len(clean)); n += n % 2
    rng = np.random.default_rng(1); fr = np.fft.rfftfreq(n, 1 / FS)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(fr, 20)), n); w = (w / np.sqrt(np.mean(w ** 2)))[:len(clean)]
    bp = lambda s: float(np.mean(band_fft(s, 80, 200) ** 2))
    g = np.sqrt(bp(clean) / (bp(w) * 10 ** (snr_db / 10.0)))
    return clean, clean + g * w


def part_v3c(cand, ref, cfgs):
    clean, noisy = step_line(25.0)
    idx = [i for i in range(2, 40) if i != 20]
    res = {}

    def ratio_stats(lib, algo, cfg, key):
        r0 = render(lib, noisy, algo, 0.0, out_db=-5.0, cfg=cfg, trace=(algo == 15)); rd = render(lib, noisy, algo, -120.0, out_db=-5.0, cfg=cfg)
        lay = layer(r0, rd); rngs = []; low = 0; rngs_hann = []; low_hann = 0; N = 960; hann = np.hanning(N)
        for i in idx:
            t0 = i * STEP_DUR; f3 = 3 * STEP_NOTES[i]
            st = [int(round((t0 + a) * FS)) for a in (.015, .035, .055, .075, .090)]
            r = dbr(tone_power(lay, f3, st, N), tone_power(clean, f3, st, N), -80)
            rngs.append(float(r.max() - r.min())); low += int(np.any(r < np.median(r) - 6))
            st2 = [int(round((t0 + a) * FS)) - 0 for a in (.015, .035, .055, .075, .090)]
            rh = dbr(tone_power_w(lay, f3, st2, N, hann), tone_power_w(clean, f3, st2, N, hann), -80)
            rngs_hann.append(float(rh.max() - rh.min())); low_hann += int(np.any(rh < np.median(rh) - 6))
        out = dict(range_rect_median_db=float(np.median(rngs)), range_rect_max_db=float(np.max(rngs)), lowbin_notes_rect=low,
                   range_hann_median_db=float(np.median(rngs_hann)), lowbin_notes_hann=low_hann, worst_notes_rect=[idx[j] for j in np.argsort(rngs)[-3:]])
        if algo == 15:
            d, hop, tc = hops_of(r0['trace'])
            ent_dom, ent_any, ent_dom_prev = [], [], []
            for i in idx:
                t0 = i * STEP_DUR; fn = STEP_NOTES[i]
                h0 = int(np.searchsorted(tc, t0)); h1 = int(np.searchsorted(tc, t0 + STEP_DUR))
                e_dom = e_any = np.inf
                for h in range(h0, h1):
                    on = np.flatnonzero(d['state'][h] == ON)
                    if not len(on):
                        continue
                    wgt = d['A'][h][on] * d['c'][h][on] * d['sig'][h][on]
                    top = on[np.argmax(wgt)]
                    if e_dom == np.inf and abs(d['fosc'][h][top] - fn) <= .02 * fn:
                        e_dom = tc[h] - t0
                    if e_any == np.inf and np.any(np.abs(d['fosc'][h][on] - fn) <= .02 * fn):
                        e_any = tc[h] - t0
                ent_dom.append(e_dom); ent_any.append(e_any)
            ed = np.array(ent_dom) * 1000; ea = np.array(ent_any) * 1000
            hop_ms = 16 / 3000 * 1000
            out.update(enter_dom_median_ms=float(np.median(ed)), enter_any_median_ms=float(np.median(ea)),
                       enter_dom_median_ms_minus_one_hop=float(np.median(ed) - hop_ms), enter_dom_p90_ms=float(np.percentile(np.where(np.isinf(ed), 1e3, ed), 90)),
                       enter_miss=int(np.isinf(ed).sum()), enter_dom_semitone_median_ms=float(np.median(ed[[k for k, i in enumerate(idx) if i < 20]])),
                       enter_dom_wholetone_median_ms=float(np.median(ed[[k for k, i in enumerate(idx) if i > 20]])))
        return out
    res['P1'] = ratio_stats(ref, 6, None, 'P1')
    for c in cfgs:
        res[c] = ratio_stats(cand, 15, CFG[c], c)
    return res


# ------------------------------------------------------------------------------------------------ sanity (task 4)
def low_notes_sig():
    n = int(round(5.3 * FS)); x = np.zeros(n)
    for f, a, b in ((35.0, 0.3, 2.3), (45.0, 2.8, 4.8)):
        n0, n1 = int(round(a * FS)), int(round(b * FS)); k = np.arange(n1 - n0); u = k / FS
        env = np.minimum(np.minimum(k / (.008 * FS), 1.0), (n1 - n0 - k) / (.008 * FS))
        x[n0:n1] = env * .1 * (np.sin(2 * np.pi * f * u) + np.sin(2 * np.pi * 2 * f * u))
    return x


def part_sanity(cand, ref, cfgs):
    bass, _, _ = bass_sig(8.0)
    t60 = read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 36.0, 12.0)
    sigs = {'bass+kick+pink': bass + .2 * kick_sig(8.0) + pink_gf(8.0), 'T60 36-48s': t60,
            'T40 30-40s': read_excerpt(SLAKH / 'Track00040' / 'mix.flac', 30.0, 10.0), 'LOGOFF 37-49s': read_excerpt(LOGOFF, 37.0, 12.0),
            'pink -30dBFS 10s': pink_gf(10.0, rms=10 ** (-30 / 20)), 'step line 25dB': step_line(25.0)[1], 'low notes 35/45Hz': low_notes_sig(),
            'T60 3s + 3s digital silence': np.concatenate([t60[:3 * FS], np.zeros((3 * FS, 2), np.float32)]),
            'T60 38s fullscale-normalised': (t60 / max(np.abs(t60).max(), 1e-9) * 0.999).astype(np.float32)}
    hp_sos = butter(4, 2000.0, btype='high', fs=FS, output='sos')
    out = {}
    ref_lay = {}
    for sn, x in sigs.items():
        out[sn] = {}
        for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
            r0 = render(lib, x, algo, 0.0, out_db=-18.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-18.0, cfg=cfg)
            y0 = np.asarray(r0['y'], float); yd = np.asarray(rd['y'], float)
            lay = layer(r0, rd); lb = band_fft(lay, 150, 600); hp = sosfilt(hp_sos, lay)
            e_lb = float(np.mean(lb ** 2)); e_hp = float(np.mean(hp ** 2))
            B = int(.1 * FS); nb = len(lb) // B
            e_bins = np.array([np.mean(lb[k * B:(k + 1) * B] ** 2) for k in range(nb)])
            if nm == 'P1':
                ref_lay[sn] = e_bins
            row = dict(finite=bool(np.all(np.isfinite(y0)) and np.all(np.isfinite(yd))), nan_events_meter=float(r0['meters'][T.M['NAN_EVENTS']]),
                       peak_dry_dbfs=float(20 * np.log10(np.abs(yd).max() + 1e-12)), peak_wet_dbfs=float(20 * np.log10(np.abs(y0).max() + 1e-12)),
                       layer_150_600_db=float(10 * np.log10(e_lb + 1e-30)), hf_over_layer_db=float(10 * np.log10(e_hp / max(e_lb, 1e-30) + 1e-30)),
                       hf_peak=float(np.abs(hp).max()), layer_peak=float(np.abs(lay).max()), layer_exact_zero_frac=float(np.mean(lay == 0)))
            row['peak_wet_at_outdb_minus5_dbfs'] = row['peak_wet_dbfs'] + 13.0
            # click index: largest ratio of the HF-highpassed layer to the local (20 ms) rms of the 150-600 Hz layer, where that rms is non-negligible
            W = int(.02 * FS); loc = np.sqrt(np.convolve(lb ** 2, np.ones(W) / W, 'same')) + 1e-9
            row['click_index'] = float(np.max(np.abs(hp)[W:-W] / loc[W:-W]))
            if nm != 'P1':
                P1b = ref_lay[sn][:nb]; m = P1b > np.median(P1b) / 10 if P1b.max() > 0 else np.zeros(nb, bool)
                rel = 10 * np.log10((e_bins[:len(P1b)] + 1e-30) / (P1b + 1e-30))
                row['layer_re_P1_db_total'] = row['layer_150_600_db'] - out[sn]['P1']['layer_150_600_db']
                row['bins_P1_active'] = int(m.sum()); row['bins_core_below_P1_minus_40dB'] = int(np.sum(m & (rel < -40)))
                row['bins_core_above_P1_plus_10dB'] = int(np.sum(m & (rel > 10)))
            out[sn][nm] = row
    return out


# ------------------------------------------------------------------------------------------------ V7d investigation
def part_v7d(cand, ref, cfgs):
    lg = read_excerpt(LOGOFF, 37.0, 12.0)
    res = {}
    hp_sos = butter(4, 2000.0, btype='high', fs=FS, output='sos')
    for out_db in (-5.0, -18.0):
        series = {}
        for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), 'A': (cand, 15, CFG['A']), 'B': (cand, 15, CFG['B'])}.items():
            r0 = render(lib, lg, algo, 0.0, out_db=out_db, cfg=cfg); rd = render(lib, lg, algo, -120.0, out_db=out_db, cfg=cfg)
            lay = band_fft(layer(r0, rd), 150, 600)
            if nm == 'P1':
                dry = mono_al(rd)
            series[nm] = lay
        W = int(.025 * FS); t_edges = np.arange(6.5, 8.51, 0.025)
        tab = {}
        for nm, lay in series.items():
            tab[nm] = [10 * np.log10(np.mean(lay[int(a * FS):int(a * FS) + W] ** 2) + 1e-30) for a in t_edges[:-1]]
        hf = [10 * np.log10(np.mean(sosfilt(hp_sos, dry)[int(a * FS):int(a * FS) + W] ** 2) + 1e-30) for a in t_edges[:-1]]
        res[f'out_db{out_db:g}'] = dict(t_start_s=t_edges[:-1].round(3).tolist(), hf_dry_db=np.round(hf, 1).tolist(), **{k: np.round(v, 1).tolist() for k, v in tab.items()})
        # ±50 ms energy around the nominal hits and around the strongest dry HF transient near them
        for hit in (4.12, 4.73):
            c0 = 3.0 + hit
            seg = [i for i, a in enumerate(t_edges[:-1]) if abs(a + .0125 - c0) < .2]
            ih = seg[int(np.argmax([hf[i] for i in seg]))]
            c_hf = t_edges[ih] + .0125
            for nm, lay in series.items():
                for cc, lab in ((c0, 'nominal'), (c_hf, 'dryHFpeak')):
                    e = 10 * np.log10(np.sum(lay[int((cc - .05) * FS):int((cc + .05) * FS)] ** 2) + 1e-30)
                    res[f'out_db{out_db:g}'][f'{nm}_hit{hit}_{lab}_c{cc:.3f}_db'] = float(e)
    return res


# ------------------------------------------------------------------------------------------------ V7a (literal: FFT energy > 1.5 kHz over 150-600 Hz)
def part_v7a(cand, ref, cfgs):
    bass, _, _ = bass_sig(8.0)
    sigs = {'T60': (read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 36.0, 12.0), (3, 11)),
            'LOGOFF': (read_excerpt(LOGOFF, 37.0, 12.0), (3, 11)),
            'bass+kick+pink': (bass + .2 * kick_sig(8.0) + pink_gf(8.0), (1, 7))}
    out = {}
    for sn, (x, (a, b)) in sigs.items():
        out[sn] = {}
        for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
            r0 = render(lib, x, algo, 0.0, out_db=-18.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-18.0, cfg=cfg)
            seg = layer(r0, rd)[int(a * FS):int(b * FS)]
            P = np.abs(np.fft.rfft(seg)) ** 2; f = np.fft.rfftfreq(len(seg), 1 / FS)
            out[sn][nm] = float(10 * np.log10(P[f > 1500].sum() / P[(f >= 150) & (f <= 600)].sum()))
    return out


# ------------------------------------------------------------------------------------------------ V3h (rise / tail times)
def _note(f, m, scale):
    k = np.arange(m); u = k / FS
    env = np.minimum(np.minimum(k / (.008 * FS), 1.0), (m - k) / (.008 * FS))
    return scale * env * (np.sin(2 * np.pi * f * u) + .5 * np.sin(2 * np.pi * 2 * f * u) + .18 * np.sin(2 * np.pi * 3 * f * u))


def _box_rms(x, ms):
    L = max(1, int(ms * FS / 1000)); c = np.concatenate([[0], np.cumsum(x ** 2)])
    n = len(x); lo = np.clip(np.arange(n) - L // 2, 0, n); hi = np.clip(np.arange(n) - L // 2 + L, 0, n)
    return np.sqrt(np.maximum((c[hi] - c[lo]) / np.maximum(hi - lo, 1), 0))


def part_v3h(cand, ref, cfgs):
    from scipy.signal import hilbert
    ph = np.linspace(0, 2 * np.pi, 400001); tpk = float(np.abs(np.sin(ph) + .5 * np.sin(2 * ph) + .18 * np.sin(3 * ph)).max()); scale = .25 / tpk
    m = int(round(STEP_DUR * FS)); per = 2 * STEP_DUR; nn = len(STEP_NOTES)
    clean = np.zeros(int(round(nn * per * FS))); on = np.zeros(len(clean), bool)
    for i, f in enumerate(STEP_NOTES):
        n0 = int(round(i * per * FS)); clean[n0:n0 + m] = _note(f, m, scale); on[n0:n0 + m] = True
    n = max(10 * FS, len(clean)); n += n % 2
    rng = np.random.default_rng(1); fr = np.fft.rfftfreq(n, 1 / FS)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(fr, 20)), n); w = (w / np.sqrt(np.mean(w ** 2)))[:len(clean)]
    bp = lambda s, mask=None: float(np.mean((band_fft(s, 80, 200) ** 2)[mask] if mask is not None else band_fft(s, 80, 200) ** 2))
    sigs = {}
    for snr in (25.0, 6.0):
        g = np.sqrt(bp(clean, on) / (bp(w) * 10 ** (snr / 10.0))); sigs[f'line{snr:g}'] = clean + g * w
    # isolated 1 s note
    bare = np.zeros(int(3.5 * FS)); bare[int(.5 * FS):int(1.5 * FS)] = _note(100.0, int(1.0 * FS), scale); sigs['bare'] = bare
    out = {}
    for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
        out[nm] = {}
        for sn, x in sigs.items():
            r0 = render(lib, x, algo, 0.0, out_db=-5.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-5.0, cfg=cfg)
            lay = layer(r0, rd)
            res = {}
            for envname, env in (('rms5', _box_rms(lay, 5.0)), ('hilbert_bp_rms5', _box_rms(np.abs(hilbert(band_fft(lay, 150, 600))), 5.0))):
                if sn == 'bare':
                    refv = float(np.mean(env[int(1.2 * FS):int(1.45 * FS)]))
                    def first(seg, thr, above=True):
                        ok = seg >= thr if above else seg <= thr
                        return float(np.argmax(ok) / FS * 1000) if ok.any() else float('inf')
                    res[envname] = dict(rise50=first(env[int(.5 * FS):int(.9 * FS)], .5 * refv), rise90=first(env[int(.5 * FS):int(.9 * FS)], .9 * refv),
                                        tail=first(env[int(1.5 * FS):int(3.0 * FS)], .1 * refv, above=False))
                else:
                    r50, r90, tl = [], [], []
                    for i in range(2, 40):
                        t0 = i * per; refv = float(np.mean(env[int((t0 + .06) * FS):int((t0 + .11) * FS)]))
                        seg = env[int(t0 * FS):int(t0 * FS) + int(.125 * FS)]
                        for fr_, lst in ((.5, r50), (.9, r90)):
                            ok = seg >= fr_ * refv; lst.append(float(np.argmax(ok) / FS * 1000) if ok.any() and refv > 1e-9 else float('inf'))
                        sg = env[int((t0 + .125) * FS):int((t0 + .125) * FS) + int(.12 * FS)]; ok = sg <= .1 * refv
                        tl.append(float(np.argmax(ok) / FS * 1000) if ok.any() and refv > 1e-9 else float('inf'))
                    res[envname] = dict(rise50=float(np.median(r50)), rise90=float(np.median(r90)), tail=float(np.median(tl)),
                                        rise90_p90=float(np.percentile(np.where(np.isinf(r90), 1e3, r90), 90)), tail_p90=float(np.percentile(np.where(np.isinf(tl), 1e3, tl), 90)))
            out[nm][sn] = res
    return out


# ------------------------------------------------------------------------------------------------ robustness of algo 15: block sizes, sample rates, parameter extremes
def part_blocks(cand, ref, cfgs):
    t60 = read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 36.0, 4.0)
    out = {}
    for algo, lib, cfg in ((6, ref, None), (15, cand, CFG['A']), (15, cand, CFG['C'])):
        ys = {}
        for blk in (256, 1, 64, 480, 4096, 7):
            e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
            if algo == 15:
                v = np.array([(cfg or {}).get(n, d) for n, d in zip(PNAMES, PDEF)], np.float64); assert lib.pvb_set_resultant(e.h, v.ctypes.data_as(DP), len(v)) == 1
            ys[blk] = e.process(t60.copy(), block=blk); e.close()
        tag = f'algo{algo}' + ('' if cfg is None else '/' + ('A' if cfg is CFG['A'] else 'C'))
        out[tag] = {f'block{b}_vs_256_maxdiff': float(np.max(np.abs(ys[b].astype(np.float64) - ys[256]))) for b in ys if b != 256}
        out[tag]['finite'] = bool(all(np.all(np.isfinite(y)) for y in ys.values()))
    # 44.1 kHz and 96 kHz operation of algo 15 (finite, layer present)
    for sr in (44100, 96000, 32000):
        g = np.gcd(sr, FS); xs = np.ascontiguousarray(resample_poly(t60, sr // g, FS // g, axis=0), np.float32)
        res = {}
        for nm, lvl in (('on', 0.0), ('off', -120.0)):
            e = T.Engine(cand, sr, vb_on=1, vb_algo=15, ramp_ms=0, vb_level_db=lvl, out_db=-18.0)
            v = np.array(PDEF, np.float64); assert cand.pvb_set_resultant(e.h, v.ctypes.data_as(DP), len(v)) == 1
            res[nm] = e.process(xs.copy(), block=256).astype(np.float64); lat = e.latency(); e.close()
        lay = (res['on'] - res['off']).mean(1)
        out[f'sr{sr}'] = dict(finite=bool(np.all(np.isfinite(res['on']))), layer_rms_db=float(10 * np.log10(np.mean(lay ** 2) + 1e-30)), latency=int(lat),
                              dry_rms_db=float(10 * np.log10(np.mean(res['off'] ** 2) + 1e-30)))
    # parameter extremes through the host API (accepted ranges of spec 5.8): finite output, no crash
    ext = {}
    lo = [0, 0, 0, 6, 10, 0, 1, 5, 0, 0, .5, 16, 0, .01, 0, 20]; hi = [1, 12, 1, 30, 40, 20, 100, 300, 1, 1, 3, 191, 96, 3.2, 1, 2000]
    for nm, vec in (('all_low', lo), ('all_high', hi)):
        e = T.Engine(cand, FS, vb_on=1, vb_algo=15, ramp_ms=0, out_db=-18.0)
        v = np.array(vec, np.float64); ok = cand.pvb_set_resultant(e.h, v.ctypes.data_as(DP), len(v))
        y = e.process(t60.copy(), block=256); e.close()
        ext[nm] = dict(accepted=int(ok), finite=bool(np.all(np.isfinite(y))), peak=float(np.abs(y).max()))
    e = T.Engine(cand, FS, vb_on=1, vb_algo=15, ramp_ms=0)
    bad = np.array([2, 0, 0, 15, 22, 6, 8, 30, .2, .9, 1, 30, 24, .12, 0, 200], np.float64); ext['voicing=2_refused'] = int(cand.pvb_set_resultant(e.h, bad.ctypes.data_as(DP), len(bad)))
    e.close()
    out['param_extremes'] = ext
    return out


# ------------------------------------------------------------------------------------------------ V1b / V2 on the steady 100 Hz tone
def part_v2(cand, ref, cfgs):
    t = np.arange(int(4.0 * FS)) / FS
    ph = np.linspace(0, 2 * np.pi, 400001); tpk = float(np.abs(np.sin(ph) + .5 * np.sin(2 * ph) + .18 * np.sin(3 * ph)).max())
    x = (np.sin(2 * np.pi * 100 * t) + .5 * np.sin(2 * np.pi * 200 * t) + .18 * np.sin(2 * np.pi * 300 * t)) * (10 ** (-12 / 20) / tpk) * np.minimum(t / .008, 1)
    out = {}
    for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
        r0 = render(lib, x, algo, 0.0, out_db=-18.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-18.0, cfg=cfg)
        lay = layer(r0, rd); dry = mono_al(rd)[:len(lay)]
        res = {}
        for k in (2, 3):
            N = int(.2 * FS); w = np.hanning(N); n = np.arange(N); ph_ = []
            for c in np.arange(.7, 3.5, .1):
                s = int(c * FS)
                e = np.exp(-2j * np.pi * 100 * k * n / FS)
                ph_.append(np.angle(np.sum(lay[s:s + N] * w * e) * np.conj(np.sum(dry[s:s + N] * w * e))))
            res[f'dphi_k{k}_mean_rad'] = float(np.angle(np.mean(np.exp(1j * np.array(ph_)))))
        sel = slice(int(.7 * FS), int(3.5 * FS))
        res['layer_150_600_db'] = float(10 * np.log10(np.mean(band_fft(lay, 150, 600)[sel] ** 2) + 1e-30))
        out[nm] = res
    for nm in out:
        out[nm]['layer_re_P1_db'] = out[nm]['layer_150_600_db'] - out['P1']['layer_150_600_db']
    return out


# ------------------------------------------------------------------------------------------------ V3a (peak of the cycle-averaged 150-600 Hz output power)
def part_v3a(cand, ref, cfgs):
    from scipy.signal import hilbert
    x, _, _ = bass_sig(9.0)
    out = {}
    for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
        r0 = render(lib, x, algo, 0.0, out_db=-5.0, cfg=cfg); rd = render(lib, x, algo, -120.0, out_db=-5.0, cfg=cfg)
        res = {}
        for what, sig in (('output', mono_al(r0)[:8 * FS]), ('layer', layer(r0, rd)[:8 * FS])):
            z = band_fft(sig, 150, 600); p = np.abs(hilbert(z)) ** 2
            cyc = p[:16 * (FS // 2)].reshape(16, FS // 2)[1:].mean(axis=0)
            sm = np.convolve(cyc, np.ones(48) / 48, 'same')[::48]               # 1 ms resolution
            pk = int(np.argmax(sm[:400]))
            res[what] = dict(peak_ms=pk, rise50_ms=int(np.argmax(sm >= .5 * sm[pk])), fall10db_ms=int(pk + np.argmax(sm[pk:] <= sm[pk] * .1)))
        out[nm] = res
    return out


# ------------------------------------------------------------------------------------------------ V7d with the hits placed on the OUTPUT timeline
def part_v7e(cand, ref, cfgs):
    lg = read_excerpt(LOGOFF, 37.0, 12.0)
    out = {}
    lat_s = 7140 / FS
    for nm, (lib, algo, cfg) in {'P1': (ref, 6, None), **{c: (cand, 15, CFG[c]) for c in cfgs}}.items():
        r0 = render(lib, lg, algo, 0.0, out_db=-5.0, cfg=cfg); rd = render(lib, lg, algo, -120.0, out_db=-5.0, cfg=cfg)
        lay = band_fft(layer(r0, rd), 150, 600)
        row = {}
        for hit in (4.12, 4.73):
            for lab, c in (('input_time', 3.0 + hit), ('output_time_minus_latency', 3.0 + hit - lat_s)):
                row[f'{hit}@{lab}'] = float(10 * np.log10(np.sum(lay[int((c - .05) * FS):int((c + .05) * FS)] ** 2) + 1e-30))
        out[nm] = row
    return out


# ------------------------------------------------------------------------------------------------ V9 (core side, voice trace)
def part_v9(cand, ref, cfgs):
    out = {}
    pk = pink_gf(10.0, rms=10 ** (-30 / 20))
    t60 = read_excerpt(SLAKH / 'Track00060' / 'mix.flac', 40.0, 6.0)
    z = lambda s: np.zeros((int(s * FS), 2), np.float32)
    comp = np.concatenate([t60[:3 * FS], z(2), np.stack([pk[:4 * FS]] * 2, 1).astype(np.float32), z(2), t60[3 * FS:]]).astype(np.float32)
    for c in cfgs:
        for nm, x, (lo, hi) in (('pink_only', pk, (0.5, 9.9)), ('music_silence_noise', comp, (4.0, 10.9))):
            r = render(cand, x, 15, 0.0, out_db=-5.0, cfg=CFG[c], trace=True)
            d, hop, tc = hops_of(r['trace'])
            w = (tc >= lo) & (tc <= hi)
            st = d['state'][w]; vid = d['voice'][w]
            n_on_ids = len(np.unique(vid[st == ON])); n_cand_ids = len(np.unique(vid[st == CAND_]))
            # births: id enters ON from absent/CAND between consecutive hops
            births = 0; prev = {}
            for h in np.flatnonzero(w):
                cur = {int(v): int(s) for v, s in zip(d['voice'][h], d['state'][h]) if s > 0}
                births += sum(1 for v, s in cur.items() if s == ON and prev.get(v, 0) in (0, CAND_))
                prev = cur
            out[f'{c}/{nm}'] = dict(on_voice_ids=n_on_ids, cand_voice_ids=n_cand_ids, births=births, births_per_s=births / (hi - lo))
    return out


# ------------------------------------------------------------------------------------------------ V6 both sides with my own P1 harmonic-trace parse
HF_, HHEAD_, HTRK_, HTRKS_, HROWS_ = 700, 28, 56, 12, 72        # P1 harmonic trace row layout (pvb_vb52.cpp beginHarmonic52 / traceTrack52)


def p1_harmonic(lib, x, block=256):
    """P1 (algo 6) with the harmonic diagnostic capture: returns (hop analysis-centre time in input seconds, tracks array (hops, 12, 56))."""
    lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]
    lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]; lib.pvb_copy_harmonic.restype = C.c_int
    x = np.asarray(x, np.float32); assert x.ndim == 2 and x.shape[1] == 2
    y = np.ascontiguousarray(np.concatenate([x, np.zeros((int(.3 * FS), 2), np.float32)])).copy()
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, ramp_ms=0)
    try:
        lib.pvb_set_diagnostic_capture(e.h, 1)
        buf = np.empty(HROWS_ * HF_, np.float32); rows = []
        for off in range(0, len(y), block):
            b = y[off:off + block]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
            n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
            if n > 0:
                d = buf[:n * HF_].reshape(n, HF_).copy(); d[:, 0] += off; rows.append(d)
    finally:
        e.close()
    R = np.vstack(rows)
    return (R[:, 0].astype(float) + R[:, 9]) / FS, R[:, HHEAD_:].reshape(len(R), HTRKS_, HTRK_)


def _v6_eval(rf, tc, vf, w, right, harm_hist=None):
    """rf: reference dict. vf, w, right: (hops, slots) voice frequency, weight, 'right voice' flag. Returns loud, covered, w_total, w_wrong."""
    cents = lambda f, g: np.abs(1200 * np.log2(np.maximum(f, 1e-9) / g))
    f0 = np.full(len(tc), np.nan)
    for i, t in enumerate(tc):
        m = (rf['ss'] <= t) & (t < rf['es'])
        if m.any():
            f0[i] = 440 * 2 ** ((rf['ps'][m].min() + rf['tp'] - 69) / 12)
    lev = np.array([10 * np.log10(np.mean(rf['lo40'][max(0, int(t * FS) - 1024):int(t * FS) + 1024] ** 2) + 1e-20) for t in tc])
    act = np.isfinite(f0) & (tc > .5)
    loud = act & (lev > (np.percentile(lev[act], 95) - 10 if act.any() else 0))
    cov = 0
    for h in np.flatnonzero(loud):
        fv = vf[h][right[h]]
        if len(fv) and any(np.any(cents(fv, k * f0[h]) <= 50) for k in (1, 2, 3)):
            cov += 1
    wsum = wwrong = 0.0
    for h in np.flatnonzero(tc > .5):
        sel = np.flatnonzero(w[h] > 0)
        if not len(sel):
            continue
        t = tc[h]
        pa = np.r_[rf['ap'][(rf['as_'] <= t) & (t < rf['ae'])], rf['ps'][(rf['ss'] <= t) & (t < rf['es'])] + rf['tp']]
        fn = 440 * 2 ** ((pa - 69) / 12); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
        for j in sel:
            bad = (not len(tgt)) or np.min(cents(vf[h][j], tgt)) > 50
            wsum += w[h][j]; wwrong += w[h][j] * bad
    return int(loud.sum()), int(cov), float(wsum), float(wwrong)


def part_v6both(cand, ref, cfgs):
    suite = json.load(open(HOME / 'r3a-dev/core_results/verify_A/results.json'))['metrics']['V6']
    names = [t['name'] for t in suite['per_track']]; tps = {t['name']: t['tp'] for t in suite['per_track']}
    tot = {k: dict(loud=0, cov=0, w=0.0, bad=0.0) for k in ('P1', 'A')}; per = []
    for name in names:
        bz, bnotes = bass_stems_and_notes(name)
        allm = sorted((SLAKH_MIDI / name / 'MIDI').glob('*.mid')); allnotes = [n for m in allm for n in read_midi(m)]
        rf = dict(tp=tps[name], ps=np.array([n[2] for n in bnotes], float), ss=np.array([n[0] for n in bnotes]), es=np.array([n[1] for n in bnotes]),
                  ap=np.array([n[2] for n in allnotes], float), as_=np.array([n[0] for n in allnotes]), ae=np.array([n[1] for n in allnotes]),
                  lo40=band_fft(bz[:31 * FS], 40, 220))
        x = read_excerpt(SLAKH / name / 'mix.flac', 0.0, 30.0)
        # core A
        r = render(cand, x, 15, 0.0, out_db=-5.0, cfg=CFG['A'], trace=True)
        d, hop, tc = hops_of(r['trace'])
        right = (d['state'] == ON) & ~(d['sub'] > .5) & (d['c'] > .5)
        w = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
        a = _v6_eval(rf, tc, d['fosc'], w, right)
        # P1 (own harmonic-trace parse): voice = track with state > 0; right = fade >= 0.5; weight (a*fade)^2
        tc1, ts = p1_harmonic(ref, x)
        valid = ts[:, :, 1] > 0; fade = np.where(valid, ts[:, :, 7], 0.0); aa = np.where(valid, ts[:, :, 4], 0.0)
        b = _v6_eval(rf, tc1, np.where(valid, ts[:, :, 2], 0.0), (aa * fade) ** 2, valid & (fade >= .5))
        per.append(dict(name=name, P1=dict(loud=b[0], cov=b[1], w=b[2], bad=b[3]), A=dict(loud=a[0], cov=a[1], w=a[2], bad=a[3])))
        for k, v in (('P1', b), ('A', a)):
            tot[k]['loud'] += v[0]; tot[k]['cov'] += v[1]; tot[k]['w'] += v[2]; tot[k]['bad'] += v[3]
    res = {k: dict(coverage=v['cov'] / max(v['loud'], 1), wrong_share=v['bad'] / max(v['w'], 1e-30)) for k, v in tot.items()}
    res['per_track'] = per
    return res


# ------------------------------------------------------------------------------------------------ V6 (core side only)
def part_v6(cand, ref, cfgs):
    suite = json.load(open(HOME / 'r3a-dev/core_results/verify_A/results.json'))['metrics']['V6']
    names = [t['name'] for t in suite['per_track']]; tps = {t['name']: t['tp'] for t in suite['per_track']}   # octave tp: an INPUT taken from the suite (YIN agreement)
    res = {}
    cents = lambda f, g: np.abs(1200 * np.log2(np.maximum(f, 1e-9) / g))
    for cfgname in cfgs[:1]:                                   # config A only (V6 is a pass/fail item for A/B; C/D identical tracker)
        tot = dict(loud=0, cov=0, w_all=0.0, w_wrong=0.0, w_wrong_by_state={ON: 0.0, CAND_: 0.0, REL: 0.0}, w_by_state={ON: 0.0, CAND_: 0.0, REL: 0.0})
        harm_hist = {}
        per = []
        for name in names:
            tdir = SLAKH / name
            try:
                bz, bnotes = bass_stems_and_notes(name)
            except Exception as ex:
                per.append(dict(name=name, error=repr(ex))); continue
            allm = sorted((SLAKH_MIDI / name / 'MIDI').glob('*.mid'))
            meta = (SLAKH_MIDI / name / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
            parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
            drum_ids = {parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'is_drum:\s*true', parts[i + 1])}
            allnotes = [n for m in allm for n in read_midi(m)]
            tp = tps[name]
            x = read_excerpt(tdir / 'mix.flac', 0.0, 30.0)
            r = render(cand, x, 15, 0.0, out_db=-5.0, cfg=CFG[cfgname], trace=True)
            d, hop, tc = hops_of(r['trace'])
            ps = np.array([n[2] for n in bnotes], float); ss = np.array([n[0] for n in bnotes]); es = np.array([n[1] for n in bnotes])
            f0 = np.full(len(tc), np.nan)
            for i, t in enumerate(tc):
                m = (ss <= t) & (t < es)
                if m.any():
                    f0[i] = 440 * 2 ** ((ps[m].min() + tp - 69) / 12)
            lo40 = band_fft(bz[:31 * FS], 40, 220)
            lev = np.array([10 * np.log10(np.mean(lo40[max(0, int(t * FS) - 1024):int(t * FS) + 1024] ** 2) + 1e-20) for t in tc])
            act = np.isfinite(f0) & (tc > .5)
            loud = act & (lev > (np.percentile(lev[act], 95) - 10 if act.any() else 0))
            vf = d['fosc']; stt = d['state']; sub = d['sub'] > .5; cc = d['c']
            right = (stt == ON) & ~sub & (cc > .5)
            cov = 0
            for h in np.flatnonzero(loud):
                fv = vf[h][right[h]]
                if len(fv) and any(np.any(cents(fv, k * f0[h]) <= 50) for k in (1, 2, 3)):
                    cov += 1
            # wrong-note weight
            ap = np.array([n[2] for n in allnotes], float); as_ = np.array([n[0] for n in allnotes]); ae = np.array([n[1] for n in allnotes])
            w = (d['A'] * d['c'] * d['sig']) ** 2
            wsum = wwrong = 0.0
            for h in np.flatnonzero(tc > .5):
                sel = np.flatnonzero((w[h] > 0) & (stt[h] > 0))
                if not len(sel):
                    continue
                t = tc[h]
                pa = np.r_[ap[(as_ <= t) & (t < ae)], ps[(ss <= t) & (t < es)] + tp]
                fn = 440 * 2 ** ((pa - 69) / 12)
                tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
                for j in sel:
                    wv = w[h][j]; s_ = int(stt[h][j])
                    bad = (not len(tgt)) or np.min(cents(vf[h][j], tgt)) > 50
                    wsum += wv; wwrong += wv * bad; tot['w_by_state'][s_] += wv; tot['w_wrong_by_state'][s_] += wv * bad
                    if bad and len(fn):
                        # which harmonic of the nearest sounding note is the voice? (diagnostic)
                        ratio = vf[h][j] / fn
                        k = np.argmin(np.abs(np.log2(ratio / np.round(ratio).clip(1))))
                        m_ = int(np.round(ratio[k])); err = abs(1200 * np.log2(ratio[k] / max(m_, 1)))
                        key = (f'x{m_}' if (m_ >= 1 and err <= 50 and m_ <= 8) else 'other') if ratio[k] >= 1 else 'below'
                        harm_hist[key] = harm_hist.get(key, 0.0) + wv
            per.append(dict(name=name, loud=int(loud.sum()), covered=int(cov), wrong=wwrong, total=wsum, share=wwrong / wsum if wsum else None, tp=tp,
                            n_midi=len(allm)))
            tot['loud'] += int(loud.sum()); tot['cov'] += cov; tot['w_all'] += wsum; tot['w_wrong'] += wwrong
        res[cfgname] = dict(per_track=per, coverage=tot['cov'] / max(tot['loud'], 1), wrong_share=tot['w_wrong'] / max(tot['w_all'], 1e-30),
                            wrong_share_by_state={int(k): (tot['w_wrong_by_state'][k] / tot['w_by_state'][k] if tot['w_by_state'][k] else None) for k in tot['w_by_state']},
                            weight_share_by_state={int(k): tot['w_by_state'][k] / max(tot['w_all'], 1e-30) for k in tot['w_by_state']},
                            wrong_weight_by_nearest_harmonic={k: v / max(tot['w_wrong'], 1e-30) for k, v in sorted(harm_hist.items())})
    return res


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--parts', default='v3b,v4,v0'); ap.add_argument('--out', default=str(HOME / 'r3a-dev/verify_core/xcheck.json'))
    ap.add_argument('--cfgs', default='A,B,C,D')
    a = ap.parse_args()
    parts = [p for p in a.parts.split(',') if p]
    cand, ref = open_lib(CAND), open_lib(REF)
    cfgs = [c for c in a.cfgs.split(',') if c]
    if 'v3b' in parts:
        log('v3b'); OUT['v3b'] = {'P1': v3b(ref, 6, None, 'P1')}
        for c in cfgs:
            OUT['v3b'][c] = v3b(cand, 15, CFG[c], c)
    if 'v4' in parts:
        log('v4'); OUT['v4'] = {'P1': v4(ref, 6, None, 'P1')}
        for c in cfgs:
            OUT['v4'][c] = v4(cand, 15, CFG[c], c)
    if 'v0' in parts:
        log('v0'); OUT['v0'] = v0_subset(cand, ref)
    for p in ('v5', 'v3c', 'sanity', 'v7d', 'v6', 'v7a', 'v9', 'v3a', 'v7e', 'v2', 'v3h', 'blocks', 'v6both'):
        if p in parts:
            fn = globals().get('part_' + p)
            if fn is None:
                log('part not available yet:', p); continue
            log(p); OUT[p] = fn(cand, ref, cfgs)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(OUT, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    print(json.dumps(OUT, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))[:12000])


if __name__ == '__main__':
    main()
