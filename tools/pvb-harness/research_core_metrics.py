#!/usr/bin/env python3
"""Independent acceptance metrics V0-V9 of the Resultant core (vb_algo 15), docs/RESULTANT_CORE.md v1.3 section 7.

One entry point: measures a configuration (library, algorithm, optional --resultant k=v,...) against the P1 reference build
(vb_algo 6) and writes <outdir>/<label>/results.json and summary.md (default ~/r3a-dev/core_results/<label>/).
Run from tools/pvb-harness with PYTHONPATH=.:study, e.g.
  python research_core_metrics.py --lib ~/r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so --algo 6 --label p1_baseline
  python research_core_metrics.py --lib build_core/libpvbcapi.so --algo 15 --resultant ampSource=0 --label core_a0
Thresholds are the ones fixed in the spec; nothing here is tuned. Where the spec is open, the most literal reading is implemented
and written to results.json["interpretations"] / summary.md.

Layer convention: layer = engine output at vb_level_db 0 minus the output at vb_level_db -120 (same input, same settings),
both shifted by the engine latency read after processing, so a sample index is an input-time index.
Hop time: the analysis centre of hop h in input time is (callback offset + header[9]) / 48000 of the harmonic trace row.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, hilbert, resample_poly, sosfiltfilt

import research_core_signals as S
import research_gt_bass as G
import research_p1plus as RP
import test_engine as T
import test_harmonic_continuity as H
from vb_quality.stage_capture import INDEX as SI, StageCapture, core_indices

try:
    import research_core_api as CA        # the implementer's wrapper; may not exist yet
except Exception as _e:                   # noqa
    CA = None
    CA_ERR = repr(_e)

FS = 48000
HOME = Path.home()
REF_LIB = HOME / 'r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so'
OUT_ROOT = HOME / 'r3a-dev/core_results'
SPEC = 'docs/RESULTANT_CORE.md v1.4 (4b8eb73)'
# spec 5.8 order (index 4 is reserved in v1.3)
PARAM_ORDER = [('voicing', 0), ('levelDb', 0), ('ampSource', 0), ('snrOnDb', 15), ('snrFastDb', 22), ('snrOffDb', 6), ('tauOnMs', 8),
               ('tauOffMs', 30), ('betaMin', .2), ('betaMax', .9), ('kappa', 1.0), ('nMin', 30), ('nFuture', 24), ('psiSlew', .12),
               ('crest', 0), ('maxDfdtBirth', 200)]
VOICE_FIELDS = ['hop', 'voice', 'track', 'state', 'coasting', 'f_track', 'f_osc', 'dfdt_s', 'A', 'c', 'sigma', 'Np', 'snr_db', 'prominent',
                'raw_db', 'res_db', 'subordinate', 'theta_hat', 'psi_2', 'psi_3', 'a_2', 'a_3']
VF = {n: i for i, n in enumerate(VOICE_FIELDS)}
NOTES = []        # interpretations the report must list


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, file=sys.stderr, flush=True)


def interp(s):
    if s not in NOTES:
        NOTES.append(s)


# ===================================================================================================== rendering
def parse_kv(s):
    out = {}
    for p in filter(None, (s or '').split(',')):
        k, v = p.split('=')
        out[k.strip()] = float(v)
    return out


def set_resultant(lib, eng, kv):
    """pvb_set_resultant(e, double v[16], 16) with the spec 5.8 order; names not given keep the spec default."""
    names = [n for n, _ in PARAM_ORDER]
    bad = [k for k in kv if k not in names]
    if bad:
        raise ValueError(f'unknown --resultant names {bad}; spec 5.8 names: {names}')
    v = np.array([float(kv.get(n, d)) for n, d in PARAM_ORDER], np.float64)
    lib.pvb_set_resultant.argtypes = [C.c_void_p, C.POINTER(C.c_double), C.c_int]
    lib.pvb_set_resultant.restype = C.c_int
    if lib.pvb_set_resultant(eng.h, v.ctypes.data_as(C.POINTER(C.c_double)), len(v)) != 1:
        raise RuntimeError(f'pvb_set_resultant rejected {kv}')


def render_raw(lib, x2, algo, level=0.0, out_db=-5.0, res=None, harmonic=False, stage=False, block=256, sr=FS):
    e = T.Engine(lib, sr, vb_on=1, vb_algo=algo, vb_level_db=level, out_db=out_db, ramp_ms=0)
    if algo == 15 and res is not None:
        set_resultant(lib, e, res)
    if harmonic:
        lib.pvb_set_diagnostic_capture(e.h, 1)
    cap = StageCapture(lib, e.h, 0, int(len(x2) / sr * 3000) + 16) if stage else None
    y = np.ascontiguousarray(x2, np.float32).copy(); rows = []; buf = np.empty(H.ROWS * H.FIELDS, np.float32); st = None
    try:
        for off in range(0, len(y), block):
            b = y[off:off + block]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
            if harmonic:
                n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
                if n > 0:
                    d = buf[:n * H.FIELDS].reshape(n, H.FIELDS).copy(); d[:, 0] += off; rows.append(d)
        lat = e.latency()
        st = cap.copy() if cap else None
    finally:
        if cap:
            cap.close()
        e.close()
    return dict(y=y, lat=lat, harm=np.vstack(rows) if rows else np.empty((0, H.FIELDS), np.float32), stage=st, voice=None)


class Ctx:
    def __init__(self, lib_path, algo, res, label=''):
        self.path = str(lib_path); self.lib = RP.api(self.path); self.algo = int(algo); self.res = res if algo == 15 else None
        self.label = label; self.cache = {}; self.voice_ok = True; self.voice_mismatch = []

    def render(self, key, x2, level=0.0, out_db=-5.0, harmonic=False, stage=False, voice=False):
        k = (key, float(level), float(out_db))
        c = self.cache.get(k)
        # 0.3 s of digital silence is appended so the latency-aligned output still covers the whole input (all metrics index input time)
        x2 = np.concatenate([np.asarray(x2, np.float32), np.zeros((int(.3 * FS), 2), np.float32)], axis=0)
        voice = bool(voice and self.algo == 15)
        want_h = bool(harmonic or voice or (c is not None and c['harm'].size > 0))
        want_s = bool(stage or (c is not None and c['stage'] is not None))
        want_v = bool(voice or (c is not None and c['voice'] is not None))
        if c is None or (want_h and c['harm'].size == 0) or (want_s and c['stage'] is None) or (want_v and c['voice'] is None):
            r = render_raw(self.lib, x2, self.algo, level, out_db, self.res, harmonic=want_h, stage=want_s)
            if want_v:
                r['voice'] = self._voice_trace(x2, level, out_db, r)
            self.cache[k] = c = r
        return c

    def _voice_trace(self, x2, level, out_db, r):
        """The 22-field voice trace through the implementer's wrapper (research_core_api.render(..., trace=True))."""
        if CA is None:
            self.voice_ok = False
            raise RuntimeError('research_core_api.py is not importable (%s): no voice trace' % CA_ERR)
        y, tr, lat = CA.render(self.lib, x2, sr=FS, algo=15, params=dict(self.res) if self.res else None, trace=True, block=256,
                               vb_level_db=level, out_db=out_db)
        y = np.asarray(y)
        yc = r['y'] if y.ndim == 2 else r['y'][:, 0]
        if y.shape != yc.shape or not np.array_equal(y, yc):
            self.voice_mismatch.append(dict(level=level, shape=[list(y.shape), list(yc.shape)],
                                            maxdiff=float(np.max(np.abs(y - yc))) if y.shape == yc.shape else None))
        return np.asarray(tr, float)


def mono(y):
    return np.asarray(y, float).mean(axis=1)


def al(r):
    return mono(r['y'])[r['lat']:]


def layer_of(r0, rd):
    a, b = al(r0), al(rd); m = min(len(a), len(b))
    return a[:m] - b[:m]


def db10(p, floor=1e-30):
    return 10 * np.log10(np.maximum(p, floor))


def bandpass(x, lo, hi, fs=FS, order=4):
    return sosfiltfilt(butter(order, [lo, hi], btype='band', fs=fs, output='sos'), x)


def amp_env(x, ms=5.0):
    return np.sqrt(np.maximum(uniform_filter1d(np.asarray(x, float) ** 2, size=max(1, int(ms * FS / 1000)), mode='nearest'), 0.0))


# ===================================================================================================== voices
class VoiceSet:
    """Per hop and slot arrays (H x V). core: voice trace; P1: harmonic-trace tracks (ON = fade >= 0.5)."""
    pass


def hop_table(rows):
    core = H.core_indices(rows)
    tc = (rows[:, 0].astype(float) + rows[:, 9]) / FS
    return core, tc


def _dense(h, order_key, n_hops, cols, width_min=1):
    """Fill H x V arrays for rows `h` (hop index) sorted by (h, order_key)."""
    order = np.lexsort((order_key, h)); hs = h[order]
    first = np.r_[0, np.flatnonzero(np.diff(hs)) + 1] if len(hs) else np.array([], int)
    counts = np.diff(np.r_[first, len(hs)]) if len(hs) else np.array([], int)
    rank = np.arange(len(hs)) - np.repeat(first, counts)
    V = max(int(rank.max()) + 1 if len(rank) else 1, width_min)
    out = {}
    for name, col in cols.items():
        a = np.full((n_hops, V), np.nan); a[hs, rank] = np.asarray(col, float)[order]; out[name] = a
    return out, V


def vs_from_harm(rows):
    core, tc = hop_table(rows); ts = H.tracks(rows); n = len(rows)
    vs = VoiceSet(); vs.kind = 'p1'; vs.core = core; vs.tc = tc
    valid = ts[:, :, 1] > 0
    vs.valid = valid; vs.vid = np.where(valid, ts[:, :, 0], -1); vs.f = np.where(valid, ts[:, :, 2], np.nan); vs.ftr = vs.f.copy()
    vs.A = np.where(valid, ts[:, :, 4], np.nan); vs.c = np.where(valid, ts[:, :, 7], 0.0); vs.sigma = np.ones_like(vs.c)
    vs.st = np.where(valid & (vs.c >= .5), 2, np.where(valid, 1, 0)); vs.sub = np.zeros_like(valid)
    vs.on = vs.st == 2
    vs.w = np.where(valid, (np.nan_to_num(vs.A) * vs.c) ** 2, 0.0)
    hs = ts[:, :, 14:].reshape(n, H.TRACKS, 7, 6)
    vs.w23 = np.where(valid, hs[:, :, 0, 1] ** 2 + hs[:, :, 1, 1] ** 2, 0.0)
    vs.snr = np.full(valid.shape, np.nan)
    return vs


