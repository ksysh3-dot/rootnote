#!/usr/bin/env python3
"""Experimental layer options (P_X_SMOOTH, P_X_RISE, P_X_S1M, P_X_DENSE; pvb_layer_condition.h).

    ./build_host.sh && python3 test_experimental.py [--baseline-ref SHA | --baseline LIB] [--report out.json]

Checks
  - all four off: report bit identity separately from bounded float32 compatibility with the historical build.
    --baseline-ref builds that engine
    from a git commit (sources taken with `git show`, fetched with --depth 1 if missing); --baseline uses a built
    libpvbcapi.so. Without either, only the in-tree checks below run (CI passes --baseline-ref).
  - in-tree: an option switched on and off again leaves the layer untouched once it has blended out (bit exact
    against a run that never had it on); S1m on a model other than P1 changes nothing; block-size invariance.
  - per option: finite output, never boosts (layer with option / layer without <= 1, same generator), floors held,
    behaviour on synthetic bursts (smooth: less 1-8 Hz layer modulation; rise: onset cut, steady state untouched;
    dense: up to 6 dB while the 500-4000 Hz band is louder than usual, back afterwards).
  - S1m equals the research hook (GenResearch52 envelope, pvb_set_gen_research) with the layer 2 dB lower.
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_engine import Engine, FP, P, load_lib  # noqa: E402

X = dict(X_SMOOTH=29, X_RISE=30, X_S1M=31, X_DENSE=32)
P.update(X)
P1, D2 = 6, 7
RESULTS = []


def check(name, ok, **info):
    RESULTS.append(dict(name=name, ok=bool(ok), **{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}))
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + ' '.join(f'{k}={v:.4g}' if isinstance(v, float) else f'{k}={v}'
                                                                   for k, v in info.items()) if info else ''))


def music(sr, seconds=8.0, seed=3, dense_from=None, dense_to=None, dense_db=10.0):
    """Bass notes with gaps, kicks every 0.5 s, and a 500-4000 Hz noise bed (louder in [dense_from, dense_to))."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    notes = [41.2, 55.0, 49.0, 61.7, 46.2, 55.0, 73.4, 41.2]
    for k in range(int(seconds / 0.75)):
        f0 = notes[k % len(notes)]
        a, b = int(k * 0.75 * sr), min(n, int((k * 0.75 + 0.6) * sr))
        tt = t[a:b] - t[a]
        x[a:b] += 0.22 * np.exp(-tt / 0.4) * sum(np.sin(2 * np.pi * f0 * h * tt) / h for h in range(1, 4))
    for st in np.arange(0.25, seconds, 0.5):
        i0 = int(st * sr)
        m = min(n - i0, int(0.3 * sr))
        tt = np.arange(m) / sr
        x[i0:i0 + m] += 0.35 * np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-tt / 0.02)) / sr) * np.exp(-tt / 0.12)
    bed = sosfilt(butter(4, [500, 4000], 'bandpass', fs=sr, output='sos'), rng.standard_normal(n)) * 0.02
    if dense_from is not None:
        g = np.ones(n)
        g[int(dense_from * sr):int(dense_to * sr)] = 10 ** (dense_db / 20)
        bed *= g
    x += bed
    return np.column_stack([x, 0.9 * x + 0.1 * np.roll(x, 7)]).astype(np.float32)


class Capture:
    """Engine with the diagnostic layer tap (layer after the options, before the mix; limiter delay included)."""

    def __init__(self, lib, sr, **kw):
        self.lib = lib
        self.fields = 32 + lib.pvb_param_count()
        self.e = Engine(lib, sr, **kw)
        lib.pvb_set_diagnostic_capture(self.e.h, 1)

    def run(self, x, block=4096):
        outs, lays = [], []
        for s in range(0, len(x), block):
            y = self.e.process(x[s:s + block], block=block)
            lay = np.empty_like(y)
            full = np.empty_like(y)
            tr = np.empty(self.fields, np.float32)
            assert self.lib.pvb_copy_diagnostic(self.e.h, lay.ctypes.data_as(FP), full.ctypes.data_as(FP), y.size,
                                                tr.ctypes.data_as(FP), self.fields) == 1
            outs.append(y)
            lays.append(lay)
        return np.concatenate(outs), np.concatenate(lays)

    def set(self, **kw):
        self.e.set(**kw)

    def close(self):
        self.e.close()


