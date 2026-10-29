#!/usr/bin/env python3
"""Study 3 development (#4 follow-up): where does the short low note lose its envelope? A stage ladder.

P1++ attribution (research/p1pp/2026-10-26): the short-note fixture fresh_note_3 (45.46 Hz) keeps a relative
main-harmonic envelope error RMS of about 83 % in P1+, without its noise too, and the same plain note gives 147, 36,
18, 15 and 9 % at 41, 55, 65, 81 and 106 Hz. Which stage it comes from was not tested. Here, notes only (no added
noise; the attribution showed it is not needed), per model and note, the envelope at each captured stage (3 kHz core
clock) against the note's own envelope:
  band            input low band at the core rate            (envelope at f)
  original_h      HPSS harmonic output                       (envelope at f)
  analytic_envelope  |analytic H|, the music envelope source (as is)
  nominal_amplitude  grain nominal amplitude, ps source      (as is)
  raw_grain       synthesis before the envelope gain         (envelope at k f)
  tonal_after_gain  after the envelope gain                  (envelope at k f)
  post_filter     after the output filter                    (envelope at k f)
and the final stem metric of the earlier study (declared latency, one constant scale). Each tap: shape error with
one constant scale at its captured clock, and the smallest error over a lag of -80..+80 ms with that lag (the taps
do not share one delay, so the lag-free value separates shape from delay; the earlier metric allows no lag).
Causal checks on the final metric: host stage flags 1 (HPSS bypassed), 2 (envelope gain bypassed), 4 (harmonic
permission bypassed) and their combinations 3, 5 and 7.
Development only; no fixture here is held out.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve, firwin, resample_poly
import check_p1hq_primary_envelopes as E
import research_p1plus as P
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS, CORE = 48000, 3000
MODELS = (('p1', 0), ('p1plus', 6))
TAPS = (('band', 'f'), ('original_h', 'f'), ('analytic_envelope', None), ('nominal_amplitude', None),
        ('raw_grain', 'k'), ('tonal_after_gain', 'k'), ('post_filter', 'k'))
WIN = slice(900, 12000)
# host stage flags: 1 HPSS bypassed, 4 harmonic permission bypassed, 16384 C2 (unfiltered peak frequency),
# 32768 C3 (wider harmonic grid below 65 Hz), 65536 C4 (C3 outside an impact context), 8192 C1
STAGES = (0, 4, 16384, 32768, 65536, 8192, 8192 | 65536)
LAGS = range(-int(.1 * CORE), int(.4 * CORE) + 1, 3)


def notes():
    """fresh_note_0..5 without their noise, and the fresh_note_3 plain envelope at the attribution frequencies."""
    t = np.arange(round(4.5 * FS)) / FS
    fx = list(E.fixtures(FS))
    for name, mixed, env, d in fx:
        yield name, d['frequency'], env, env * np.cos(2 * np.pi * d['frequency'] * t + .3)
    _, _, env3, d3 = fx[3]
    plain = env3 / (1 + .35 * np.sin(2 * np.pi * d3['rate'] * t))
    for f in (41., 45.4609, 55., 65., 81., 106.):
        yield f'plain_{f:g}hz', f, plain, plain * np.cos(2 * np.pi * f * t + .3)


def lowpass(x, cutoff):
    return fftconvolve(x, firwin(901, cutoff, fs=CORE, window=('kaiser', 8)), mode='same')


def demod(x, centre, cutoff):
    t = np.arange(len(x)) / CORE
    return abs(lowpass(2 * x * np.exp(-2j * np.pi * centre * t), cutoff))


def pitch_cents(y, centre, cutoff, ref):
    """Energy-weighted RMS deviation (cents) of the main harmonic's instantaneous frequency from k f, over the
    samples where the note's own envelope is above 10 % of its peak."""
    z = resample_poly(np.asarray(y, float), CORE, FS); t = np.arange(len(z)) / CORE
    b = fftconvolve(2 * z * np.exp(-2j * np.pi * centre * t), firwin(901, cutoff, fs=CORE, window=('kaiser', 8)), mode='same')
    df = np.angle(b[1:] * np.conj(b[:-1])) * CORE / (2 * np.pi)
    w = np.abs(b[1:]) ** 2 * (np.r_[ref, np.zeros(max(0, len(df) - len(ref)))][:len(df)] > .1 * ref.max())
    if w.sum() <= 0: return None
    cents = 1200 * np.log2(np.maximum(centre + df, 1e-6) / centre)
    return float(np.sqrt(np.sum(w * cents ** 2) / w.sum()))