def vs_from_core(trace, rows):
    core, tc = hop_table(rows); n = len(rows)
    tr = np.asarray(trace, float).reshape(-1, 22)
    tr = tr[tr[:, VF['state']] > 0]
    vs = VoiceSet(); vs.kind = 'core'; vs.core = core; vs.tc = tc
    best = None
    hop = tr[:, 0].astype(np.int64)
    tf = H.tracks(rows)[:, :, 2]            # tracker frequencies per hop: the voice's f_track must be one of them at its hop
    for off in (0, 16, -16):
        idx = np.searchsorted(core, hop - off); ok = (idx < n) & (core[np.minimum(idx, n - 1)] == hop - off)
        if ok.any():
            ft = tr[ok][:, VF['f_track']]; hh = idx[ok]
            m = np.mean([np.any(np.abs(tf[h_] - f_) <= .005 * max(f_, 1) + 1e-6) for h_, f_ in zip(hh, ft) if f_ > 0] or [0.0])
        else:
            m = 0.0
        fr = float(ok.mean()) if len(ok) else 1.0
        score = fr + m          # index match first, then agreement of f_track with the tracker at that hop (tie -> offset 0)
        if best is None or score > best[0] + 1e-9:
            best = (score, off, idx, ok, fr)
    if len(tr) and best[4] < .95:
        raise RuntimeError(f'voice trace hop index matches the harmonic trace core index in only {best[4]:.2f} of rows')
    vs.hop_offset = best[1] if len(tr) else 0
    if len(tr):
        tr = tr[best[3]]; h = best[2][best[3]]
    else:
        h = np.array([], int)
    cols = {nm: (tr[:, VF[nm]] if len(tr) else np.array([])) for nm in ('voice', 'track', 'state', 'coasting', 'f_track', 'f_osc', 'A', 'c', 'sigma',
                                                                           'subordinate', 'snr_db', 'a_2', 'a_3')}
    d, V = _dense(h, tr[:, VF['voice']] if len(tr) else np.array([]), n, cols)
    st = np.nan_to_num(d['state']).astype(int)
    vs.valid = st > 0; vs.vid = np.where(vs.valid, np.nan_to_num(d['voice'], nan=-1), -1).astype(int)
    vs.tid = np.nan_to_num(d['track'], nan=-1)
    vs.f = d['f_osc']; vs.ftr = d['f_track']; vs.A = d['A']; vs.c = np.nan_to_num(d['c']); vs.sigma = np.nan_to_num(d['sigma'], nan=1.0)
    vs.st = st; vs.sub = np.nan_to_num(d['subordinate']) > .5; vs.on = st == 2; vs.coast = np.nan_to_num(d['coasting']) > .5
    vs.w = np.where(vs.valid, (np.nan_to_num(vs.A) * vs.c * vs.sigma) ** 2, 0.0)
    vs.w23 = np.where(vs.valid, np.nan_to_num(d['a_2']) ** 2 + np.nan_to_num(d['a_3']) ** 2, 0.0)
    vs.snr = d['snr_db']
    return vs


def voices(ctx, r):
    if ctx.algo == 15:
        if r['voice'] is None:
            raise RuntimeError('voice trace not captured')
        return vs_from_core(r['voice'], r['harm'])
    return vs_from_harm(r['harm'])


def near_mask(vs, f0, tol, on=True):
    m = vs.valid & (np.abs(np.nan_to_num(vs.f, nan=1e9) - f0) <= tol * f0)
    return m & vs.on if on else m


def series_near(vs, f0, tol_hz=5.0, field='A', on=False):
    """Per hop the `field` of the slot nearest f0 (by tracker frequency, within tol_hz); NaN if none."""
    ft = np.nan_to_num(vs.ftr, nan=1e9)
    m = vs.valid & (np.abs(ft - f0) < tol_hz)
    if on:
        m &= vs.on
    val = np.where(m, getattr(vs, field), np.nan)
    with np.errstate(all='ignore'):
        return np.nanmax(np.where(np.isnan(val), -np.inf, val), axis=1).astype(float) if val.size else np.array([])


# ===================================================================================================== analysis helpers
def proj_power(x, centers_s, freq, win_s=0.020):
    """Hann-windowed single-frequency projection power |sum w x e^{-jwn}|^2/(sum w)^2 for each centre (s); freq scalar or per centre.
    A unit sine gives 0.25. NaN where the window leaves the signal."""
    N = int(round(win_s * FS)); N += N % 2
    w = np.hanning(N); n = np.arange(N) - N / 2
    c = np.asarray(centers_s, float); f = np.broadcast_to(np.asarray(freq, float), c.shape)
    out = np.full(len(c), np.nan)
    n0 = np.round(c * FS).astype(int) - N // 2
    ok = (n0 >= 0) & (n0 + N <= len(x)) & np.isfinite(f)
    for a in range(0, len(c), 4000):
        sel = np.flatnonzero(ok[a:a + 4000]) + a
        if not len(sel):
            continue
        idx = n0[sel, None] + np.arange(N)[None]
        z = (x[idx] * w[None] * np.exp(-2j * np.pi * f[sel, None] * n[None] / FS)).sum(axis=1)
        out[sel] = (np.abs(z) / w.sum()) ** 2
    return out


def ratio_db(pl, pd, floor_db=-80.0):
    return np.maximum(10 * np.log10((pl + 1e-20) / (pd + 1e-20)), floor_db)


def legacy_peak_ms(y):
    """research_r4l_timing_layer.py: 150-600 Hz band, Hilbert power, mean over notes 1..15 of the 16 half-second cycles, 1 ms smoothing."""
    z = bandpass(y, 150, 600); e = np.abs(hilbert(z)) ** 2; Cy = FS // 2
    c = e[:16 * Cy].reshape(16, Cy)[1:].mean(axis=0)
    c = np.convolve(c, np.ones(48) / 48, 'same')[::48]
    pk = int(np.argmax(c[:400])); r50 = int(np.argmax(c >= .5 * c[pk])); fall = pk + int(np.argmax(c[pk:] <= c[pk] * .1))
    return dict(peak_ms=pk, rise50_ms=r50, fall10db_ms=fall)