def setup(lib):
    lib.pvb_set_diagnostic_capture.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.pvb_copy_diagnostic.argtypes = [ctypes.c_void_p, FP, FP, ctypes.c_int, FP, ctypes.c_int]
    lib.pvb_copy_diagnostic.restype = ctypes.c_int
    if hasattr(lib, 'pvb_set_gen_research'):
        lib.pvb_set_gen_research.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                             ctypes.POINTER(ctypes.c_double), ctypes.c_int]
    return lib


QUIET = dict(out_db=-24, ramp_ms=0)  # limiter idle: the captured layer is the generator x options x level


def gain_of(on, off, rel=0.05):
    """Per-sample gain where the reference layer is not near a zero crossing (same generator on both sides)."""
    a = np.abs(off).max(axis=1)
    m = a > rel * np.abs(off).max()
    r = np.abs(on).max(axis=1)[m] / a[m]
    return r, m


def env_db(v, sr, ms=20):
    p = sosfilt(butter(2, 1 / (2 * np.pi * ms * 1e-3), fs=sr, output="sos"), (v ** 2).mean(axis=1))
    return 10 * np.log10(np.maximum(p, 1e-14))


# ------------------------------------------------------------------------------------------------ bit exactness
def build_baseline(ref, out_dir):
    root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, text=True).strip()
    if subprocess.run(['git', 'cat-file', '-e', ref + '^{commit}'], cwd=root).returncode != 0:
        subprocess.check_call(['git', 'fetch', '--quiet', '--depth', '1', 'origin', ref], cwd=root)
    src = os.path.join(out_dir, 'src')
    os.makedirs(src, exist_ok=True)
    files = subprocess.check_output(['git', 'ls-tree', '--name-only', ref, 'app/src/main/cpp/libpvb/'], cwd=root,
                                    text=True).split()
    for f in files + ['tools/pvb-harness/pvb_capi.cpp']:
        with open(os.path.join(src, os.path.basename(f)), 'wb') as fh:
            fh.write(subprocess.check_output(['git', 'show', f'{ref}:{f}'], cwd=root))
    lib = os.path.join(out_dir, 'libpvbcapi_baseline.so')
    cpp = [os.path.join(src, f) for f in ('pvb_engine.cpp', 'pvb_analysis.cpp', 'pvb_vb.cpp', 'pvb_vb52.cpp', 'pvb_capi.cpp')]
    subprocess.check_call([os.environ.get('CXX', 'g++'), '-std=c++17', '-O2', '-fno-fast-math', '-fPIC', '-shared',
                           '-I' + src, *cpp, '-o', lib])
    return lib


