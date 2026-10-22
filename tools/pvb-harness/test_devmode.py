#!/usr/bin/env python3
"""Developer mode ("개발자 모드", general build): P_DEV_ON, P_DEV_METER and the P_D_* voicing values.

    ./build_host.sh && python3 test_devmode.py [--baseline-ref SHA | --baseline LIB] [--report out.json]

Checks
  - never used: developer mode off (any P_D_* values), and on with every value at its default, and the display meters
    on, are bit-identical to the engine before developer mode existed (--baseline-ref builds that commit, like
    test_experimental.py; CI passes it). In-tree: the same three against each other.
  - ranges: out-of-range and non-finite values are clamped (no NaN, finite output); the output stays at or below the
    -1 dBTP ceiling at the most extreme settings, also when the ceiling parameter asks for 0 dBTP.
  - each value changes the processing on P1 and acts in the documented direction (harmonic offsets at k f0, path
    gains, roll-off, output band, generator edge, release tail).
  - block-size invariance with every value moved; finite on NaN/Inf input.
  - meters: fundamental and harmonics of a 55 Hz tone, band levels, ring advancing every 5 ms, dry/layer envelopes.
"""
import argparse
import ctypes
import json
import os
import sys
import tempfile

import numpy as np
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_engine import Engine, FP, P, load_lib, true_peak_db  # noqa: E402
from test_experimental import build_baseline, music  # noqa: E402

D = dict(X_SMOOTH=29, X_RISE=30, X_S1M=31, X_DENSE=32, DEV_ON=33, DEV_METER=34, D_BOUNDARY_HZ=35, D_OUT_LO_HZ=36,
         D_OUT_HI_HZ=37, D_H2_DB=38, D_H3_DB=39, D_H4_DB=40, D_H5_DB=41, D_ROLLOFF_DB_OCT=42, D_SUST_DB=43,
         D_PERC_DB=44, D_ATTACK_MS=45, D_RELEASE_MS=46)
P.update(D)
DEFAULTS = dict(d_boundary_hz=190, d_out_lo_hz=150, d_out_hi_hz=600, d_h2_db=0, d_h3_db=0, d_h4_db=0, d_h5_db=0,
                d_rolloff_db_oct=0, d_sust_db=0, d_perc_db=0, d_attack_ms=32 / 3, d_release_ms=32)
MOVED = dict(d_boundary_hz=150, d_out_lo_hz=120, d_out_hi_hz=800, d_h2_db=-6, d_h3_db=3, d_h4_db=-3, d_h5_db=-6,
             d_rolloff_db_oct=-6, d_sust_db=-3, d_perc_db=2, d_attack_ms=5, d_release_ms=120)
P1, D2, GENTLE12 = 6, 7, 3
RESULTS = []
QUIET = dict(out_db=-24, ramp_ms=0)


def check(name, ok, **info):
    RESULTS.append(dict(name=name, ok=bool(ok), **{k: (float(v) if isinstance(v, (np.floating, float)) else v)
                                                   for k, v in info.items()}))
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + ' '.join(f'{k}={v:.4g}' if isinstance(v, float) else f'{k}={v}'
                                                                   for k, v in info.items()) if info else ''))


def setup(lib):
    lib.pvb_set_diagnostic_capture.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.pvb_copy_diagnostic.argtypes = [ctypes.c_void_p, FP, FP, ctypes.c_int, FP, ctypes.c_int]
    lib.pvb_copy_diagnostic.restype = ctypes.c_int
    if hasattr(lib, 'pvb_copy_dev_meters'):
        lib.pvb_copy_dev_meters.argtypes = [ctypes.c_void_p, FP, ctypes.c_int]
        lib.pvb_copy_dev_meters.restype = ctypes.c_int
    return lib


def tone(sr, seconds, f0=55.0, amp=0.3, on=None):
    t = np.arange(int(seconds * sr)) / sr
    x = amp * (np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t))
    if on is not None:
        x *= on(t)
    return np.column_stack([x, x]).astype(np.float32)