def legacy_cycle_bins(y):
    sos3 = butter(4, (285, 315), btype='band', fs=FS, output='sos')
    p = np.abs(hilbert(sosfiltfilt(sos3, y))) ** 2
    cyc = p[:16 * FS // 2].reshape(16, -1)[1:].mean(axis=0)
    return cyc.reshape(-1, 480).mean(axis=1)          # 50 bins of 10 ms


def causal_power(x, ms):
    L = max(1, int(ms * FS / 1000)); c = np.cumsum(np.r_[0.0, np.asarray(x, float) ** 2])
    out = np.empty(len(x)); out[L - 1:] = (c[L:] - c[:-L]) / L; out[:L - 1] = c[1:L] / np.arange(1, L)
    return out


def median_or_nan(a):
    a = np.asarray(a, float)
    return float(np.median(a)) if len(a) else float('nan')


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if np.isfinite(v) else (None if np.isnan(v) else ('inf' if v > 0 else '-inf'))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


# ===================================================================================================== V1 / V2
def v1(ctx):
    x = S.tone_steady(); X = S.stereo(x)
    r = ctx.render('tone', X, 0.0, harmonic=True, stage=True, voice=True)
    vs = voices(ctx, r); core, tc = vs.core, vs.tc
    win = (tc >= .5) & (tc <= 3.8)
    pf = r['stage'][:, SI['post_filter']]; ci = core_indices(r['stage']).astype(np.int64)
    sel = (ci >= int(.7 * 3000)) & (ci <= int(3.5 * 3000))
    z = sosfiltfilt(butter(4, [150, 600], btype='band', fs=3000, output='sos'), pf)
    level = float(db10(np.mean(z[sel] ** 2)))
    p1 = vs_from_harm(r['harm'])        # the tracker of this very run (identical to P1 when V0 holds)
    a_p1 = series_near(p1, 100.0)
    A = series_near(vs, 100.0, on=True) if ctx.algo == 15 else series_near(vs, 100.0)
    ok = win & np.isfinite(A) & np.isfinite(a_p1) & (a_p1 > 0) & (A > 0)
    d = 20 * np.log10(A[ok] / a_p1[ok]) if ok.any() else np.array([])
    interp('V1: A/tr.a is the median over hops with tc in 0.5-3.8 s of 20log10(A of the ON voice within 5 Hz of 100 Hz / tr.a of the same-run '
           'tracker track within 5 Hz of 100 Hz) and is compared with the P1 reference run by core index in make_checks. Layer level = 10log10(mean square of '
           'post_filter (stage column), band-passed 150-600 Hz, core indices 2100-10500)')
    return dict(a_ratio_db_median=median_or_nan(d), a_ratio_db_p5=float(np.percentile(d, 5)) if len(d) else None,
                a_ratio_db_p95=float(np.percentile(d, 95)) if len(d) else None, n_hops=int(ok.sum()), layer_level_db=level,
                arrays=dict(core=core[win], a_p1=np.round(a_p1[win], 6), A=np.round(A[win], 6)))


def v2(ctx):
    x = S.tone_steady(); X = S.stereo(x)
    r0 = ctx.render('tone', X, 0.0, out_db=-18.0); rd = ctx.render('tone', X, -120.0, out_db=-18.0)
    lay = layer_of(r0, rd); dry = al(rd)[:len(lay)]
    out = {}
    for k in (2, 3):
        f = 100.0 * k; N = int(.2 * FS); w = np.hanning(N); n = np.arange(N); ph = []
        for c in np.arange(.7, 3.5, .1):
            s = int(c * FS)
            if s + N > len(lay):
                break
            e = np.exp(-2j * np.pi * f * n / FS)
            zl = np.sum(lay[s:s + N] * w * e); zd = np.sum(dry[s:s + N] * w * e)
            ph.append(np.angle(zl * np.conj(zd)))
        ph = np.array(ph); m = np.angle(np.mean(np.exp(1j * ph)))
        out[f'k{k}'] = dict(dphi_mean_rad=float(m), dphi_std_rad=float(np.sqrt(-2 * np.log(max(np.abs(np.mean(np.exp(1j * ph))), 1e-12)))), n=len(ph))
    interp('V2: layer = out(-120 dB) subtracted from out(0 dB) at out_db -18; "original" = the dry engine output (vb_level -120), so EQ/latency '
           'phase is shared; dphi_k = circular mean over 200 ms Hann frames (hop 100 ms, input time 0.7-3.5 s) of angle(layer_k * conj(dry_k)) '
           'at exactly k*100 Hz. Pass requires BOTH |dphi_2| and |dphi_3| <= 0.3 rad (stricter reading of "average")')
    return out


# ===================================================================================================== V3
def v3_bare(ctx):
    X = S.stereo(S.bass_notes(9.0))
    r0 = ctx.render('bass9', X, 0.0, harmonic=True); rd = ctx.render('bass9', X, -120.0)
    y = al(r0)[:8 * FS]; dry = al(rd)[:8 * FS]; lay = layer_of(r0, rd)[:8 * FS]
    a = legacy_peak_ms(y)
    cl, cd = legacy_cycle_bins(lay), legacy_cycle_bins(dry)
    rat = np.array([10 * np.log10(cl[i:i + 2].sum() / max(cd[i:i + 2].sum(), 1e-30) + 1e-30) for i in range(0, 50, 2)])
    rr = np.maximum(rat[2:22], -100)           # 20 ms bins 40..440 ms
    interp('V3b: bins [40+20j, 60+20j) ms, j=0..19 (the last full 20 ms bin before 450 ms); 300 Hz band 285-315, Hilbert power cycle-averaged over '
           'notes 1..15 (research_r4l_timing_layer.py); input partial = dry engine output (vb_level -120); ratio floored at -100 dB')
    # V3d pre-echo: causal 10 ms power, window [t0-30, t0] ms vs a line fitted on dB over [t0-150, t0-50] ms
    p = causal_power(lay, 10.0); rises = []
    for n_ in range(2, 16):
        t0 = .5 * n_
        tb = np.arange(int((t0 - .150) * FS), int((t0 - .050) * FS)); Eb = db10(p[tb])
        sl, ic = np.polyfit(tb / FS - t0, Eb, 1)
        w1 = np.arange(int((t0 - .030) * FS), int(t0 * FS))
        rises.append(float(db10(np.mean(p[w1])) - (ic + sl * (w1.mean() / FS - t0))))
    interp('V3d: layer power with a causal 10 ms boxcar; baseline line = least squares of its dB over [t0-150, t0-50] ms extrapolated to the '
           'centre of [t0-30, t0] ms; rise = dB of the mean power over [t0-30, t0] minus that line; reattacks 1.0..7.5 s (14); pass uses the median')
    # V3h bare: rise (peak referenced) over the 14 notes
    env = amp_env(lay, 5.0); r50, r90 = [], []
    for n_ in range(1, 15):
        t0 = .5 * n_; i0 = int(t0 * FS); seg = env[i0:i0 + int(.15 * FS)]; ref = seg.max()
        for fr, lst in ((.5, r50), (.9, r90)):
            k = int(np.argmax(seg >= fr * ref)); lst.append(k / FS * 1000 if seg[k] >= fr * ref else np.inf)
    # tail note
    xt = S.stereo(S.tail_note()); rt0 = ctx.render('tail', xt, 0.0); rtd = ctx.render('tail', xt, -120.0)
    lt = layer_of(rt0, rtd); et = amp_env(lt, 5.0)
    ref = float(np.mean(et[int(1.2 * FS):int(1.45 * FS)])); i1 = int(1.5 * FS)
    k = np.flatnonzero(et[i1:i1 + int(1.5 * FS)] <= .1 * ref); tail = float(k[0] / FS * 1000) if len(k) else float('inf')
    i0 = int(.5 * FS); seg = et[i0:i0 + int(.4 * FS)]
    tr50 = float(np.argmax(seg >= .5 * ref) / FS * 1000) if (seg >= .5 * ref).any() else float('inf')
    tr90 = float(np.argmax(seg >= .9 * ref) / FS * 1000) if (seg >= .9 * ref).any() else float('inf')
    interp('V3h bare: layer amplitude envelope = sqrt(5 ms boxcar of layer^2). The repeating decaying bare bass has no steady level and no silence before the attack, so '
           'its peak-referenced rise (max envelope in the first 150 ms of notes 1..14) is only REPORTED (v3h_bare.rise50_ms/rise90_ms); the PASS values come from a separate '
           'isolated flat 1 s 100 Hz note (tail_note, attack from silence): ref = mean envelope 1.2-1.45 s, rise = time from the attack (0.5 s) to 50/90 % of ref, '
           'tail = time after the note end (1.5 s) to fall to -20 dB (10 %) of ref')
    return dict(v3a=a, v3b=dict(range_db=float(rr.max() - rr.min()), ratio_db_per20ms=rr), v3d=dict(rise_db_median=median_or_nan(rises),
                rise_db_max=float(np.max(rises)), rise_db_all=rises), v3h_bare=dict(rise50_ms=median_or_nan(r50), rise90_ms=median_or_nan(r90),
                tail_ms=tail, tailnote_rise50_ms=tr50, tailnote_rise90_ms=tr90))


def entering_time(vs, t0, f_new, tol=.02, tmax=.125, dominant=False):
    """Time (s, relative to t0) of the first hop with tc in [t0, t0+tmax) at which an ON voice within tol of f_new exists that was not
    already within tol of f_new on the last hop before t0 ("lingering" voices are ignored). dominant=True: only the ON voice with the
    largest weight counts. inf if never."""
    hpre = int(np.searchsorted(vs.tc, t0)) - 1
    ling = set()
    if hpre >= 0:
        m = near_mask(vs, f_new, tol)[hpre]
        ling = set(vs.vid[hpre][m].tolist())
    h0 = int(np.searchsorted(vs.tc, t0)); h1 = int(np.searchsorted(vs.tc, t0 + tmax))
    for h in range(h0, h1):
        m = near_mask(vs, f_new, tol)[h]
        if dominant:
            on = np.flatnonzero(vs.on[h])
            if not len(on):
                continue
            top = on[np.argmax(vs.w[h][on])]
            if m[top]:
                return float(vs.tc[h] - t0)
        else:
            if any(v not in ling for v in vs.vid[h][m]):
                return float(vs.tc[h] - t0)
    return float('inf')


def v3c(ctx):
    sg = S.stepwise_line(25.0); X = S.stereo(sg['noisy'])
    r0 = ctx.render('step25', X, 0.0, harmonic=True, voice=True); rd = ctx.render('step25', X, -120.0)
    rc = ctx.render('step25c', S.stereo(sg['clean']), -120.0)
    vs = voices(ctx, r0); lay = layer_of(r0, rd); dry = al(rc)
    ent, entd, rng, low = [], [], [], 0
    idx = [i for i in range(2, 40) if i != 20]
    for i in idx:
        t0 = sg['t0'][i]; f = sg['notes'][i]
        ent.append(entering_time(vs, t0, f, dominant=True)); entd.append(entering_time(vs, t0, f))
        cen = t0 + np.array([.025, .045, .065, .085, .100])
        r = ratio_db(proj_power(lay, cen, 3 * f), proj_power(dry, cen, 3 * f))
        rng.append(float(r.max() - r.min())); low += int(np.any(r < np.median(r) - 6))
    ent = np.array(ent)
    interp('V3c: f_osc entering time = first hop (analysis-centre time tc >= note start) at which the DOMINANT ON voice (largest (A*c*sigma)^2; core: state ON; P1: '
           'fade>=0.5 track, (a*fade)^2) is within +-2 % of the new note; inf (never within 125 ms) counts as a miss in the median. Variant (enter_ms_median_anyvoice): '
           'any ON voice within 2 %, ignoring voices that already matched on the last hop before the note start. '
           'In-note ratio at 3f of the note: layer vs the clean line through the dry engine path, 20 ms Hann projections centred at 25,45,65,85,100 ms '
           '(= the 20 ms bins tiling 15-110 ms, the last overlapping); range = max-min; "no bin > 6 dB below the note median" is counted per note; '
           'the range pass uses the median over notes')
    return dict(enter_ms_median=float(np.median(ent) * 1000), enter_ms_p90=float(np.percentile(np.where(np.isinf(ent), 1e3, ent), 90) * 1000),
                enter_miss=int(np.isinf(ent).sum()), enter_ms_median_anyvoice=float(np.median(entd) * 1000), n_notes=len(idx),
                range_db_median=median_or_nan(rng), range_db_p90=float(np.percentile(rng, 90)), range_db_max=float(np.max(rng)),
                notes_with_low_bin=low, enter_ms_all=np.where(np.isinf(ent), 999, ent * 1000))


def v3h_line(ctx, snr):
    sg = S.gated_line(snr); X = S.stereo(sg['noisy'])
    r0 = ctx.render(f'gated{snr}', X, 0.0); rd = ctx.render(f'gated{snr}', X, -120.0)
    lay = layer_of(r0, rd); env = amp_env(lay, 5.0)
    r50, r90, tail = [], [], []
    for i in range(2, 40):
        t0 = sg['t0'][i]; ref = float(np.mean(env[int((t0 + .06) * FS):int((t0 + .11) * FS)]))
        i0 = int(t0 * FS); seg = env[i0:i0 + int(.125 * FS)]
        for fr, lst in ((.5, r50), (.9, r90)):
            ok = seg >= fr * ref
            lst.append(float(np.argmax(ok) / FS * 1000) if ok.any() and ref > 1e-9 else np.inf)
        i1 = int((t0 + .125) * FS); seg = env[i1:i1 + int(.12 * FS)]; ok = seg <= .1 * ref
        tail.append(float(np.argmax(ok) / FS * 1000) if ok.any() and ref > 1e-9 else np.inf)
    return dict(rise50_ms=median_or_nan(r50), rise90_ms=median_or_nan(r90), tail_ms=median_or_nan(tail), miss90=int(np.isinf(r90).sum()),
                miss_tail=int(np.isinf(tail).sum()), n=len(r90))


def v3h(ctx):
    interp('V3h line: measured on the GATED stepwise line (125 ms note, 125 ms gap, same pink bed at in-band SNR 25 / 6 dB) because the back-to-back line '
           'has no tail and no rise from silence; ref = mean layer envelope 60-110 ms into the note; rise = time from the note start to 50/90 % of ref, '
           'tail = time from the note end to <= 10 % (-20 dB) of ref (cap 120 ms); medians over notes 2..39')
    return {'snr25': v3h_line(ctx, 25.0), 'snr6': v3h_line(ctx, 6.0)}


def env_depth_db(sig, t0=1.0, t1=3.8):
    z = bandpass(sig, 150, 600); p = uniform_filter1d(np.abs(hilbert(z)) ** 2, size=int(.010 * FS), mode='nearest')[int(t0 * FS):int(t1 * FS)]
    return float(10 * np.log10(np.percentile(p, 95) / max(np.percentile(p, 5), 1e-30)))


def v3e(ctx):
    out = {}
    iso = {}
    for f in (100.0, 104.0, 110.0):
        n = int(4 * FS); t = np.arange(n) / FS
        tone = .5 * S.DB(-12) / S.TRIPLE_PEAK * sum(a * np.sin(2 * np.pi * k * f * t) for k, a in S.PARTIALS) * np.minimum(np.arange(n) / (.008 * FS), 1)
        r = ctx.render(f'iso{f}', S.stereo(tone), 0.0, harmonic=True)
        p1 = vs_from_harm(r['harm']); a = series_near(p1, f, 3.0); iso[f] = float(np.nanmedian(a[(p1.tc >= 1) & (p1.tc <= 3.8)]))
    for df in (4.0, 10.0):
        pair, a1, a2 = S.close_pair(df); X = S.stereo(pair)
        r0 = ctx.render(f'pair{df}', X, 0.0, harmonic=True, voice=True); rd = ctx.render(f'pair{df}', X, -120.0)
        vs = voices(ctx, r0); lay = layer_of(r0, rd)
        win = (vs.tc >= 1.0) & (vs.tc <= 3.8); res = {}
        for f in (100.0, 100.0 + df):
            ft = np.nan_to_num(vs.f, nan=1e9)
            near = vs.valid & vs.on & (np.abs(ft - f) <= .03 * f) & (np.abs(ft - f) <= np.abs(ft - (200.0 + df - f)))
            A = np.where(near, vs.A, np.nan)
            with np.errstate(all='ignore'):
                Am = np.nanmax(np.where(np.isnan(A), -np.inf, A), axis=1)
            Am[~np.isfinite(Am)] = np.nan
            err = np.abs(20 * np.log10(Am[win] / iso[f]))
            have = np.isfinite(err)
            res[f'{f:g}'] = dict(median_abs_err_db=float(np.median(np.where(have, err, np.inf))), found_frac=float(have.mean()),
                                 median_err_db_of_found=median_or_nan(err[have]), truth_a=iso[f])
        dl, di = env_depth_db(lay), env_depth_db(pair)
        out[f'df{df:g}'] = dict(voices=res, depth_layer_db=dl, depth_input_db=di, depth_excess_db=dl - di)
    interp('V3e: truth for a voice = median tr.a of the same-frequency tone alone (0.5 x V1 tone, same lib, tracker track within 3 Hz) over tc 1-3.8 s '
           '(the engine amplitude unit); a voice belongs to the nearer tone if within 3 %; error = median over hops of |20log10(A/truth)| with missing hops '
           'counted as infinite; beating depth = 10log10(P95/P5) of the 10 ms boxcar Hilbert power of the 150-600 Hz band over 1-3.8 s (layer vs the raw '
           'input); pass needs both pairs, both voices')
    return out


def v3f(ctx):
    sg = S.weak_tail_attack(); X = S.stereo(sg['x'])
    r0 = ctx.render('weak', X, 0.0, harmonic=True); rd = ctx.render('weak', X, -120.0)
    lay = layer_of(r0, rd); env = amp_env(lay, 5.0); Ta = sg['Ta']
    ref = float(np.mean(env[int(sg['steady_win'][0] * FS):int(sg['steady_win'][1] * FS)]))
    seg = env[int(Ta * FS):int((Ta + .6) * FS)]
    t = lambda fr: float(np.argmax(seg >= fr * ref) / FS * 1000) if (seg >= fr * ref).any() else float('inf')
    interp('V3f: total layer amplitude envelope (5 ms) of the whole layer (the old 80 Hz note is ~18 dB weaker); 90 % time = first time after T_a=1.4 s '
           'at which it reaches 0.9 x its mean over 1.7-2.6 s. SNRs are set on the input with the engine\'s 5.4 definition (not the engine\'s own snr_db)')
    return dict(t50_ms=t(.5), t90_ms=t(.9), steady_ref=ref, calib={k: sg[k] for k in ('tau', 'rms_noise', 'a_old_at_Ta', 'a_new', 'peak')})


def v3g(ctx):
    x = S.low_notes(); X = S.stereo(x)
    r0 = ctx.render('low', X, 0.0, harmonic=True, voice=True)
    vs = voices(ctx, r0); res = {}
    hop_s = 16 / 3000.0
    for f, a, b in S.LOW_NOTES:
        m = near_mask(vs, f, .05, on=True); anyv = near_mask(vs, f, .05, on=False)
        has_on = m.any(axis=1); has_any = anyv.any(axis=1)
        w = np.flatnonzero((vs.tc >= a - .1) & (vs.tc <= b))
        on_idx = [h for h in w if has_on[h]]; any_idx = [h for h in w if has_any[h]]
        first_ms = float((vs.tc[any_idx[0]] - a) * 1000) if any_idx else None      # info only: when the tracker first shows the note
        if not on_idx or not any_idx:
            res[f'{f:g}'] = dict(on_found=False, first_appearance_after_onset_ms=first_ms); continue
        h_on = on_idx[0]; last = np.flatnonzero((vs.tc >= vs.tc[h_on]) & (vs.tc <= b - .05))
        lost = int(np.sum(~has_on[last]))
        res[f'{f:g}'] = dict(on_found=True, first_appearance_after_onset_ms=first_ms,
                             on_after_first_hop=float((vs.tc[h_on] - vs.tc[any_idx[0]]) / hop_s),
                             off_hops_during_note=lost, n_hops_checked=int(len(last)))
    interp('V3g (v1.4): a voice "at the note" = tracker/oscillator frequency within 5 % of the fundamental; ON = core state ON (P1: fade>=0.5); the "2 hops" are counted '
           'from the first hop at which any voice/track at the note exists (tc difference / 5.33 ms; non-measured hops are not distinguished); the tc-onset reading is dropped '
           '(first_appearance_after_onset_ms is information); "never REL" = no hop with tc from the first ON to note end - 50 ms lacks an ON voice at the note')
    return res


def v3i(ctx):
    sg = S.chatter_tone(); X = S.stereo(sg['noisy'])
    r0 = ctx.render('chatter', X, 0.0, harmonic=True, voice=True)
    vs = voices(ctx, r0)
    win = (vs.tc >= 1.0) & (vs.tc <= 9.9); dur = float(vs.tc[win][-1] - vs.tc[win][0])
    onb = near_mask(vs, 100.0, .05, on=True).any(axis=1)[win]
    flips = int(np.sum(onb[1:] != onb[:-1]))
    ft = np.nan_to_num(vs.f, nan=1e9)
    nearv = vs.valid & (np.abs(ft - 100.0) <= 5.0)
    cmax = np.where(nearv, vs.c, 0.0).max(axis=1)[win]
    low = cmax < .5
    # continuous below 0.5 = a single run covering all of the window's end (stays off) or the whole window
    runs = np.flatnonzero(np.diff(np.r_[0, low.astype(int), 0]))
    stays = bool(low.all() or (low[-1] and len(runs) <= 2 and runs[-2] / len(low) <= .5 and flips <= 1))
    return dict(transitions_per_s=flips / dur, flips=flips, frac_c_below_half=float(low.mean()), stays_below_half=stays, window_s=dur,
                fade_crossings_per_s=flips / dur if ctx.algo != 15 else None)


# ===================================================================================================== V4
def v4(ctx):
    sig = S.flicker_signals(8.0); X_clean = S.stereo(sig['bass'])
    rdc = ctx.render('bass8c', X_clean, -120.0); dry_clean = al(rdc)
    out = {}
    for nm in ('bass+pink', 'bass+kick+pink'):
        X = S.stereo(sig[nm])
        r0 = ctx.render(nm, X, 0.0, harmonic=True, voice=True); rd = ctx.render(nm, X, -120.0)
        lay = layer_of(r0, rd); vs = voices(ctx, r0)
        means, meds, nlow, nbin = [], [], 0, 0
        for c in range(2, 16):
            t0 = .5 * c; cen = t0 + .040 + .020 * np.arange(20) + .010
            r = ratio_db(proj_power(lay, cen, 300.0), proj_power(dry_clean, cen, 300.0))
            means.append(float(np.mean(r))); m = np.median(r); nlow += int(np.sum(r < m - 6)); nbin += len(r)
        # (c) std of 20log10(A) minus the known envelope exp(-u/0.35) over 40-450 ms of each note
        A = series_near(vs, 100.0, on=(ctx.algo == 15)); res_all, per = [], []
        for c in range(2, 16):
            t0 = .5 * c; sel = np.flatnonzero((vs.tc >= t0 + .040) & (vs.tc < t0 + .450) & np.isfinite(A) & (A > 0))
            if len(sel) < 5:
                continue
            u = vs.tc[sel] - t0; rr = 20 * np.log10(A[sel]) + 20 * np.log10(np.e) * u / .35
            res_all.append(rr - rr.mean()); per.append(float(np.std(rr)))
        allr = np.concatenate(res_all) if res_all else np.array([])
        out[nm] = dict(note_mean_ratio_db=means, std_between_notes_db=float(np.std(means, ddof=1)), low_bin_frac=nlow / nbin,
                       a_std_db=float(np.std(allr)) if len(allr) else None, a_std_db_per_note_median=median_or_nan(per),
                       a_rms_hop_diff_db=None, a_missing_frac=float(1 - len(allr) / (14 * 77)))
    interp('V4: ratio = layer (noisy mix, out(0)-out(-120)) / the CLEAN bass partial at 300 Hz through the dry engine path; 20 ms Hann projections tiling 40-440 ms '
           'of notes 2..15, floored at -80 dB; std between the 14 per-note means uses ddof=1; V4c = std (pooled over notes, per-note mean removed) of 20log10(A) '
           '+ 8.686*u/0.35 over 40-450 ms (A = ON voice within 5 Hz of 100 Hz; P1: tr.a)')
    return out


# ===================================================================================================== bass references
_REF = {}


def bass_ref(name):
    if name in _REF:
        return _REF[name]
    it = S.slakh_item(name)
    notes = sum((G.midi_notes(m) for m in it['bass_midis']), [])
    allnotes = sum((G.midi_notes(m) for m in it['all_midis']), [])
    nodrum = sum((G.midi_notes(m) for m in it['all_midis'] if m not in it['drum_midis']), [])
    stems = [sf.read(str(s), always_2d=True)[0] for s in it['bass_stems']]
    fsr = sf.info(str(it['bass_stems'][0])).samplerate
    n = max(len(s) for s in stems)
    bz = sum(np.pad(s.mean(axis=1), (0, n - len(s))) for s in stems)
    if fsr != FS:
        g = np.gcd(fsr, FS); bz = resample_poly(bz, FS // g, fsr // g)
    # octave from the first 30 s as research_resultant_pitch_truth.py
    tp, agree = 0, {}
    try:
        ty, fy = G.yin(G.to_rate(bz[:30 * FS], FS, G.CORE))
        for t in (-24, -12, 0, 12):
            fm = G.midi_f0(ty, notes, 0, t); both = np.isfinite(fm) & np.isfinite(fy)
            agree[t] = float(np.mean(np.abs(1200 * np.log2(fm[both] / fy[both])) < 50)) if both.sum() >= 20 else -1
        tp = max(agree, key=agree.get)
    except Exception as ex:
        agree = {'error': repr(ex)}
    lo = sosfiltfilt(butter(4, [40, 220], btype='band', fs=FS, output='sos'), bz)
    ref = dict(item=it, notes=notes, allnotes=allnotes, nodrum=nodrum, tp=tp, agree=agree, bz=bz, lo=lo)
    _REF[name] = ref
    return ref


def midi_f0_fast(tt, notes, transpose=0):
    out = np.full(len(tt), np.nan)
    if not notes:
        return out
    s = np.array([n[0] for n in notes]); e = np.array([n[1] for n in notes]); p = np.array([n[2] for n in notes], float)
    tt = np.asarray(tt, float)
    for a in range(0, len(tt), 1500):
        t = tt[a:a + 1500, None]
        pm = np.where((s[None] <= t) & (t < e[None]), p[None], np.inf).min(axis=1)
        out[a:a + 1500] = np.where(np.isfinite(pm), 440 * 2 ** ((pm + transpose - 69) / 12), np.nan)
    return out


def stem_level_db(lo, tc, win=2048):
    out = np.empty(len(tc))
    for i, c in enumerate(tc):
        a = int(c * FS) - win // 2; b = int(c * FS) + win // 2
        out[i] = 10 * np.log10(np.mean(lo[max(0, a):max(1, b)] ** 2) + 1e-20)
    return out


# ===================================================================================================== V5
def v5(ctx):
    x = S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0)
    r0 = ctx.render('t60', x, 0.0, harmonic=True); rd = ctx.render('t60', x, -120.0)
    lay = layer_of(r0, rd)
    ref = bass_ref('Track00060')
    B = int(.020 * FS); i0 = int(3.0 * FS); nb = int(8.0 / .020)
    cen_song = 39.0 + .020 * (np.arange(nb) + .5)
    f0 = midi_f0_fast(cen_song, ref['notes'], ref['tp'])
    # bass stem level (40-220 Hz) in 20 ms bins, p95 over the whole song
    lo = ref['lo']; nbins = len(lo) // B
    levall = 10 * np.log10(np.mean(lo[:nbins * B].reshape(nbins, B) ** 2, axis=1) + 1e-20)
    p95 = np.percentile(levall, 95)
    k0 = int(39.0 / .020); lev = levall[k0:k0 + nb]
    present = np.isfinite(f0) & (lev > p95 - 20)
    bs = bandpass(ref['bz'][36 * FS:49 * FS], 150, 600)[:len(lay)]
    L = bandpass(lay, 150, 600)
    el = np.array([np.sum(L[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(nb)])
    es = np.array([np.sum(bs[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(nb)])
    ratio = db10(el, 1e-20) - db10(es, 1e-20)
    ldb = db10(el, 1e-20)
    idx = np.flatnonzero(present); cen = (np.arange(nb) + .5) * .020
    drop = 0; localmax_ok = np.zeros(nb, bool)
    for i in idx:
        m = idx[np.abs(cen[idx] - cen[i]) <= .250]
        if ratio[i] < np.median(ratio[m]) - 6:
            drop += 1
        if ldb[i] >= np.max(ldb[m]) - 3:
            localmax_ok[i] = True
    interp('V5 (v1.3): bins = 20 ms from 39.00 s of Track00060 (rendered 36-48 s, 3 s warm-up); bass-present = MIDI bass note sounding at the bin centre '
           '(octave from the YIN agreement as research_resultant_pitch_truth.py) and the sum of the bass stems 40-220 Hz within 20 dB of its p95 over the whole song; '
           'ratio = layer 150-600 Hz energy / bass-stem-sum 150-600 Hz energy per bin; local = +-250 ms among present bins; (b) compares the layer energy '
           'per bin with P1 over bins where P1 is within 3 dB of its local max')
    return dict(n_present=int(len(idx)), drop_frac=drop / max(len(idx), 1), tp=ref['tp'],
                arrays=dict(present=present.astype(int), layer_db=np.round(ldb, 3), ratio_db=np.round(ratio, 3), localmax_ok=localmax_ok.astype(int)))


# ===================================================================================================== V6
def v6_item(ctx, name, seconds=30.0):
    ref = bass_ref(name); it = ref['item']
    x = S.load_excerpt(it['mix'], 0.0, seconds)
    r = ctx.render('v6_' + name, x, 0.0, harmonic=True, voice=True)
    vs = voices(ctx, r); tc = vs.tc
    f0 = midi_f0_fast(tc, ref['notes'], ref['tp']); lev = stem_level_db(ref['lo'], tc)
    act = np.isfinite(f0) & (tc > .5)
    loud = act & (lev > np.percentile(lev[act], 95) - 10) if act.any() else act
    cov_ok = np.zeros(len(tc), bool)
    cents = lambda f, g: np.abs(1200 * np.log2(np.maximum(f, 1e-9) / g))
    onm = vs.on & ~vs.sub & (vs.c > .5) if vs.kind == 'core' else vs.on
    for h in np.flatnonzero(loud):
        fv = vs.f[h][onm[h]]
        if len(fv):
            cov_ok[h] = np.any([np.any(cents(fv, k * f0[h]) <= 50) for k in (1, 2, 3)])
    # wrong-note energy: x 0.5,1,2,3 of every sounding MIDI note of EVERY instrument (v1.4: ~/datasets/slakh2100_midi), plus the octave-shifted bass
    arr = lambda nl: (np.array([n[2] for n in nl], float), np.array([n[0] for n in nl]), np.array([n[1] for n in nl]))
    allp, alls, alle = arr(ref['allnotes']); ndp, nds, nde = arr(ref['nodrum'])
    bassp, bs, be = arr(ref['notes'])
    acc = {k: [0.0, 0.0] for k in ('a', 'b', 'c', 'w23')}           # [total, wrong]
    for h in np.flatnonzero(tc > .5):
        wv = vs.w[h]; sel = np.flatnonzero(wv > 0)
        if not len(sel):
            continue
        t = tc[h]
        for tag, (pp, ss, ee), tolms in (('a', (allp, alls, alle), 0.0), ('b', (allp, alls, alle), .060), ('c', (ndp, nds, nde), 0.0)):
            pa = np.r_[pp[(ss <= t + tolms) & (t - tolms < ee)], bassp[(bs <= t + tolms) & (t - tolms < be)] + ref['tp']]
            fn = 440 * 2 ** ((pa - 69) / 12)
            T_ = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
            for j in sel:
                bad = (not len(T_)) or np.min(cents(vs.f[h][j], T_)) > 50
                acc[tag][0] += wv[j]; acc[tag][1] += wv[j] * bad
                if tag == 'a':
                    acc['w23'][0] += vs.w23[h][j]; acc['w23'][1] += vs.w23[h][j] * bad
    interp('V6: hop time = analysis centre tc (no lag search); loud-bass hops = MIDI bass note sounding and bass stem 40-220 Hz within 10 dB of its p95 over the sounding hops, '
           'tc>0.5 s; "right" voice (core: ON, non-subordinate, c>0.5; P1: fade>=0.5) = frequency (f_osc / track f) within 50 cent of f0, 2f0 or 3f0 of the lowest sounding '
           'MIDI bass note (octave tp from YIN agreement; bass MIDI from the original train path). Wrong-note energy (v1.4): weight (A*c*sigma)^2 (P1 (a*fade)^2) over voices with '
           'weight>0 per hop with tc>0.5 s; "right" if within 50 cent of 0.5,1,2,3 x any note sounding at tc in ANY MIDI file of the track (drums included; the bass MIDI also '
           'octave-shifted by tp), from ~/datasets/slakh2100_midi/train. Variants reported: b = +-60 ms note tolerance, c = drum MIDI excluded, w23 = weights a_2^2+a_3^2. Primary = a')
    return dict(name=name, tp=ref['tp'], agree=ref['agree'], loud_hops=int(loud.sum()), covered=int(cov_ok.sum()), wrong=acc['a'][1], total=acc['a'][0],
                wrong_tol=acc['b'][1], total_tol=acc['b'][0], wrong_nodrum=acc['c'][1], total_nodrum=acc['c'][0], wrong23=acc['w23'][1], total23=acc['w23'][0],
                n_midi_files=len(ref['item']['all_midis']), n_notes_all=len(ref['allnotes']))


def v6(ctx, names):
    items = []
    for n in names:
        log('V6', n)
        items.append(v6_item(ctx, n))
    cov = sum(i['covered'] for i in items) / max(sum(i['loud_hops'] for i in items), 1)
    wr = sum(i['wrong'] for i in items) / max(sum(i['total'] for i in items), 1e-30)
    wt = sum(i['wrong_tol'] for i in items) / max(sum(i['total_tol'] for i in items), 1e-30)
    w23 = sum(i['wrong23'] for i in items) / max(sum(i['total23'] for i in items), 1e-30)
    wn = sum(i['wrong_nodrum'] for i in items) / max(sum(i['total_nodrum'] for i in items), 1e-30)
    return dict(tracks=names, coverage=cov, wrong_share=wr, wrong_share_tol60=wt, wrong_share_nodrum=wn, wrong_share_w23=w23, per_track=items)


# ===================================================================================================== V7
_PH = {}


def _phone_setup():
    if _PH:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'study'))
    import phone_model as PM
    from scipy.signal import firwin2
    fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
    erb = lambda f: 24.7 * (4.37 * f / 1000 + 1)
    cams = np.arange(21.4 * np.log10(4.37 * .15 + 1), 21.4 * np.log10(4.37 * 1.5 + 1), 1.0)
    fcs = (10 ** (cams / 21.4) - 1) / 4.37 * 1000
    _PH.update(PM=PM, FIR=firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20)), fcs=fcs,
               banks=[butter(2, [fc - erb(fc) / 2, fc + erb(fc) / 2], btype='band', fs=FS, output='sos') for fc in fcs])
    fm = np.fft.rfftfreq(200, 1 / 1000); _PH['wm'] = np.where((fm >= 20) & (fm <= 200), 2 * (fm / 70) ** 2 / (1 + (fm / 70) ** 4), 0)


def roughness(y):
    """research_r4_roughness.py --phone-hz -1 (S26 Ultra model): returns total roughness (mean over 200 ms frames of the sum over ERB bands),
    its 200-600 Hz part, and the phone model gain reduction (low band max / p95, all bands max)."""
    from scipy.signal import fftconvolve
    _phone_setup(); PM = _PH['PM']; y = np.asarray(y, float)
    z, inf = PM.drc(np.stack([y, y], 1), FS)
    yp = fftconvolve(z.mean(axis=1), _PH['FIR'], 'same')
    nf = len(yp) // (FS // 5); R = np.zeros((nf, len(_PH['fcs']))); wm = _PH['wm']
    for b, sos in enumerate(_PH['banks']):
        env = resample_poly(np.abs(hilbert(sosfiltfilt(sos, yp))), 1, 48)
        for f in range(nf):
            s = env[f * 200:(f + 1) * 200]
            if len(s) < 200:
                break
            mu = s.mean() + 1e-12; Sp = np.fft.rfft(s - mu); mod = np.sqrt(np.sum(np.abs(Sp * wm) ** 2) * 2) / 200
            R[f, b] = (mod / mu) ** 2 * (np.mean(s ** 2)) ** .3
    mid = (_PH['fcs'] >= 200) & (_PH['fcs'] <= 600)
    gl = np.asarray(inf['gr_low'], float); gb = np.asarray(inf['gr_bands'], float)
    return dict(total=float(R.sum(1).mean()), mid=float(R[:, mid].sum(1).mean()), gr_low_max=float(gl.max()), gr_low_p95=float(np.percentile(gl, 95)),
                gr_all_max=float(gb.max()))


def v7_items(quick=False):
    items = []
    for t in (['Track00060', 'Track00040'] if quick else ['Track00060', 'Track00040', 'Track00031', 'Track00001']):
        it = S.slakh_item(t); items.append((t, S.load_excerpt(it['mix'], 30.0, 10.0)))
    for nm, p in S.musdb_items(3 if quick else 8):
        items.append(('musdb:' + nm, S.load_excerpt(p, 0.0, 7.0)))
    return items


def v7(ctx, quick=False):
    out = {}
    # (a) and (d) from the T60 and LOGOFF renders
    t60 = S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0)
    lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
    rows = {}
    for nm, x in (('T60', t60), ('LOGOFF', lg), ('bass+kick+pink', S.stereo(S.flicker_signals(8.0)['bass+kick+pink']))):
        r0 = ctx.render('t60' if nm == 'T60' else nm, x, 0.0, harmonic=(nm != 'LOGOFF'), voice=False); rd = ctx.render('t60' if nm == 'T60' else nm, x, -120.0)
        lay = layer_of(r0, rd); a0 = int(3 * FS) if nm != 'bass+kick+pink' else int(1 * FS)
        seg = lay[a0:a0 + int(8 * FS)] if nm != 'bass+kick+pink' else lay[a0:7 * FS]
        X = np.abs(np.fft.rfft(seg)) ** 2; f = np.fft.rfftfreq(len(seg), 1 / FS)
        hi = X[f > 1500].sum(); lo = X[(f >= 150) & (f <= 600)].sum()
        rows[nm] = dict(hi_over_lo_db=float(10 * np.log10(hi / max(lo, 1e-30) + 1e-30)))
        if nm == 'LOGOFF':
            Lb = bandpass(lay, 150, 600); e = {}
            for hit in (4.12, 4.73):
                c = 3.0 + hit; e[f'{hit}'] = float(db10(np.sum(Lb[int((c - .05) * FS):int((c + .05) * FS)] ** 2), 1e-30))
            rows[nm]['hit_energy_db'] = e
    out['a_d'] = rows
    # V7a (v1.4): both sides at out_db -18 (no limiter); the -5 dB renders above stay for V7d and as information
    rows18 = {}
    for nm, x in (('T60', t60), ('LOGOFF', lg), ('bass+kick+pink', S.stereo(S.flicker_signals(8.0)['bass+kick+pink']))):
        key = 't60' if nm == 'T60' else nm
        lay = layer_of(ctx.render(key, x, 0.0, out_db=-18.0), ctx.render(key, x, -120.0, out_db=-18.0))
        seg = lay[int(3 * FS):int(11 * FS)] if nm != 'bass+kick+pink' else lay[int(1 * FS):7 * FS]
        X = np.abs(np.fft.rfft(seg)) ** 2; f = np.fft.rfftfreq(len(seg), 1 / FS)
        rows18[nm] = dict(hi_over_lo_db=float(10 * np.log10(X[f > 1500].sum() / max(X[(f >= 150) & (f <= 600)].sum(), 1e-30) + 1e-30)))
    out['a_d18'] = rows18
    # (b)/(c)
    items = v7_items(quick); rr = {}
    for nm, x in items:
        r = ctx.render('rough_' + nm, x, 0.0)
        rr[nm] = roughness(al(r))
        log('V7b/c', nm, rr[nm]['total'])
    out['rough'] = rr
    interp('V7a (v1.4): layer = out(0)-out(-120) with BOTH renders at out_db -18 (no limiter); energy above 1.5 kHz / 150-600 Hz energy, over input time 3-11 s of the 12 s renders '
           '(bass+kick+pink: 1-7 s); per item <= -50 dB, or <= P1 + 1 dB on an item where P1 itself is above -50 dB. (The out_db -5 values are kept as information in a_d; V7d still uses the -5 renders.) V7b/c: research_r4_roughness.py (phone model -1) ported unchanged, total roughness and the phone model gain reduction "low band max" '
           '(gr_low max); items = Slakh 30-40 s of Track00060/40/31/01 and every 12th MUSDB7 train excerpt (7 s), cold start; pass rule: each item and also reported as median. '
           'V7d: layer 150-600 Hz energy within +-50 ms of 4.12 s and 4.73 s of the 40-48 s LOGOFF excerpt')
    return out