def t_baseline(lib, base_path, label):
    base = setup(load_lib(base_path))
    cases = []
    for sr in (48000, 44100):
        x = music(sr, 6.0)
        for algo in (None, 0, 1, 2, 3, 4, 5, P1, D2, 8, 9, 10):
            kw = dict(vb_on=0) if algo is None else dict(vb_on=1, vb_algo=algo, vb_level_db=9)
            a = Engine(lib, sr, **kw)
            a.set(x_smooth=0, x_rise=0, x_s1m=0, x_dense=0)
            b = Engine(base, sr, **kw)
            ya = a.process(x, blocks=[480, 1024, 4096, 333])
            yb = b.process(x, blocks=[480, 1024, 4096, 333])
            # a mid-stream model switch and a level change (the switching path must not differ either)
            if algo is not None:
                a.set(vb_algo=P1 if algo != P1 else D2, vb_level_db=4)
                b.set(vb_algo=P1 if algo != P1 else D2, vb_level_db=4)
                ya = np.concatenate([ya, a.process(x[:sr * 2])])
                yb = np.concatenate([yb, b.process(x[:sr * 2])])
            error = float(np.max(np.abs(ya.astype(np.float64) - yb.astype(np.float64))))
            peak = float(max(np.max(np.abs(ya)), np.max(np.abs(yb))))
            # Independently compiled historical code may differ at float32 rounding boundaries. The base branch
            # already failed by 2.328e-10 on 2026-10-27 (run 40434973221), before acoustic-lab changes.
            # Keep bit identity visible; permit at most two float32 epsilons of the peak, not a fixed dB/audio floor.
            bound = 2 * np.finfo(np.float32).eps * peak + np.finfo(np.float32).tiny
            cases.append(dict(sr=sr, algo=-1 if algo is None else algo, equal=bool(np.array_equal(ya, yb)),
                              max_diff=error, float32_bound=float(bound), compatible=bool(np.isfinite(error) and error <= bound)))
            a.close()
            b.close()
    bad = [c for c in cases if not c['compatible']]
    check(f'all options off compatible with historical engine at {label} (float32 bound; exactness reported separately)',
          not bad, cases=len(cases), bit_exact_cases=sum(c['equal'] for c in cases),
          worst=max(c['max_diff'] for c in cases), details=cases)
    # A gain mutation far below the app's adjustment steps must still fail this compatibility criterion.
    probe = np.array([-.1, .025, 0, .08], np.float32)
    bound = 2 * np.finfo(np.float32).eps * float(np.max(np.abs(probe)))
    changed = probe.astype(np.float64) * (1 + 1e-4)
    check('historical tolerance control rejects a 0.01% gain mutation', float(np.max(abs(changed - probe))) > bound)


def t_off_after_blend(lib, sr=48000):
    """Option on, then off: once blended out (100 ms) the layer equals a run that never had it, bit for bit."""
    x = music(sr, 6.0)
    for opt in ('x_smooth', 'x_rise', 'x_dense'):
        ref = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9)
        e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9)
        y0 = ref.process(x[:2 * sr], block=480)
        y1 = e.process(x[:2 * sr], block=480)
        same_before = np.array_equal(y0, y1)
        e.set(**{opt: 1})
        y0 = ref.process(x[2 * sr:4 * sr], block=480)
        y1 = e.process(x[2 * sr:4 * sr], block=480)
        changed = not np.array_equal(y0, y1)
        e.set(**{opt: 0})
        y0 = ref.process(x[4 * sr:], block=480)
        y1 = e.process(x[4 * sr:], block=480)
        # blend-out 100 ms + limiter look-ahead and release (60 ms) settle well within 0.5 s
        k = int(0.5 * sr)
        check(f'{opt}: on changes the output, off again returns to the never-on output exactly (after 0.5 s)',
              same_before and changed and np.array_equal(y0[k:], y1[k:]),
              max_diff_after=float(np.max(np.abs(y0[k:] - y1[k:]))))
        ref.close()
        e.close()
    # S1m is P1-only: on D2 nothing changes at all.
    a = Engine(lib, sr, vb_on=1, vb_algo=D2, vb_level_db=9)
    b = Engine(lib, sr, vb_on=1, vb_algo=D2, vb_level_db=9, x_s1m=1)
    check('x_s1m on a model other than P1 (D2): output unchanged (bit exact)', np.array_equal(a.process(x), b.process(x)))
    a.close()
    b.close()
    # VB off: all four on change nothing.
    a = Engine(lib, sr, vb_on=0)
    b = Engine(lib, sr, vb_on=0, x_smooth=1, x_rise=1, x_s1m=1, x_dense=1)
    check('virtual bass off: all four options on change nothing (bit exact)', np.array_equal(a.process(x), b.process(x)))
    a.close()
    b.close()