def layer_of(lib, sr, x, block=4096, **kw):
    """Output and the captured layer (diagnostic tap), quiet output so the limiter stays idle."""
    e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=6, **QUIET)
    e.set(**kw)
    fields = 32 + lib.pvb_param_count()
    lib.pvb_set_diagnostic_capture(e.h, 1)
    outs, lays = [], []
    for s in range(0, len(x), block):
        y = e.process(x[s:s + block], block=block)
        lay, full = np.empty_like(y), np.empty_like(y)
        tr = np.empty(fields, np.float32)
        assert lib.pvb_copy_diagnostic(e.h, lay.ctypes.data_as(FP), full.ctypes.data_as(FP), y.size,
                                       tr.ctypes.data_as(FP), fields) == 1
        outs.append(y)
        lays.append(lay)
    e.close()
    return np.concatenate(outs), np.concatenate(lays)


def band_db(v, sr, f, width=0.06):
    """Level of the component at f (FFT of the steady part), dB."""
    s = v[:, 0]
    w = np.hanning(len(s))
    spec = np.abs(np.fft.rfft(s * w))
    fr = np.fft.rfftfreq(len(s), 1 / sr)
    m = np.abs(fr - f) <= max(2.0, width * f)
    return 20 * np.log10(spec[m].max() + 1e-20)


# ------------------------------------------------------------------------------------------------ never used
def run_case(lib, sr, x, algo, extra):
    kw = dict(vb_on=0) if algo is None else dict(vb_on=1, vb_algo=algo, vb_level_db=9)
    e = Engine(lib, sr, **kw)
    if extra:
        e.set(**extra)
    y = e.process(x, blocks=[480, 1024, 4096, 333])
    if algo is not None:
        e.set(vb_algo=P1 if algo != P1 else D2, vb_level_db=4)
        y = np.concatenate([y, e.process(x[:sr * 2])])
    e.close()
    return y


VARIANTS = {
    'dev off, values moved': dict(dev_on=0, **MOVED),
    'dev on, all defaults': dict(dev_on=1, **DEFAULTS),
    'dev on, defaults, meters on': dict(dev_on=1, dev_meter=1, **DEFAULTS),
    'dev off, meters on': dict(dev_on=0, dev_meter=1, **MOVED),
}


def t_baseline(lib, base_path, label):
    base = setup(load_lib(base_path))
    worst, bad, n = 0.0, [], 0
    for sr in (48000, 44100):
        x = music(sr, 5.0)
        for algo in (None, 0, 1, 2, 3, 4, 5, P1, D2, 8, 9, 10):
            ref = run_case(base, sr, x, algo, None)
            for name, extra in VARIANTS.items():
                y = run_case(lib, sr, x, algo, extra)
                n += 1
                d = float(np.max(np.abs(y - ref)))
                worst = max(worst, d)
                if not np.array_equal(y, ref):
                    bad.append((sr, algo, name))
    check(f'never used = engine at {label} (bit exact; dev off with values moved, dev on at defaults, meters on; '
          f'VB off and all 11 models, 44.1/48 kHz, switch + level)', not bad, cases=n, worst=worst, bad=str(bad[:4]))


def t_in_tree(lib):
    sr = 48000
    x = music(sr, 5.0)
    bad = []
    for algo in (None, GENTLE12, P1, D2, 8, 9, 10):
        ref = run_case(lib, sr, x, algo, None)
        for name, extra in VARIANTS.items():
            if not np.array_equal(run_case(lib, sr, x, algo, extra), ref):
                bad.append((algo, name))
    check('in tree: dev off / dev on at defaults / meters on all equal the plain engine (bit exact)', not bad,
          bad=str(bad[:4]))