# ===================================================================================================== V9
def births_p1(vs, t_lo, t_hi):
    seen = set(); n = 0
    for h in np.flatnonzero((vs.tc >= t_lo) & (vs.tc <= t_hi)):
        for j in np.flatnonzero(vs.valid[h] & (vs.c[h] >= .5)):
            v = int(vs.vid[h][j])
            if v not in seen:
                seen.add(v); n += 1
    return n


def births_core(vs, t_lo, t_hi):
    n = 0
    for h in np.flatnonzero((vs.tc >= t_lo) & (vs.tc <= t_hi)):
        if h == 0:
            continue
        prev = {int(v): int(s) for v, s in zip(vs.vid[h - 1], vs.st[h - 1]) if v >= 0}
        for j in np.flatnonzero(vs.st[h] == 2):
            if prev.get(int(vs.vid[h][j]), 0) in (0, 1):
                n += 1
    return n


def stage_time(n):
    return (16.0 * (n - 398) + 1359.0) / FS


def v9(ctx):
    out = {}
    t60 = S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 40.0, 6.0)
    sigs = {'pink_only': (S.stereo(S.pink_only()), (.5, 9.9)),
            'music_silence_noise': (S.music_silence_noise(t60[:3 * FS], t60[3 * FS:]), (4.0, 10.9))}
    for nm, (X, (t_lo, t_hi)) in sigs.items():
        r0 = ctx.render('v9_' + nm, X, 0.0, harmonic=True, stage=True, voice=True); rd = ctx.render('v9_' + nm, X, -120.0)
        vs = voices(ctx, r0)
        births = births_core(vs, t_lo, t_hi) if ctx.algo == 15 else births_p1(vs, t_lo, t_hi)
        st = r0['stage']; ci = core_indices(st).astype(np.int64); ts_ = np.array([stage_time(int(n)) for n in (ci[0], ci[-1])])
        tt = stage_time(ci.astype(float)); sel = (tt >= t_lo) & (tt <= t_hi)
        tag = st[:, SI['tonal_after_gain']]
        e_tag = float(db10(np.mean(tag[sel] ** 2), 1e-14))
        lay = layer_of(r0, rd); e_lay = float(db10(np.mean(bandpass(lay[int(t_lo * FS):int(t_hi * FS)], 150, 600) ** 2), 1e-14))
        out[nm] = dict(births=births, births_per_s=births / (t_hi - t_lo), sustained_energy_db=e_tag, layer_energy_db_total=e_lay, window_s=[t_lo, t_hi])
    interp('V9: births = new tracks reaching fade>=0.5 (P1) / voices entering ON from empty or CAND (core) with tc in the scored window; energy = 10log10 mean square '
           'of the stage-capture column tonal_after_gain (sustained path only, v1.3) over the window mapped with core index n -> input time (16(n-398)+1359)/48000 s, '
           'floored at -140 dB; composite scored on input time 4-10.9 s; pink-only on 0.5-9.9 s')
    return out