def shape(measured, ref):
    m, r = measured[WIN], ref[WIN]
    if r @ r <= 0 or m @ m <= 0: return None
    scale = float(m @ r / (r @ r)); e = m - scale * r
    return float(10 * np.log10(max(np.mean(e ** 2), 1e-30) / max(np.mean((scale * r) ** 2), 1e-30)))


def best_lag(measured, ref):
    best = (None, 0)
    for lag in LAGS:
        s = shape(np.roll(measured, -lag), ref)
        if s is not None and (best[0] is None or s < best[0]): best = (s, lag)
    return best


def taps(r):
    s = r['stages']; idx = s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32); n = int(idx.max()) + 1
    out = {}
    for k, _ in TAPS:
        a = np.zeros(n); a[idx] = s[:, COLUMNS.index(k)]; out[k] = a
    return out


def pct(db):
    return None if db is None else 100 * 10 ** (db / 20)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []
    for name, f, env, x in notes():
        k = E.primary(f); cut = .35 * f; n = len(x)
        env_core = resample_poly(env, CORE, FS)
        ref_f = lowpass(env_core, cut)  # the note envelope through the same low-pass as every demodulated tap
        t = np.arange(n) / FS; ideal = env * np.cos(2 * np.pi * k * f * t)
        ref_final = E.envelope(ideal, FS, k * f, cut)[WIN]
        for model, flags in MODELS:
            row = dict(note=name, frequency=f, harmonic=k, model=model, flags=flags, ladder={}, final={}, final_best={},
                       pitch_cents={})
            for stage in STAGES:
                r = P.render(lib, np.r_[x, np.zeros(FS)], FS, flags, stage_flags=stage)
                y = r['stem'][r['latency']:r['latency'] + n, 0]
                fin = E.envelope(y, FS, k * f, cut)
                row['final'][str(stage)] = pct(E.score(fin[WIN], ref_final)['shape_error_db'])
                lagged, lag = best_lag(fin, np.r_[np.zeros(WIN.start), ref_final, np.zeros(len(fin) - WIN.stop)])
                row['final_best'][str(stage)] = dict(pct=pct(lagged), lag_ms=lag / CORE * 1000)
                row['pitch_cents'][str(stage)] = pitch_cents(y, k * f, cut, np.roll(ref_f, lag))
                if stage: continue
                tp = taps(r)
                for tap, centre in TAPS:
                    v = tp[tap][:len(ref_f)]
                    v = np.r_[v, np.zeros(len(ref_f) - len(v))]
                    m = lowpass(v, cut) if centre is None else demod(v, f if centre == 'f' else k * f, cut)
                    lagged, lag = best_lag(m, ref_f)
                    row['ladder'][tap] = dict(at_clock_pct=pct(shape(m, ref_f)), best_pct=pct(lagged),
                                              best_lag_ms=lag / CORE * 1000)
            rows.append(row)
            print('ROW', name, f'{f:.1f}Hz k{k}', model, 'final', {s: round(v, 1) for s, v in row['final'].items()},
                  'lagged', {s: f"{v['pct']:.0f}%@{v['lag_ms']:+.0f}" for s, v in row['final_best'].items()},
                  'cents', {s: None if v is None else round(v) for s, v in row['pitch_cents'].items()},
                  ' '.join(f"{t_}:{v['best_pct']:.0f}%@{v['best_lag_ms']:+.0f}" for t_, v in row['ladder'].items()
                           if v['best_pct'] is not None), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study3.shortnote_ladder.v1', issue=4, fixture_seed=2026102606,
                                        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                                        held_out=False, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