def t_block_invariance(lib, sr=48000):
    x = music(sr, 4.0)
    kw = dict(vb_on=1, vb_algo=P1, vb_level_db=9, x_smooth=1, x_rise=1, x_s1m=1, x_dense=1)
    a = Engine(lib, sr, **kw)
    b = Engine(lib, sr, **kw)
    ya = a.process(x, block=4096)
    yb = b.process(x, blocks=[1, 127, 480, 1024, 333])
    check('all options on: block-size invariance (bit exact)', np.array_equal(ya, yb))
    a.close()
    b.close()


# ------------------------------------------------------------------------------------------------ per option
def layers(lib, sr, x, opts, algo=P1, level=9):
    off = Capture(lib, sr, vb_on=1, vb_algo=algo, vb_level_db=level, **QUIET)
    on = Capture(lib, sr, vb_on=1, vb_algo=algo, vb_level_db=level, **QUIET, **opts)
    yo, lo = off.run(x)
    yn, ln = on.run(x)
    off.close()
    on.close()
    return yo, lo, yn, ln


def t_bounds(lib):
    floors = dict(x_smooth=0.3, x_rise=0.2, x_dense=10 ** (-6 / 20))
    for sr in (48000, 44100):
        x = music(sr, 8.0, dense_from=5.0, dense_to=6.5)
        for opt, floor in list(floors.items()) + [('all3', floors['x_smooth'] * floors['x_rise'] * floors['x_dense'])]:
            opts = dict(x_smooth=1, x_rise=1, x_dense=1) if opt == 'all3' else {opt: 1}
            yo, lo, yn, ln = layers(lib, sr, x, opts)
            sl = slice(int(0.3 * sr), None)  # after the 100 ms blend-in
            g, _ = gain_of(ln[sl], lo[sl])
            finite = np.isfinite(yn).all() and np.isfinite(ln).all()
            check(f'{opt} @ {sr}: finite, never boosts (gain <= 1), floor held',
                  finite and g.max() <= 1 + 1e-6 and g.min() >= floor * (1 - 1e-6),
                  max_gain=float(g.max()), min_gain_db=float(20 * np.log10(g.min())),
                  mean_cut_db=float(10 * np.log10(np.mean(ln[sl] ** 2) / np.mean(lo[sl] ** 2))))
    # Nonsense input: NaN/Inf and full-scale square bursts.
    sr = 48000
    x = music(sr, 3.0) * 4
    x[sr:sr + 100] = np.nan
    x[sr + 5000:sr + 5100] = np.inf
    e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=12, x_smooth=1, x_rise=1, x_s1m=1, x_dense=1)
    y = e.process(x)
    check('all four on: NaN/Inf and +12 dB overload input -> finite output', np.isfinite(y).all())
    e.close()


def t_smooth(lib, sr=48000):
    """A bass tone whose level wobbles at 4 Hz (12 dB): the layer's 1-8 Hz modulation must shrink; tails not longer."""
    n = 8 * sr
    t = np.arange(n) / sr
    am = 10 ** ((-6 + 6 * np.sin(2 * np.pi * 4 * t)) / 20)
    tone = 0.3 * am * (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 110 * t))
    tone[int(6 * sr):] = 0.0  # stop: the tail after the note
    x = np.column_stack([tone, tone]).astype(np.float32)
    yo, lo, yn, ln = layers(lib, sr, x, dict(x_smooth=1))
    sl = slice(int(2 * sr), int(5.8 * sr))
    eo, en = env_db(lo, sr)[sl], env_db(ln, sr)[sl]
    depth_o, depth_n = np.percentile(eo, 95) - np.percentile(eo, 5), np.percentile(en, 95) - np.percentile(en, 5)
    tail = slice(int(6.0 * sr), int(6.6 * sr))
    e_tail_o, e_tail_n = np.sum(lo[tail] ** 2), np.sum(ln[tail] ** 2)
    check('x_smooth: 4 Hz layer wobble smaller (5-95% envelope range), tail energy not larger',
          depth_n < depth_o - 2.0 and e_tail_n <= e_tail_o * (1 + 1e-9),
          wobble_off_db=float(depth_o), wobble_on_db=float(depth_n),
          tail_change_db=float(10 * np.log10((e_tail_n + 1e-30) / (e_tail_o + 1e-30))))