# ===================================================================================================== V8
def v8(ref_path, new_path, algo_new, res, reps=3):
    x = S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 30.0, 60.0)
    libs = {'p1': (RP.api(str(ref_path)), 6, None), 'new': (RP.api(str(new_path)), algo_new, res)}
    times = {k: [] for k in libs}; blocks = {k: [] for k in libs}
    for rep in range(reps):
        for k in ('p1', 'new') if rep % 2 == 0 else ('new', 'p1'):
            lib, algo, rs = libs[k]
            e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
            if algo == 15 and rs is not None:
                set_resultant(lib, e, rs)
            y = x.copy(); bt = []
            for off in range(0, len(y), 256):
                b = y[off:off + 256]; t0 = time.perf_counter(); lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b)); bt.append(time.perf_counter() - t0)
            e.close(); times[k].append(sum(bt)); blocks[k].append(np.array(bt) * 1e6)
    res_ = {}
    for k in libs:
        bt = np.concatenate(blocks[k])
        res_[k] = dict(total_s_min=min(times[k]), total_s_all=times[k], block_us_mean=float(bt.mean()), block_us_p999=float(np.percentile(bt, 99.9)),
                       block_us_max_median_over_reps=float(np.median([b.max() for b in blocks[k]])))
    res_['ratio_mean'] = res_['new']['total_s_min'] / res_['p1']['total_s_min']
    interp('V8: Track00060 30-90 s stereo, block 256 (= one hop), host wall time of pvb_process summed per run, min over %d interleaved runs per build; '
           'worst hop time = per-256-sample-block time (one hop plus the rest of the chain) max, median over runs' % reps)
    return res_


