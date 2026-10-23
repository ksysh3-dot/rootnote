#!/usr/bin/env python3
"""Crosstalk cancellation in the engine (P_XTC_*, pvb_xtc.h).

- off (mode 0) is bit-identical whatever the other XTC values are;
- on, after the 30 ms fade-in, the engine equals the plain engine fed with the prototype's output
  (tools/xtc/check_eel_port.py, the LiveProg version judged by ear), both modes, 44.1 and 48 kHz;
- switching on and off while playing is click-free and finite; silence stays silence; strong setting stays stable;
- cost on the host.

    tools/pvb-harness/build_host.sh && python3 tools/pvb-harness/test_xtc.py
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'xtc'))
import test_engine as te  # noqa: E402
import check_eel_port as port  # noqa: E402

XTC = dict(XTC_MODE=47, XTC_STRENGTH_DB=48, XTC_DIST_CM=49, XTC_HAT_CM=50, XTC_SPACING_CM=51, XTC_LO_HZ=52,
           XTC_HI_HZ=53, XTC_BAL_LO_DB=54, XTC_BAL_HI_DB=55)
te.P.update(XTC)
failures = 0


def check(name, ok, info=''):
    global failures
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {info}")
    if not ok:
        failures += 1


def noise(sr, seconds, level_db, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((int(sr * seconds), 2)) * 10 ** (level_db / 20)
    # partly correlated, like music: a centre part and a side part
    c = rng.standard_normal(x.shape[0]) * 10 ** (level_db / 20)
    return (0.6 * x + 0.8 * c[:, None]).astype(np.float32)


# Neutral chain (EQ flat, no output gain), so the comparison with the prototype is linear and below the limiter.
NEUTRAL = dict(low_db=0, hi_db=0, hs_db=0, hp_hz=20, out_db=0, ceil_db=0)


def main():
    lib = te.load_lib(os.path.join(HERE, 'build/libpvbcapi.so'))
    check('parameter count 56 (47 + 9 crosstalk-cancellation values)', lib.pvb_param_count() == 56)
    d = np.zeros(lib.pvb_param_count(), np.float32)
    lib.pvb_default_params(d.ctypes.data_as(te.FP))
    check('defaults: off, gentle, 40 cm, hat 57, 15.5 cm, 400-8000 Hz, balance 0 / 0',
          list(d[47:56]) == [0, -6, 40, 57, 15.5, 400, 8000, 0, 0], str(list(d[47:56])))

    sr = 48000
    x = noise(sr, 3, -30)
    a = te.Engine(lib, sr).process(x)
    b = te.Engine(lib, sr, xtc_mode=0, xtc_strength_db=-3, xtc_dist_cm=30, xtc_hat_cm=60, xtc_lo_hz=300,
                  xtc_hi_hz=6000).process(x)
    check('off: bit-identical whatever the other XTC values are', np.array_equal(a, b))

    for sr in (48000, 44100):
        x = noise(sr, 2, -30, seed=2)
        port.FS = float(sr)
        for mode in (1, 2):
            for gdb, dist, hat in ((-6, 40, 57), (-3, 30, 54), (-4.5, 50, 60)):
                e = te.Engine(lib, sr, **NEUTRAL, xtc_mode=mode, xtc_strength_db=gdb, xtc_dist_cm=dist, xtc_hat_cm=hat)
                y = e.process(x)
                radius = 0.0875 * hat / 57
                theta = np.arctan((15.5 * 0.005) / (dist * 0.01))
                tau = radius / 343 * (theta + np.sin(theta))
                pl, pr = port.run(mode == 2, 10 ** (gdb / 20), x[:, 0].astype(np.float64), x[:, 1].astype(np.float64),
                                  theta, tau, radius, 400, 8000)
                ref = te.Engine(lib, sr, **NEUTRAL).process(np.stack([pl, pr], 1).astype(np.float32))
                k = int(0.1 * sr)
                err = np.max(np.abs(y[k:] - ref[k:])) / np.max(np.abs(ref[k:]))
                check(f'{sr} Hz mode {mode} g {gdb} {dist} cm hat {hat}: engine = prototype (after the fade-in)',
                      err < 1e-4, f'max_rel_err={err:.2e}')

    sr = 48000
    x = noise(sr, 4, -20, seed=3)
    e = te.Engine(lib, sr, xtc_mode=0)
    out = []
    for i, blk in enumerate(np.array_split(x, 40)):
        if i == 10:
            e.set(xtc_mode=2, xtc_strength_db=-3)
        if i == 20:
            e.set(xtc_mode=1)
        if i == 30:
            e.set(xtc_mode=0)
        out.append(e.process(blk))
    y = np.concatenate(out)
    from scipy.signal import butter, sosfilt
    hp = butter(4, 12000, 'hp', fs=sr, output='sos')
    hf_in = np.max(np.abs(sosfilt(hp, x, axis=0)))
    hf_out = np.max(np.abs(sosfilt(hp, y, axis=0)))
    check('switching on, mode change, off while playing: finite, no click (HF > 12 kHz not above the input + 1 dB)',
          np.all(np.isfinite(y)) and hf_out <= hf_in * 10 ** (1 / 20), f'hf_out={hf_out:.4g} hf_in={hf_in:.4g}')

    # Speaker balance: after the canceller, left -b/2 and right +b/2 in its band; the other band untouched.
    from scipy.signal import butter, sosfilt
    def band_db(y, lo, hi):
        sos = butter(4, [lo, hi], 'bp', fs=sr, output='sos')
        return 10 * np.log10(np.mean(sosfilt(sos, y, axis=0)[sr // 2:] ** 2, axis=0))
    x = noise(sr, 3, -30, seed=6)
    y0 = te.Engine(lib, sr, **NEUTRAL, xtc_mode=2).process(x)
    for key, lo_b, hi_b, other in (('xtc_bal_lo_db', 700, 860, (3100, 3800)), ('xtc_bal_hi_db', 3100, 3800, (700, 860))):
        y1 = te.Engine(lib, sr, **NEUTRAL, xtc_mode=2, **{key: 4}).process(x)
        dc = band_db(y1, lo_b, hi_b) - band_db(y0, lo_b, hi_b)
        do = band_db(y1, *other) - band_db(y0, *other)
        check(f'balance {key} +4 dB: left -2, right +2 in its band; the other band within 0.6 dB',
              abs(dc[0] + 2) < 0.4 and abs(dc[1] - 2) < 0.4 and np.all(np.abs(do) < 0.6),
              f'band L/R={dc[0]:+.2f}/{dc[1]:+.2f} other={do[0]:+.2f}/{do[1]:+.2f}')
    ya = te.Engine(lib, sr, **NEUTRAL, xtc_mode=0, xtc_bal_lo_db=5, xtc_bal_hi_db=-5).process(x)
    yb = te.Engine(lib, sr, **NEUTRAL).process(x)
    check('balance does nothing while spatial is off (bit-identical)', np.array_equal(ya, yb))
    # moving the balance while playing (calibrating by ear): no fade, no gap
    e = te.Engine(lib, sr, **NEUTRAL, xtc_mode=2)
    out = []
    for i, blk in enumerate(np.array_split(x, 30)):
        if i >= 10:
            e.set(xtc_bal_lo_db=(i - 10) * 0.5)
        out.append(e.process(blk))
    y = np.concatenate(out)
    w = int(0.01 * sr)
    rms = np.sqrt(np.mean(y[: (len(y) // w) * w, 0].reshape(-1, w) ** 2, axis=1))
    k = len(rms) // 3
    check('moving the balance while playing: no dip (10 ms RMS stays above half the median)',
          np.min(rms[k:]) > 0.5 * np.median(rms[k:]), f'min/median={np.min(rms[k:]) / np.median(rms[k:]):.2f}')

    # Held upright: mono (3) and the two-way split (4: low to the left channel, 5: low to the right).
    xs = noise(sr, 3, -30, seed=7)
    k0 = int(0.1 * sr)
    ref = te.Engine(lib, sr, **NEUTRAL).process(xs)
    ym = te.Engine(lib, sr, **NEUTRAL, xtc_mode=3).process(xs)
    mono_ref = te.Engine(lib, sr, **NEUTRAL).process(np.repeat(xs.mean(axis=1, keepdims=True), 2, axis=1).astype(np.float32))
    merr = np.max(np.abs(ym[k0:] - mono_ref[k0:])) / np.max(np.abs(mono_ref))
    check('upright mono: both channels play the mono sum', merr < 1e-4, f'max_rel_err={merr:.1e}')
    for mode, low_ch in ((4, 0), (5, 1)):
        y = te.Engine(lib, sr, **NEUTRAL, xtc_mode=mode).process(xs)
        hi_ch = 1 - low_ch
        lo_l = band_db(y, 150, 400); hi_h = band_db(y, 3000, 6000)
        # LR4: the two parts add up to an all-pass of the mono sum, so compare levels per third-octave
        summed = ((y[:, 0] + y[:, 1]) / np.sqrt(2))[:, None]
        flat = max(abs(band_db(summed, f / 1.12, f * 1.12)[0] - band_db(mono_ref[:, :1], f / 1.12, f * 1.12)[0])
                   for f in (200, 500, 800, 1000, 1250, 2000, 5000))
        check(f'upright split {mode}: lows on channel {low_ch} (>= 20 dB over the other), highs on the other, parts add up flat (mono +3 dB)',
              lo_l[low_ch] - lo_l[hi_ch] > 20 and hi_h[hi_ch] - hi_h[low_ch] > 20 and flat < 0.5,
              f'low {lo_l[low_ch] - lo_l[hi_ch]:.1f} dB, high {hi_h[hi_ch] - hi_h[low_ch]:.1f} dB, sum within {flat:.2f} dB')

    # Upright with virtual bass (code review 2026-10-23, F3): the layer is added after this stage, so it must be routed
    # like the music: split -> only the low channel (nothing to the earpiece), mono -> the same on both.
    t = np.arange(sr * 6) / sr
    bass = np.repeat((0.2 * np.sin(2 * np.pi * 80 * t))[:, None], 2, axis=1).astype(np.float32)
    k2 = 2 * sr
    # Both model families: P1 (generates from the input, routed by the XTC stage) and Bankstown (generates from the
    # EQ output, so it already follows the split and must not be routed twice). The layer's power is kept: the low
    # channel gets the per-channel landscape level +3 dB.
    for algo, name in ((6, 'P1'), (1, 'Bankstown')):
        flat = band_db(te.Engine(lib, sr, xtc_mode=0, vb_on=1, vb_algo=algo, vb_level_db=4).process(bass)[k2:], 150, 800)
        for mode, low_ch in ((4, 0), (5, 1)):
            y = te.Engine(lib, sr, xtc_mode=mode, vb_on=1, vb_algo=algo, vb_level_db=4).process(bass)[k2:]
            lay = band_db(y, 150, 800)
            check(f'upright split {mode} + virtual bass ({name}): layer only on the low channel (earpiece >= 40 dB lower), '
                  f'power kept (low = landscape + 3 dB)',
                  lay[low_ch] - lay[1 - low_ch] >= 40 and abs(lay[low_ch] - flat[low_ch] - 3.01) < 0.2 and np.all(np.isfinite(y)),
                  f'low {lay[low_ch]:.1f} dBFS (landscape {flat[low_ch]:.1f}), earpiece {lay[1 - low_ch]:.1f} dBFS')
    left_bass = bass.copy(); left_bass[:, 1] = 0
    y = te.Engine(lib, sr, xtc_mode=3, vb_on=1, vb_algo=6, vb_level_db=4).process(left_bass)[k2:]
    lay = band_db(y, 150, 800)
    check('upright mono + virtual bass: the layer is mono too (bass on one input channel, same on both speakers)',
          abs(lay[0] - lay[1]) < 0.1 and lay[0] > -60, f'L {lay[0]:.2f} R {lay[1]:.2f} dBFS')

    # Matched M/S widener (6 = for centre, 7 = for full; blind comparison only): mid and side have the same
    # magnitude per third octave as the canceller with the same settings, without its delay structure.
    def ms_bands(y, rate):
        res = []
        sk = rate // 2
        for comp in (0.5 * (y[sk:, 0] + y[sk:, 1]), 0.5 * (y[sk:, 0] - y[sk:, 1])):
            row = []
            for fc in 400 * 2 ** (np.arange(0, 13) / 3):
                sos = butter(4, [fc * 2 ** (-1 / 6), min(fc * 2 ** (1 / 6), 0.45 * rate)], 'bp', fs=rate, output='sos')
                row.append(10 * np.log10(np.mean(sosfilt(sos, comp) ** 2)))
            res.append(np.array(row))
        return res
    for rate in (44100, 48000):
        xm = noise(rate, 6, -30, seed=11)
        for base, ms in ((1, 6), (2, 7)):
            for gdb, dist, hat in ((-6, 40, 57), (-3, 30, 54), (-4.5, 60, 60)):
                kw = dict(xtc_strength_db=gdb, xtc_dist_cm=dist, xtc_hat_cm=hat)
                yr = te.Engine(lib, rate, **NEUTRAL, xtc_mode=base, **kw).process(xm)
                ym = te.Engine(lib, rate, **NEUTRAL, xtc_mode=ms, **kw).process(xm)
                (mr, sr_), (mm, sm) = ms_bands(yr, rate), ms_bands(ym, rate)
                em, es = np.max(np.abs(mm - mr)), np.max(np.abs(sm - sr_))
                tot = 10 * np.log10(np.mean(ym[rate:] ** 2) / np.mean(yr[rate:] ** 2))
                check(f'{rate} Hz M/S widener {ms} vs canceller {base}, g {gdb} {dist} cm hat {hat}: mid and side within '
                      f'0.4 dB per third octave 400 Hz-8 kHz, total level within 0.2 dB',
                      em < 0.4 and es < 0.4 and abs(tot) < 0.2 and np.all(np.isfinite(ym)),
                      f'mid {em:.2f} side {es:.2f} total {tot:+.2f} dB, side boost up to {np.max(sr_ - ms_bands(xm, rate)[1]):.1f} dB')
    # it is a different signal from the canceller (no crosstalk delay), not the canceller relabelled
    yr = te.Engine(lib, sr, **NEUTRAL, xtc_mode=2, xtc_strength_db=-3).process(x[:sr * 2])
    ym = te.Engine(lib, sr, **NEUTRAL, xtc_mode=7, xtc_strength_db=-3).process(x[:sr * 2])
    check('M/S widener output differs from the canceller sample by sample', np.max(np.abs(yr - ym)) > 1e-3)
    e = te.Engine(lib, sr, xtc_mode=0)
    out = []
    xw = noise(sr, 4, -20, seed=12)
    for i, blk in enumerate(np.array_split(xw, 40)):
        if i == 10:
            e.set(xtc_mode=6, xtc_strength_db=-3)
        if i == 20:
            e.set(xtc_mode=2)
        if i == 25:
            e.set(xtc_mode=7)
        if i == 30:
            e.set(xtc_mode=0)
        out.append(e.process(blk))
    y = np.concatenate(out)
    hf_in = np.max(np.abs(sosfilt(hp, xw, axis=0)))
    hf_out = np.max(np.abs(sosfilt(hp, y, axis=0)))
    check('switching to and from the M/S widener while playing: finite, no click (HF > 12 kHz not above the input + 1 dB)',
          np.all(np.isfinite(y)) and hf_out <= hf_in * 10 ** (1 / 20), f'hf_out={hf_out:.4g} hf_in={hf_in:.4g}')
    z = te.Engine(lib, sr, xtc_mode=7, xtc_strength_db=-3).process(np.zeros((sr, 2), np.float32))
    check('M/S widener: silence in, silence out', np.max(np.abs(z)) == 0.0)
    ya = te.Engine(lib, sr, **NEUTRAL, xtc_mode=12).process(x[:sr])
    yb = te.Engine(lib, sr, **NEUTRAL, xtc_mode=9).process(x[:sr])
    check('mode above 9 is clamped to 9', np.array_equal(ya, yb))
    # Aligned canceller (8 = centre, 9 = full; comparison only): the canceller after the widener's 256-sample delay,
    # so both comparison sides have the same latency.
    D = 256
    xa = noise(sr, 2, -30, seed=13)
    for base, al, ms in ((1, 8, 6), (2, 9, 7)):
        yc = te.Engine(lib, sr, **NEUTRAL, xtc_mode=base, xtc_strength_db=-3).process(xa)
        yal = te.Engine(lib, sr, **NEUTRAL, xtc_mode=al, xtc_strength_db=-3).process(xa)
        ym = te.Engine(lib, sr, **NEUTRAL, xtc_mode=ms, xtc_strength_db=-3).process(xa)
        k = int(0.1 * sr)
        err = np.max(np.abs(yal[k + D:] - yc[k:-D])) / np.max(np.abs(yc))
        # latency: the widener and the aligned canceller line up at lag 0 (mid channel cross-correlation peak)
        def lag(a, b):
            ma, mb = a[k:, 0] + a[k:, 1], b[k:, 0] + b[k:, 1]
            c = np.correlate(ma[:sr], mb[:sr], 'full')[sr - 1 - 400: sr + 400]
            return int(np.argmax(c)) - 400
        check(f'aligned canceller {al} = canceller {base} delayed by {D} samples; same latency as widener {ms}',
              err < 1e-4 and lag(yal, ym) == 0 and lag(yc, ym) == -D,
              f'max_rel_err={err:.1e} lag(aligned, widener)={lag(yal, ym)} lag(canceller, widener)={lag(yc, ym)}')

    # Low sample rates (the app runs at 44.1/48 kHz; the engine accepts 8-192): the feedback low-pass stays below
    # Nyquist, so the canceller stays stable and finite.
    for rate in (8000, 11025, 12000, 14000, 16000, 22050):
        tt = np.arange(rate * 2) / rate
        xl = np.column_stack((.01 * np.sin(2 * np.pi * 700 * tt), .006 * np.sin(2 * np.pi * 1100 * tt))).astype(np.float32)
        ok = True
        for mode in (1, 2, 6, 7, 8, 9):
            e = te.Engine(lib, rate, xtc_mode=mode)
            yy = e.process(xl, block=128)
            ok = ok and bool(np.all(np.isfinite(yy))) and float(np.max(np.abs(yy))) < 1.0 and e.meters()[te.M['NAN_EVENTS']] == 0
        check(f'{rate} Hz, centre, full and both M/S widener modes: finite, no recovery events', ok)

    z = te.Engine(lib, sr, xtc_mode=2, xtc_strength_db=-3).process(np.zeros((sr, 2), np.float32))
    check('silence in, silence out (no self-oscillation)', np.max(np.abs(z)) == 0.0)
    loud = noise(sr, 5, -3, seed=4)
    y = te.Engine(lib, sr, xtc_mode=2, xtc_strength_db=-3, xtc_dist_cm=25).process(loud)
    check('strong, 25 cm, loud noise: finite and limited', np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 1.0,
          f'peak={np.max(np.abs(y)):.3f}')

    x = noise(sr, 60, -20, seed=5)
    t0 = time.perf_counter()
    te.Engine(lib, sr).process(x)
    t_off = time.perf_counter() - t0
    t0 = time.perf_counter()
    te.Engine(lib, sr, xtc_mode=2).process(x)
    t_on = time.perf_counter() - t0
    check('cost on the host (60 s at 48 kHz)', True, f'off_s={t_off:.3f} full_xtc_s={t_on:.3f} '
          f'added_pct_of_realtime={(t_on - t_off) / 60 * 100:.3f}')
    t0 = time.perf_counter()
    te.Engine(lib, sr, xtc_mode=7).process(x)
    t_ms = time.perf_counter() - t0
    check('cost of the M/S widener (full, two 513-tap FIRs) on the host', True,
          f'added_pct_of_realtime={(t_ms - t_off) / 60 * 100:.3f}')

    print('test_xtc: all passed' if not failures else f'test_xtc: {failures} FAILED')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