# ------------------------------------------------------------------------------------------------ ranges, safety
def t_ranges(lib):
    sr = 48000
    x = music(sr, 4.0) * 1.5
    wild = dict(dev_on=1, d_boundary_hz=1e6, d_out_lo_hz=-50, d_out_hi_hz=np.inf, d_h2_db=1e9, d_h3_db=-1e9,
                d_h4_db=np.nan, d_h5_db=99, d_rolloff_db_oct=-1e3, d_sust_db=np.nan, d_perc_db=1e4,
                d_attack_ms=-5, d_release_ms=1e9)
    e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=12, **wild)
    y = e.process(x, block=480)
    e.close()
    check('out-of-range and NaN/Inf developer values: clamped, finite output', np.isfinite(y).all())
    extreme = dict(dev_on=1, d_boundary_hz=220, d_out_lo_hz=60, d_out_hi_hz=1200, d_h2_db=12, d_h3_db=12, d_h4_db=12,
                   d_h5_db=12, d_rolloff_db_oct=-24, d_sust_db=12, d_perc_db=12, d_attack_ms=1, d_release_ms=1000)
    worst = -200.0
    for algo in (P1, GENTLE12, D2, 9):
        for sr in (48000, 44100):
            xx = music(sr, 4.0) * 2.5   # +8 dB hot input
            e = Engine(lib, sr, vb_on=1, vb_algo=algo, vb_level_db=12, out_db=12, ceil_db=0, **extreme)
            y = e.process(xx, block=960)
            e.close()
            tp = true_peak_db(y[sr // 2:])
            worst = max(worst, tp)
    check('most extreme developer settings (+12 dB everywhere, out gain +12, ceiling asked 0 dBTP): '
          'true peak <= -1 dBTP', worst <= -1.0 + 0.05, worst_true_peak_dbtp=worst)
    # the cap applies only in developer mode: with dev off the ceiling parameter is unchanged (0 dBTP allowed)
    e = Engine(lib, 48000, vb_on=1, vb_algo=P1, vb_level_db=12, out_db=12, ceil_db=0)
    tp_off = true_peak_db(e.process(music(48000, 3.0) * 2.5, block=960)[24000:])
    e.close()
    check('dev off: ceiling parameter as before (0 dBTP reachable)', tp_off > -0.5, true_peak_dbtp=tp_off)
    x = music(48000, 3.0) * 4
    x[48000:48100] = np.nan
    x[60000:60050] = np.inf
    e = Engine(lib, 48000, vb_on=1, vb_algo=P1, vb_level_db=12, x_smooth=1, x_rise=1, x_s1m=1, x_dense=1, **extreme)
    y = e.process(x)
    e.close()
    check('extreme developer values + NaN/Inf/overload input: finite', np.isfinite(y).all())


def t_block_invariance(lib):
    sr = 48000
    x = music(sr, 4.0)
    kw = dict(vb_on=1, vb_algo=P1, vb_level_db=9, dev_on=1, dev_meter=1, **MOVED)
    a, b = Engine(lib, sr, **kw), Engine(lib, sr, **kw)
    ya, yb = a.process(x, block=4096), b.process(x, blocks=[1, 127, 480, 1024, 333])
    a.close()
    b.close()
    check('developer values moved: block-size invariance (bit exact)', np.array_equal(ya, yb))


# ------------------------------------------------------------------------------------------------ effects
def t_each_value_changes(lib):
    sr = 48000
    x = music(sr, 4.0)
    ref, _ = layer_of(lib, sr, x, dev_on=1)
    quiet = []
    for k, v in MOVED.items():
        y, _ = layer_of(lib, sr, x, dev_on=1, **{k: v})
        if np.array_equal(y, ref):
            quiet.append(k)
    check('every developer value changes the P1 output when moved', not quiet, unchanged=str(quiet))


def t_directions(lib):
    sr = 48000
    x = tone(sr, 6.0, 55.0)
    st = slice(2 * sr, 6 * sr)
    _, l0 = layer_of(lib, sr, x, dev_on=1)
    # harmonic offsets: +6 dB on k=3 -> the 165 Hz component about +6 dB, 220 Hz (k=4) unchanged
    _, l3 = layer_of(lib, sr, x, dev_on=1, d_h3_db=6)
    g3 = band_db(l3[st], sr, 165) - band_db(l0[st], sr, 165)
    other = band_db(l3[st], sr, 220) - band_db(l0[st], sr, 220)
    # k=2: the model has no 2nd harmonic for a 55 Hz note (it would fall where the speaker cannot play it), so the
    # offset only acts where the table has one: a 90 Hz note, 180 Hz
    x90 = tone(sr, 6.0, 90.0)
    _, l90 = layer_of(lib, sr, x90, dev_on=1)
    _, l2 = layer_of(lib, sr, x90, dev_on=1, d_h2_db=-6)
    g2 = band_db(l2[st], sr, 180) - band_db(l90[st], sr, 180)
    check('harmonic offsets re the model table: k=3 +6 dB -> 165 Hz about +6 dB (220 Hz unchanged); k=2 -6 dB on a '
          '90 Hz note -> 180 Hz about -6 dB',
          4.5 < g3 < 7.5 and -7.5 < g2 < -4.5 and abs(other) < 1.0, k3_db=g3, k2_db=g2,
          k4_change_db=other)
    # sustained path -6 dB on a steady tone: layer about -6 dB
    _, ls = layer_of(lib, sr, x, dev_on=1, d_sust_db=-6)
    gs = 10 * np.log10(np.mean(ls[st] ** 2) / np.mean(l0[st] ** 2))
    check('sustained path -6 dB on a steady tone: layer about -6 dB', -7.5 < gs < -4.0, layer_change_db=gs)
    # roll-off: steeper above 220 Hz -> 275 Hz (k=5) lower, 165 Hz (k=3) unchanged
    _, lr = layer_of(lib, sr, x, dev_on=1, d_rolloff_db_oct=12)
    r5 = band_db(lr[st], sr, 275) - band_db(l0[st], sr, 275)
    r3 = band_db(lr[st], sr, 165) - band_db(l0[st], sr, 165)
    check('roll-off +12 dB/oct: 275 Hz lower (by about 12 x log2(275/220) = 3.9 dB), 165 Hz unchanged',
          -5.5 < r5 < -2.5 and abs(r3) < 0.5, k5_db=r5, k3_db=r3)
    # output band: high-pass up to 250 Hz -> 110 Hz much lower
    _, lo = layer_of(lib, sr, x, dev_on=1, d_out_lo_hz=250, d_out_hi_hz=1000)
    o2 = band_db(lo[st], sr, 110) - band_db(l0[st], sr, 110)
    check('output band from 250 Hz: 110 Hz component down by more than 15 dB', o2 < -15, k2_db=o2)
    # generator edge: 100 Hz -> a 150 Hz bass note barely generates any layer, at 190 Hz it does
    x150 = tone(sr, 5.0, 150.0, 0.3)
    _, lb0 = layer_of(lib, sr, x150, dev_on=1)
    _, lb1 = layer_of(lib, sr, x150, dev_on=1, d_boundary_hz=100)
    sb = slice(2 * sr, 5 * sr)
    gb = 10 * np.log10((np.mean(lb1[sb] ** 2) + 1e-20) / (np.mean(lb0[sb] ** 2) + 1e-20))
    check('generator edge 100 Hz: a 150 Hz note makes at least 10 dB less layer', gb < -10, change_db=gb)
    # release: notes that stop -> a longer release leaves a longer layer tail
    notes = tone(sr, 6.0, 55.0, on=lambda t: ((t % 1.5) < 0.8).astype(float))
    _, ln0 = layer_of(lib, sr, notes, dev_on=1)
    _, ln1 = layer_of(lib, sr, notes, dev_on=1, d_release_ms=250)
    e = Engine(lib, sr, vb_on=1, vb_algo=P1)
    e.process(notes[:4800])
    lat = e.latency()   # the layer tap is aligned with the output, which is late by the latency
    e.close()
    tail0, tail1 = [], []
    for start in (1.5, 3.0, 4.5):
        stop = int((start + 0.8) * sr) + lat + int(0.02 * sr)
        w = slice(stop, stop + int(0.6 * sr))
        tail0.append(np.sum(ln0[w] ** 2))
        tail1.append(np.sum(ln1[w] ** 2))
    tr = 10 * np.log10(np.sum(tail1) / (np.sum(tail0) + 1e-20))
    check('release 250 ms (vs 32 ms): more layer energy after the notes stop', tr > 3.0, tail_change_db=tr)
    # attack: 100 ms (vs 11 ms) -> less layer in the first 60 ms of each note, same once settled
    _, la = layer_of(lib, sr, notes, dev_on=1, d_attack_ms=100)
    on0, on1, held0, held1 = [], [], [], []
    for start in (1.5, 3.0, 4.5):
        a0 = int(start * sr)
        seg = slice(a0, a0 + int(0.8 * sr))
        first = a0 + int(np.argmax(np.abs(ln0[seg, 0]) > 0.05 * np.abs(ln0[seg, 0]).max()))
        w = slice(first, first + int(0.06 * sr))
        on0.append(np.sum(ln0[w] ** 2)); on1.append(np.sum(la[w] ** 2))
        h = slice(a0 + int(0.5 * sr), a0 + int(0.75 * sr))
        held0.append(np.sum(ln0[h] ** 2)); held1.append(np.sum(la[h] ** 2))
    oc = 10 * np.log10(np.sum(on1) / np.sum(on0))
    hc = 10 * np.log10(np.sum(held1) / np.sum(held0))
    check('attack 100 ms (vs 11 ms): onset (first 60 ms) at least 2 dB lower, held note within 0.6 dB',
          oc < -2.0 and abs(hc) < 0.6, onset_change_db=oc, held_change_db=hc)


# ------------------------------------------------------------------------------------------------ meters
def t_meters(lib):
    sr = 48000
    n = lib.pvb_dev_meter_size()
    fields = lib.pvb_dev_meter_fields()
    check('meter layout: 16 fields + 512 (dry, layer) pairs', n == 16 + 2 * 512 and fields == 16, size=n)
    e = Engine(lib, sr, vb_on=1, vb_algo=P1, vb_level_db=6, dev_on=1, dev_meter=1)
    out = np.zeros(n, np.float32)
    e.process(tone(sr, 3.0, 55.0), block=960)
    assert lib.pvb_copy_dev_meters(e.h, out.ctypes.data_as(FP), n) == n
    f0 = float(out[0])
    h = out[1:8]
    ring = out[fields:].reshape(-1, 2)
    count = float(out[10])
    check('meters on a 55 Hz tone: fundamental found, harmonics finite, k=3, 4 above -60 dBFS (k=2 not in the model)',
          abs(f0 - 55) < 3 and np.isfinite(h).all() and (h[1:3] > -60).all() and h[0] <= -100, f0=f0, h2=float(h[0]),
          h3=float(h[1]),
          h4=float(h[2]))
    check('meters: ring advances every 5 ms (3 s -> 600 entries), bin 5 ms, band levels finite',
          abs(count - 600) <= 2 and abs(out[11] - 5.0) < 0.01 and np.isfinite(out[8]) and np.isfinite(out[9]),
          ring_count=count, dry_band=float(out[8]), layer_band=float(out[9]))
    check('meters: dry low band near the tone level and the layer present in the last second',
          ring[-100:, 0].mean() > -20 and ring[-100:, 1].mean() > -60,
          dry_db=float(ring[-100:, 0].mean()), layer_db=float(ring[-100:, 1].mean()))
    # silence afterwards: the dry envelope falls first, the layer later (tail); both reach the floor
    e.process(np.zeros((sr, 2), np.float32), block=960)
    lib.pvb_copy_dev_meters(e.h, out.ctypes.data_as(FP), n)
    ring = out[fields:].reshape(-1, 2)
    check('meters: after the tone stops both envelopes fall below -80 dBFS', ring[-20:].max() < -80,
          last_max=float(ring[-20:].max()))
    e.set(dev_meter=0)
    e.process(np.zeros((960, 2), np.float32))
    e.close()
    bad = Engine(lib, sr)
    check('copy_dev_meters rejects a short buffer', lib.pvb_copy_dev_meters(bad.h, out.ctypes.data_as(FP), n - 1) == 0)
    bad.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(HERE, 'build/libpvbcapi.so'))
    ap.add_argument('--baseline')
    ap.add_argument('--baseline-ref')
    ap.add_argument('--report')
    a = ap.parse_args()
    lib = setup(load_lib(a.lib))
    assert lib.pvb_param_count() == 56, lib.pvb_param_count()  # + 9 crosstalk-cancellation values
    d = np.zeros(56, np.float32)
    lib.pvb_default_params(d.ctypes.data_as(FP))
    exp = [0, 0, 190, 150, 600, 0, 0, 0, 0, 0, 0, 0, 32 / 3, 32]
    check('defaults: developer mode off, meters off, model values', np.allclose(d[33:47], exp, atol=1e-6))
    if a.baseline:
        t_baseline(lib, a.baseline, os.path.basename(a.baseline))
    elif a.baseline_ref:
        with tempfile.TemporaryDirectory() as tmp:
            t_baseline(lib, build_baseline(a.baseline_ref, tmp), a.baseline_ref[:10])
    else:
        print('[SKIP] baseline comparison (no --baseline / --baseline-ref)')
    t_in_tree(lib)
    t_ranges(lib)
    t_block_invariance(lib)
    t_each_value_changes(lib)
    t_directions(lib)
    t_meters(lib)
    failed = [r for r in RESULTS if not r['ok']]
    if a.report:
        with open(a.report, 'w') as fh:
            json.dump(dict(schema='pvb.devmode.v1', results=RESULTS), fh, indent=1, ensure_ascii=False)
    print(f'{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