# ===================================================================================================== V0
V0_HDR = [i for i in range(2, 17)] + [18] + list(range(21, 28))     # v1.4: header field 1 (algorithm id) is excluded


def v0(ref_path, new_path, quick=True):
    ref = RP.api(str(ref_path)); new = RP.api(str(new_path)); out = dict(bit_identical={}, tracker={}, switch={})
    bass = S.stereo(S.bass_notes(3.0)); noise = S.stereo(S.pink_only(3.0)); t60 = S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 30.0, 5.0)
    lg = S.load_excerpt(S.LOGOFF, 40.0, 5.0)
    sigs = {'bass': bass, 'pink': noise, 'T60': t60, 'LOGOFF': lg}
    for sr in (48000, 44100):
        for nm, x in sigs.items():
            xs = x if sr == 48000 else np.ascontiguousarray(resample_poly(x, 147, 160, axis=0), np.float32)
            for blk in ((256, 4096) if quick else (1, 64, 480, 4096)):
                if blk == 1 and nm in ('T60', 'LOGOFF'):
                    continue
                md = 0.0
                for a in range(0, 15):
                    ya = T.Engine(ref, sr, vb_on=1, vb_algo=a, ramp_ms=0).process(xs, block=blk)
                    yb = T.Engine(new, sr, vb_on=1, vb_algo=a, ramp_ms=0).process(xs, block=blk)
                    md = max(md, float(np.max(np.abs(ya.astype(np.float64) - yb))))
                out['bit_identical'][f'{sr}/{nm}/b{blk}'] = md
    for nm in ('bass', 'T60'):
        ra = render_raw(ref, sigs[nm], 6, harmonic=True); rb = render_raw(new, sigs[nm], 15, harmonic=True)
        n = min(len(ra['harm']), len(rb['harm']))
        hd = {i: float(np.max(np.abs(ra['harm'][:n, i] - rb['harm'][:n, i]))) for i in V0_HDR}
        tk = ra['harm'][:n, 28:].reshape(n, 12, 56)[:, :, :14] - rb['harm'][:n, 28:].reshape(n, 12, 56)[:, :, :14]
        out['tracker'][nm] = dict(rows=[len(ra['harm']), len(rb['harm'])], header_maxdiff={k: v for k, v in hd.items() if v != 0},
                                  track_fields_0_13_maxdiff=float(np.max(np.abs(tk))))
    # 6 -> 14 -> 6 old vs new, and 6 -> 15 -> 6 in the new build alone
    def seq(lib, algos, x):
        e = T.Engine(lib, FS, vb_on=1, vb_algo=algos[0], ramp_ms=0); n = len(x) // len(algos); y = np.ascontiguousarray(x, np.float32).copy()
        for i, a in enumerate(algos):
            if i:
                e.set(vb_algo=a)
            seg = y[i * n:(i + 1) * n if i < len(algos) - 1 else len(y)]
            for off in range(0, len(seg), 256):
                b = seg[off:off + 256]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        e.close(); return y
    xs = t60; n = len(xs) // 3
    out['switch']['6-14-6 old vs new maxdiff'] = float(np.max(np.abs(seq(ref, [6, 14, 6], xs) - seq(new, [6, 14, 6], xs))))
    # primary: the last 6 segment of 6->15->6 vs the CONTINUOUS 6 on the same input (a switch back keeps the tracker history, so a cold start is not the reference)
    third = seq(new, [6, 15, 6], xs)
    out['switch']['6-15-6 new: last 6 vs continuous 6 maxdiff (primary)'] = float(np.max(np.abs(third[2 * n:] - seq(new, [6], xs)[2 * n:])))
    out['switch']['6-15-6 new: last 6 vs a cold 6 started at the segment (secondary)'] = float(np.max(np.abs(third[2 * n:] - seq(new, [6], xs[2 * n:]))))
    out['switch']['grounding: ref 6-6-6 last segment vs continuous 6 maxdiff (must be 0)'] = float(np.max(np.abs(seq(ref, [6, 6, 6], xs)[2 * n:] - seq(ref, [6], xs)[2 * n:])))
    return out