def t_rise(lib, sr=48000):
    """Bass notes after silence: the onset is cut (>= 6 dB in the first 30 ms), the held note is left alone."""
    n = 6 * sr
    t = np.arange(n) / sr
    x = np.zeros(n)
    for st in (0.5, 2.5, 4.5):
        a, b = int(st * sr), int((st + 1.2) * sr)
        x[a:b] = 0.3 * (np.sin(2 * np.pi * 49 * t[a:b]) + 0.5 * np.sin(2 * np.pi * 98 * t[a:b]))
    x = np.column_stack([x, x]).astype(np.float32)
    yo, lo, yn, ln = layers(lib, sr, x, dict(x_rise=1))
    eo, en = env_db(lo, sr, 5), env_db(ln, sr, 5)
    onset_cut, steady = [], []
    for st in (2.5, 4.5):
        # where the layer itself starts (P1 enters some ms after the note)
        seg = slice(int(st * sr), int((st + 1.2) * sr))
        start = int(st * sr) + int(np.argmax(eo[seg] > eo[seg].max() - 20))
        w = slice(start, start + int(0.03 * sr))
        onset_cut.append(float(np.mean(eo[w] - en[w])))
        h = slice(int((st + 0.7) * sr), int((st + 1.1) * sr))
        steady.append(float(np.mean(eo[h] - en[h])))
    g, _ = gain_of(ln, lo)
    check('x_rise: layer onset after silence cut >= 6 dB (first 30 ms), held note within 0.5 dB, never boosts',
          min(onset_cut) >= 6.0 and max(steady) <= 0.5 and g.max() <= 1 + 1e-6,
          onset_cut_db=min(onset_cut), steady_cut_db=max(steady))


def t_dense(lib, sr=48000):
    """Steady bass + a 500-4000 Hz bed that jumps +10 dB for 2 s after 12 s: layer down ~6 dB there, ~0 before/after."""
    x = music(sr, 18.0, dense_from=12.0, dense_to=14.0, dense_db=10.0)
    yo, lo, yn, ln = layers(lib, sr, x, dict(x_dense=1))
    g, m = gain_of(ln, lo)
    idx = np.nonzero(m)[0]
    gd = np.full(len(lo), np.nan)
    gd[idx] = 20 * np.log10(g)
    lat = 0  # the layer tap and the dry detector are aligned; windows are generous

    def med(a, b):
        v = gd[int(a * sr) + lat:int(b * sr) + lat]
        return float(np.nanmedian(v))
    before, during, after = med(9.0, 11.9), med(12.4, 13.9), med(15.5, 17.9)
    check('x_dense: ~0 dB at the usual level, about -6 dB (cap) while the band is +10 dB, back within 1.5 s',
          before > -1.0 and -6.0 - 1e-6 <= during < -4.5 and after > -1.5 and np.nanmin(gd) >= -6.0 - 1e-6,
          before_db=before, during_db=during, after_db=after)