# ===================================================================================================== checks
def measure_all(ctx, which, quick=False, v6names=None):
    M = {}
    steps = [('V1', lambda: v1(ctx)), ('V2', lambda: v2(ctx)), ('V3bare', lambda: v3_bare(ctx)), ('V3c', lambda: v3c(ctx)), ('V3h', lambda: v3h(ctx)),
             ('V3e', lambda: v3e(ctx)), ('V3f', lambda: v3f(ctx)), ('V3g', lambda: v3g(ctx)), ('V3i', lambda: v3i(ctx)), ('V4', lambda: v4(ctx)),
             ('V5', lambda: v5(ctx)), ('V6', lambda: v6(ctx, v6names)), ('V7', lambda: v7(ctx, quick)), ('V9', lambda: v9(ctx))]
    for key, fn in steps:
        if which and not any(key.lower().startswith(w.lower()) or w.lower().startswith(key.lower()) for w in which):
            continue
        t0 = time.time(); log('start', key)
        try:
            M[key] = fn()
        except Exception as ex:
            import traceback
            M[key] = dict(error=repr(ex), trace=traceback.format_exc()[-1500:]); log('FAILED', key, repr(ex))
        log('done', key, f'{time.time() - t0:.0f}s')
    return M


def g(d, *path, default=None):
    for p in path:
        if d is None:
            return default
        try:
            d = d[p]
        except (KeyError, IndexError, TypeError):
            return default
    return d


def make_checks(M, R, algo):
    """list of dict(id, desc, value, op, limit, ok) -- M candidate metrics, R the P1 reference metrics (same code)."""
    C_ = []

    def add(id_, desc, val, op, lim, p1=None, note=''):
        ok = None
        if val is not None and lim is not None and not (isinstance(val, float) and np.isnan(val)):
            if op == '<=':
                ok = bool(val <= lim)
            elif op == '>=':
                ok = bool(val >= lim)
            elif op == 'abs<=':
                ok = bool(abs(val) <= lim)
            elif op == 'in':
                ok = bool(lim[0] <= val <= lim[1])
        C_.append(dict(id=id_, desc=desc, value=val, op=op, limit=lim, ok=ok, p1=p1, note=note))
    v1m, v1r = M.get('V1', {}), R.get('V1', {})
    # V1a: compare A with P1 reference tr.a by core index
    a = g(v1m, 'arrays'); ar = g(v1r, 'arrays')
    val = None
    if a and ar:
        cm = dict(zip(a['core'], a['A'])); cr = dict(zip(ar['core'], ar['a_p1']))
        d = [20 * np.log10(cm[c] / cr[c]) for c in cm if c in cr and cm[c] and cr[c] and cm[c] > 0 and cr[c] > 0]
        val = float(np.median(d)) if d else None
    add('V1a', 'trace A / P1 tr.a (median dB)', val, 'abs<=', .5)
    lv = g(v1m, 'layer_level_db'); lr = g(v1r, 'layer_level_db')
    add('V1b', 'layer 150-600 Hz level re P1 (dB, voicing 0)', None if lv is None or lr is None else lv - lr, 'abs<=', 1.0)
    for k in ('k2', 'k3'):
        add(f'V2.{k}', f'|dphi| layer vs original, {k[1]}x100 Hz (rad)', g(M, 'V2', k, 'dphi_mean_rad'), 'abs<=', .3, p1=g(R, 'V2', k, 'dphi_mean_rad'))
    b = M.get('V3bare', {}); br = R.get('V3bare', {})
    add('V3a', '150-600 Hz cycle-mean peak (ms)', g(b, 'v3a', 'peak_ms'), 'in', (11, 31), p1=g(br, 'v3a', 'peak_ms'))
    add('V3b', '300 Hz layer/input range 40-440 ms (dB)', g(b, 'v3b', 'range_db'), '<=', 4.0, p1=g(br, 'v3b', 'range_db'))
    c = M.get('V3c', {}); cr_ = R.get('V3c', {})
    add('V3c.enter', 'stepwise 25 dB: f_osc within 2 % of new note, median (ms)', g(c, 'enter_ms_median'), '<=', 30.0, p1=g(cr_, 'enter_ms_median'))
    add('V3c.range', 'stepwise 25 dB: in-note ratio range 15-110 ms, median (dB)', g(c, 'range_db_median'), '<=', 6.0, p1=g(cr_, 'range_db_median'))
    nn = g(c, 'n_notes'); nl = g(c, 'notes_with_low_bin')
    add('V3c.lowbin', 'stepwise 25 dB: notes with a 20 ms bin > 6 dB under the note median', nl, '<=', 0, p1=g(cr_, 'notes_with_low_bin'))
    add('V3d', 'pre-echo rise [t0-30, t0] ms (dB, median)', g(b, 'v3d', 'rise_db_median'), '<=', 1.0, p1=g(br, 'v3d', 'rise_db_median'))
    h = M.get('V3h', {}); hr = R.get('V3h', {})
    add('V3h.bare.rise90', 'bare 100 Hz note (from silence) 90 % rise (ms)', g(b, 'v3h_bare', 'tailnote_rise90_ms'), '<=', 25.0, p1=g(br, 'v3h_bare', 'tailnote_rise90_ms'))
    add('V3h.bare.tail', 'bare note -20 dB tail (ms)', g(b, 'v3h_bare', 'tail_ms'), '<=', 40.0, p1=g(br, 'v3h_bare', 'tail_ms'))
    add('V3h.25.rise90', 'line SNR 25 dB 90 % rise (ms)', g(h, 'snr25', 'rise90_ms'), '<=', 25.0, p1=g(hr, 'snr25', 'rise90_ms'))
    add('V3h.25.tail', 'line SNR 25 dB tail (ms)', g(h, 'snr25', 'tail_ms'), '<=', 40.0, p1=g(hr, 'snr25', 'tail_ms'))
    add('V3h.6.rise90', 'line SNR 6 dB 90 % rise (ms)', g(h, 'snr6', 'rise90_ms'), '<=', 70.0, p1=g(hr, 'snr6', 'rise90_ms'))
    add('V3h.6.tail', 'line SNR 6 dB tail (ms)', g(h, 'snr6', 'tail_ms'), '<=', 90.0, p1=g(hr, 'snr6', 'tail_ms'))
    e = M.get('V3e', {}); er = R.get('V3e', {})
    for df in ('df4', 'df10'):
        vals = [g(e, df, 'voices', k, 'median_abs_err_db') for k in (g(e, df, 'voices') or {})]
        add(f'V3e.{df}.A', f'two tones {df[2:]} Hz apart: worst voice median |A error| (dB)', max(vals) if vals else None, '<=', 1.5,
            p1=max([g(er, df, 'voices', k, 'median_abs_err_db') for k in (g(er, df, 'voices') or {})] or [None]) if g(er, df, 'voices') else None)
        add(f'V3e.{df}.beat', f'two tones {df[2:]} Hz apart: layer beating depth - input depth (dB)', g(e, df, 'depth_excess_db'), '<=', 3.0, p1=g(er, df, 'depth_excess_db'))
    add('V3f', 'weak tail + 110 Hz attack: layer 90 % time (ms)', g(M, 'V3f', 't90_ms'), '<=', 25.0, p1=g(R, 'V3f', 't90_ms'))
    for f_ in ('35', '45'):
        gg = g(M, 'V3g', f_) or {}
        have = bool(gg)
        add(f'V3g.{f_}.on', f'{f_} Hz note: ON within 2 hops of the track\'s first appearance (hops)', (gg.get('on_after_first_hop') if gg.get('on_found') else float('inf')) if have else None,
            '<=', 2.0, p1=g(R, 'V3g', f_, 'on_after_first_hop') if g(R, 'V3g', f_, 'on_found') else ('never ON' if g(R, 'V3g', f_) else None))
        add(f'V3g.{f_}.noREL', f'{f_} Hz note: hops without an ON voice after first ON', (gg.get('off_hops_during_note') if gg.get('on_found') else float('inf')) if have else None,
            '<=', 0, p1=g(R, 'V3g', f_, 'off_hops_during_note'))
    i = M.get('V3i', {})
    add('V3i.trans', 'chatter tone on SNR 8 dB: ON/REL transitions per second', g(i, 'transitions_per_s'), '<=', 1.0, p1=g(R, 'V3i', 'transitions_per_s'))
    fr = g(i, 'frac_c_below_half'); ok_ = None if fr is None else (fr <= .10 or bool(g(i, 'stays_below_half')))
    C_.append(dict(id='V3i.c', desc='c < 0.5 for <= 10 % of the time (or continuously below)', value=fr, op='<=', limit=.10, ok=ok_, p1=g(R, 'V3i', 'frac_c_below_half'), note=''))
    for nm in ('bass+pink', 'bass+kick+pink'):
        v = g(M, 'V4', nm) or {}; r = g(R, 'V4', nm) or {}
        add(f'V4a.{nm}', f'{nm}: std of per-note mean layer/input (dB)', v.get('std_between_notes_db'), '<=', 1.5, p1=r.get('std_between_notes_db'))
        add(f'V4b.{nm}', f'{nm}: bins > 6 dB under the note median', v.get('low_bin_frac'), '<=', .02, p1=r.get('low_bin_frac'))
        add(f'V4c.{nm}', f'{nm}: std of A after the known envelope (dB)', v.get('a_std_db'), '<=', 1.0, p1=r.get('a_std_db'))
    v5m, v5r = M.get('V5', {}), R.get('V5', {})
    add('V5a', 'Track00060: bass-present 20 ms bins > 6 dB under the local median', g(v5m, 'drop_frac'), '<=', .05, p1=g(v5r, 'drop_frac'))
    val = None
    am, ar = g(v5m, 'arrays'), g(v5r, 'arrays')
    if am and ar:
        pm_ = np.array(am['present']) > 0; ok2 = (np.array(ar['localmax_ok']) > 0) & pm_
        d = np.array(am['layer_db'])[ok2] - np.array(ar['layer_db'])[ok2]
        val = float(np.median(d)) if len(d) else None
    add('V5b', 'Track00060: layer level re P1 where P1 has no gap (median dB)', val, 'abs<=', 2.0)
    v6m, v6r = M.get('V6', {}), R.get('V6', {})
    add('V6a', 'pitch coverage (core - P1, percentage points)', None if not v6m or not v6r or 'coverage' not in v6m else 100 * (v6m['coverage'] - v6r['coverage']), '>=', 5.0,
        p1=100 * v6r['coverage'] if 'coverage' in v6r else None)
    add('V6b', 'wrong-note energy share (core - P1, percentage points)', None if not v6m or not v6r or 'wrong_share' not in v6m else 100 * (v6m['wrong_share'] - v6r['wrong_share']), '<=', 2.0,
        p1=100 * v6r['wrong_share'] if 'wrong_share' in v6r else None)
    v7m, v7r = M.get('V7', {}), R.get('V7', {})
    for nm in ('T60', 'LOGOFF', 'bass+kick+pink'):
        p1v = g(v7r, 'a_d18', nm, 'hi_over_lo_db')
        lim = -50.0 if (p1v is None or p1v <= -50.0) else p1v + 1.0          # v1.4: where P1 itself is above -50 dB the item's limit is P1 + 1 dB
        add(f'V7a.{nm}', f'{nm}: layer energy >1.5 kHz re 150-600 Hz at out_db -18 (dB)', g(v7m, 'a_d18', nm, 'hi_over_lo_db'), '<=', lim, p1=p1v)
    rm, rr = g(v7m, 'rough') or {}, g(v7r, 'rough') or {}
    common = [k for k in rm if k in rr and 'total' in rm[k] and 'total' in rr[k]]
    if common:
        pct = [100 * (rm[k]['total'] / rr[k]['total'] - 1) for k in common]
        dgr = [rm[k]['gr_low_max'] - rr[k]['gr_low_max'] for k in common]
        add('V7b', 'phone-model roughness re P1: worst item (%)', max(pct), '<=', 5.0, note=f'median {np.median(pct):+.1f} %')
        add('V7c', 'phone-model low-band GR max re P1: worst item (dB)', max(dgr), '<=', .5, note=f'median {np.median(dgr):+.2f} dB')
    else:
        add('V7b', 'phone-model roughness re P1: worst item (%)', None, '<=', 5.0); add('V7c', 'phone-model GR', None, '<=', .5)
    for hit in ('4.12', '4.73'):
        a_, b_ = g(v7m, 'a_d', 'LOGOFF', 'hit_energy_db', hit), g(v7r, 'a_d', 'LOGOFF', 'hit_energy_db', hit)
        add(f'V7d.{hit}', f'LOGOFF hit {hit} s: layer 150-600 Hz energy re P1 (dB)', None if a_ is None or b_ is None else a_ - b_, '<=', 1.0)
    for nm in ('pink_only', 'music_silence_noise'):
        a_, b_ = g(M, 'V9', nm, 'sustained_energy_db'), g(R, 'V9', nm, 'sustained_energy_db')
        add(f'V9e.{nm}', f'{nm}: sustained-path energy re P1 (dB)', None if a_ is None or b_ is None else a_ - b_, '<=', 3.0)
        a_, b_ = g(M, 'V9', nm, 'births_per_s'), g(R, 'V9', nm, 'births_per_s')
        add(f'V9b.{nm}', f'{nm}: births per second', a_, '<=', b_ if b_ is not None else None, p1=b_)
    return C_


def summarize_md(label, meta, M, checks, R_is_self):
    L = [f'# Resultant core metrics: {label}', '', f'spec {SPEC}; lib `{meta["lib"]}` algo {meta["algo"]} resultant {meta["resultant"]}; '
         f'source commit {meta.get("source_commit")}; ref lib {meta["ref_lib"]} ({meta.get("ref_commit")})', '',
         '| id | what | value | limit | P1 | pass |', '|---|---|---|---|---|---|']
    f = lambda v: 'n/a' if v is None else (f'{v:.3g}' if isinstance(v, (int, float)) else str(v))
    for c in checks:
        lim = c['limit']; lim = f'[{lim[0]}, {lim[1]}]' if isinstance(lim, tuple) else f(lim)
        L.append(f'| {c["id"]} | {c["desc"]} | {f(c["value"])} | {c["op"]} {lim} | {f(c["p1"])} | {"PASS" if c["ok"] else "FAIL" if c["ok"] is False else "n/a"} |')
    L += ['', '## Interpretations', ''] + [f'- {n}' for n in NOTES]
    return '\n'.join(L) + '\n'


def code_hash():
    h = hashlib.sha256()
    for p in (Path(__file__), Path(__file__).with_name('research_core_signals.py')):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lib', required=True); ap.add_argument('--algo', type=int, required=True)
    ap.add_argument('--resultant', default='', help='spec 5.8 names: voicing,levelDb,ampSource,snrOnDb,snrOffDb,... as k=v,k=v')
    ap.add_argument('--label', required=True); ap.add_argument('--ref-lib', default=str(REF_LIB))
    ap.add_argument('--ref-json', default='', help='cached P1 metrics (default <outroot>/p1_baseline/results.json); recomputed if missing/stale')
    ap.add_argument('--outroot', default=str(OUT_ROOT)); ap.add_argument('--metrics', default='', help='comma list, e.g. V1,V3c,V4')
    ap.add_argument('--quick', action='store_true'); ap.add_argument('--v8', action='store_true'); ap.add_argument('--v0', action='store_true')
    ap.add_argument('--v6-count', type=int, default=0, help='debug: use only the first N V6 tracks')
    a = ap.parse_args()
    which = [w for w in a.metrics.split(',') if w]
    res = parse_kv(a.resultant) if a.algo == 15 else None
    v6names = S.v6_tracks()[:(a.v6_count or None)]
    outdir = Path(a.outroot) / a.label; outdir.mkdir(parents=True, exist_ok=True)
    is_ref = (os.path.realpath(a.lib) == os.path.realpath(a.ref_lib) and a.algo == 6)
    ctx = Ctx(a.lib, a.algo, res, a.label)
    t0 = time.time(); M = measure_all(ctx, which, a.quick, v6names)
    meta = dict(lib=a.lib, lib_sha=sha256_file(a.lib), algo=a.algo, resultant=res, ref_lib=a.ref_lib, source_commit=T.source_commit(a.lib),
                ref_commit=T.source_commit(a.ref_lib), spec=SPEC, code_hash=code_hash(), v6_tracks=v6names, seconds=time.time() - t0,
                voice_trace_mismatch=ctx.voice_mismatch, wrapper=('present' if CA else 'missing: ' + CA_ERR), date=time.strftime('%F %T'),
                latency=None)
    ref_path = Path(a.ref_json) if a.ref_json else Path(a.outroot) / 'p1_baseline' / 'results.json'
    if is_ref:
        R = M
    else:
        R = None
        if ref_path.exists():
            j = json.loads(ref_path.read_text())
            if j['meta'].get('code_hash') == code_hash() and j['meta'].get('v6_tracks') == v6names:
                R = j['metrics']
            else:
                log('cached P1 baseline is stale (code or V6 set changed); recomputing')
        if R is None:
            rctx = Ctx(a.ref_lib, 6, None, 'p1_baseline')
            R = measure_all(rctx, which, a.quick, v6names)
    if a.v8 and not is_ref:
        M['V8'] = v8(a.ref_lib, a.lib, a.algo, res)
    elif a.v8:
        M['V8'] = v8(a.ref_lib, a.lib, 6, None)
    if a.v0 and not is_ref:
        M['V0'] = v0(a.ref_lib, a.lib)
    checks = make_checks(M, R, a.algo)
    if M.get('V8'):
        add_ = dict(id='V8', desc='host mean time re P1', value=M['V8']['ratio_mean'], op='<=', limit=1.6, ok=M['V8']['ratio_mean'] <= 1.6, p1=1.0, note='')
        checks.append(add_)
    out = dict(meta=meta, interpretations=NOTES, definitions=S.DEFS, metrics=M, checks=checks)
    (outdir / 'results.json').write_text(json.dumps(jsonable(out), indent=1))
    (outdir / 'summary.md').write_text(summarize_md(a.label, meta, M, checks, is_ref))
    print((outdir / 'summary.md').read_text())
    if is_ref and not (Path(a.outroot) / 'p1_baseline' / 'results.json').exists() and a.label != 'p1_baseline':
        pass


if __name__ == '__main__':
    main()