def t_s1m(lib, sr=48000):
    x = music(sr, 6.0)
    app = Capture(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9, x_s1m=1, **QUIET)
    hook = Capture(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=7, **QUIET)
    lib.pvb_set_gen_research(hook.e.h, 1, 0, None, 0)
    p1 = Capture(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9, **QUIET)
    ya, la = app.run(x)
    yh, lh = hook.run(x)
    yp, lp = p1.run(x)
    sl = slice(int(0.5 * sr), None)
    err = float(np.max(np.abs(la[sl] - lh[sl])) / np.max(np.abs(lh[sl])))
    diff_p1 = float(10 * np.log10(np.mean((la[sl] - lp[sl]) ** 2) / np.mean(lp[sl] ** 2)))
    check('x_s1m: layer = research hook GenResearch52 (S1 envelope) 2 dB lower; differs from P1; finite',
          err < 1e-5 and diff_p1 > -40 and np.isfinite(ya).all(), max_rel_err=err, change_vs_p1_db=diff_p1,
          layer_rms_vs_p1_db=float(10 * np.log10(np.mean(la[sl] ** 2) / np.mean(lp[sl] ** 2))))
    for c in (app, hook, p1):
        c.close()
    # switching S1m during playback goes through the VB switch fade (30 ms out, 30 ms in), no jump in time
    e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9)
    y0 = e.process(x[:sr], block=480)
    lat0 = e.latency()
    e.set(x_s1m=1)
    y1 = e.process(x[sr:2 * sr], block=480)
    e.set(x_s1m=0)
    y2 = e.process(x[2 * sr:3 * sr], block=480)
    y = np.concatenate([y0, y1, y2])
    hf = sosfilt(butter(4, 6000, 'highpass', fs=sr, output='sos'), y[:, 0])
    hf_ref = sosfilt(butter(4, 6000, 'highpass', fs=sr, output='sos'), x[:3 * sr, 0])
    check('x_s1m switched on and off while playing: same latency, finite, no click (HF > 6 kHz not above the input)',
          e.latency() == lat0 and np.isfinite(y).all() and np.max(np.abs(hf)) <= np.max(np.abs(hf_ref)) * 1.5 + 1e-4,
          hf_peak=float(np.max(np.abs(hf))), hf_input_peak=float(np.max(np.abs(hf_ref))))
    e.close()


def t_cost(lib, sr=48000):
    x = music(sr, 10.0)
    res = {}
    for name, kw in (('off', {}), ('all_on', dict(x_smooth=1, x_rise=1, x_s1m=1, x_dense=1)),
                     ('cond_only', dict(x_smooth=1, x_rise=1, x_dense=1))):
        e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=9, **kw)
        e.process(x[:sr])
        t0 = time.perf_counter()
        e.process(x, block=960)
        res[name] = (time.perf_counter() - t0) / 10.0 * 1000
        e.close()
    check('cost on the host (ms per second of audio)', res['all_on'] < 4 * max(res['off'], 1.0),
          off_ms=res['off'], all_on_ms=res['all_on'], conditioning_only_ms=res['cond_only'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(HERE, 'build/libpvbcapi.so'))
    ap.add_argument('--baseline', help='libpvbcapi.so built without the options')
    ap.add_argument('--baseline-ref', help='git commit without the options (built here)')
    ap.add_argument('--report')
    a = ap.parse_args()
    lib = setup(load_lib(a.lib))
    assert lib.pvb_param_count() >= 33, lib.pvb_param_count()   # 47 since developer mode (P_DEV_ON ...)
    d = np.zeros(lib.pvb_param_count(), np.float32)
    lib.pvb_default_params(d.ctypes.data_as(FP))
    check('defaults: all four options off', all(d[i] == 0 for i in X.values()))
    if a.baseline:
        t_baseline(lib, a.baseline, os.path.basename(a.baseline))
    elif a.baseline_ref:
        with tempfile.TemporaryDirectory() as tmp:
            t_baseline(lib, build_baseline(a.baseline_ref, tmp), a.baseline_ref[:10])
    else:
        print('[SKIP] baseline comparison (no --baseline / --baseline-ref)')
    t_off_after_blend(lib)
    t_block_invariance(lib)
    t_bounds(lib)
    t_smooth(lib)
    t_rise(lib)
    t_dense(lib)
    t_s1m(lib)
    t_cost(lib)
    failed = [r for r in RESULTS if not r['ok']]
    if a.report:
        with open(a.report, 'w') as fh:
            json.dump(dict(schema='pvb.experimental.v1', results=RESULTS), fh, indent=1, ensure_ascii=False)
    print(f'{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
