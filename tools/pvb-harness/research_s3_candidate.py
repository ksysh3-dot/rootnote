#!/usr/bin/env python3
"""Study 3 (#4 follow-up): candidate C3 (host stage flag 32768) for short low notes, on P1 and on P1 + C1.

Mechanism (development: research_s3_shortnote_ladder.py and its notes in docs/STUDY3_PREREG.md): a short note below
about 65 Hz is analysed from the band-filtered harmonic signal; the band filter's 32 Hz high-pass tilts the short
note's spectrum and the track frequency comes out several Hz high for most of the note (47 -> 42 Hz for a 41 Hz note).
The harmonic grid accepts harmonic k only when k f lies within an ERB tolerance (about 4.5 Hz) of h times a peak of
the unfiltered input, i.e. within about 1 Hz at the fundamental for k = 4-5, so the main harmonic is held back until
the estimate settles near the end of the note. C3 lets a fundamental within 10 % support its harmonics below 65 Hz.

Models (each with and without C3): P1 (stage 0 -> 32768) and P1 + C1 (stage 8192 -> 8192 | 32768).
  short       primary: short notes 35-64 Hz (generated per cohort seed), relative main-harmonic envelope error at the
              declared latency (the P1+ metric, one constant scale, no fitted delay), per waveform in dB of error
              power; G/L rule of study 1. Also the error with the best lag (-100..+400 ms) and the RMS pitch
              deviation of the main harmonic (cents), both secondary
  high        short notes 65-125 Hz of the same generator: the change must stay within 0.5 dB
  notes       R01 ordinary-note controls: generated-layer energy change, block-size exactness (4096 vs 1379)
  kicks       study 2 interaction E (mixture - bed-only - impact-only) on the development, preservation and regression
              kick/broadband cohorts; the preservation measure is E relative to the mixture's own layer energy in
              the same window (C3 adds layer where an impact's low tail was held back); absolute E and the layer and
              impact-only changes are reported; windows with both energies below -150 dB are left out
  attack      study 1 attack budget on the mixture (median >= -1 dB, worst >= -3 dB)
  limiter     LIM_GR_DB of every render
Cohorts: development (seed 2026102903) and confirmation (seed 2026102904, opened once from a frozen tag). Output -18 dB.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve, firwin, resample_poly
import check_p1hq_primary_envelopes as E
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
import test_engine as T
from p1plus_paths import default_library
from research_p1pp_track_controls import signals

FS, CORE = 48000, 3000
OUT_DB = -18
C3 = 32768
CAND = C3                               # development: --candidate-flags may name another study 3 flag set
MODELS = (('p1', 0), ('p1_c1', 8192))   # (name, base host stage flags); the candidate adds C3
DEV_SEED, CONFIRM_SEED = 2026102903, 2026102904
WIN = slice(900, 12000)                 # 0.3-4.0 s at the 3 kHz core rate, as in the P1+ metric
LAGS = range(-int(.1 * CORE), int(.4 * CORE) + 1, 3)
NEAR_G, LOWER_PITCH_CENTS, HIGH_DB, NOTE_ANY_DB, NOTE_SINGLE_DB = 3., 10., .5, .5, .05
SINGLE_NOTES = ('steady_65hz', 'continuous_gliss_50_to_90hz')
FLOOR_DB = -150


def short_notes(seed, count, lo, hi):
    """Four short notes per waveform at fixed onsets (as the P1+ fixtures): frequency log-uniform in [lo, hi), length
    60-250 ms, a sin^2 or a plucked (5 ms attack, exponential decay, 10 ms taper) envelope, optional AM up to 8 Hz,
    peak 0.09 or 0.09 / 4."""
    rng = np.random.default_rng(seed); t = np.arange(round(4.5 * FS)) / FS
    for j in range(count):
        f = float(np.exp(rng.uniform(np.log(lo), np.log(hi)))); duration = float(rng.uniform(.06, .25))
        pluck = bool(rng.integers(2)); tau = float(rng.uniform(.05, .2)); rate = float(rng.uniform(0, 8)) * bool(rng.integers(2))
        peak = .09 / (4 if rng.integers(3) == 0 else 1); phase = float(rng.uniform(-np.pi, np.pi))
        env = np.zeros(len(t))
        for start in (.55, 1.3, 2.25, 3.4):
            u = t - start; on = (u >= 0) & (u < duration)
            if pluck:
                e = np.minimum(1, np.maximum(u, 0) / .005) * np.exp(-np.maximum(u - .005, 0) / tau)
                e *= np.clip((duration - u) / .01, 0, 1)
            else:
                e = np.sin(np.pi * np.clip(u / duration, 0, 1)) ** 2
            env += np.where(on, e, 0)
        env *= peak * (1 + .35 * np.sin(2 * np.pi * rate * t))
        yield f'note_{seed}_{j}', f, env, env * np.cos(2 * np.pi * f * t + phase), \
            dict(frequency=f, note_seconds=duration, pluck=pluck, decay_s=tau, am_hz=rate, peak=peak)


def demod(y, centre, cutoff):
    z = resample_poly(np.asarray(y, float), CORE, FS); t = np.arange(len(z)) / CORE
    return fftconvolve(2 * z * np.exp(-2j * np.pi * centre * t), firwin(901, cutoff, fs=CORE, window=('kaiser', 8)), mode='same')


def err_db(m, r):
    scale = float(m @ r / (r @ r))
    if scale < 1e-7: return None
    return float(10 * np.log10(max(np.mean((m - scale * r) ** 2), 1e-30) / max(np.mean((scale * r) ** 2), 1e-30)))


def short_metrics(y, env, f, k):
    """Error at the declared latency, error and lag at the best lag, and the RMS pitch deviation (cents) of the main
    harmonic over the samples where the (lagged) note envelope is above 10 % of its peak."""
    cut = .35 * f; t = np.arange(len(env)) / FS
    ref = E.envelope(env * np.cos(2 * np.pi * k * f * t), FS, k * f, cut)
    b = demod(y, k * f, cut); m = np.abs(b)
    at = err_db(m[WIN], ref[WIN])
    best = min(((e, lag) for lag in LAGS if (e := err_db(np.roll(m, -lag)[WIN], ref[WIN])) is not None), default=(None, 0))
    df = np.angle(b[1:] * np.conj(b[:-1])) * CORE / (2 * np.pi)
    mask = np.roll(ref, best[1])[1:] > .1 * ref.max(); w = np.abs(b[1:]) ** 2 * mask
    cents = 1200 * np.log2(np.maximum(k * f + df, 1e-6) / (k * f))
    pitch = float(np.sqrt(np.sum(w * cents ** 2) / w.sum())) if w.sum() > 0 else None
    return dict(error_db=at, best_error_db=best[0], best_lag_ms=best[1] / CORE * 1000, pitch_cents=pitch)


def render(lib, x, stage, block=4096, flags=0, mode=0):
    return P.render(lib, x, FS, flags, block=block, impact_mode=mode, stage_flags=stage, out_db=OUT_DB)


def short_cohort(lib, fixtures):
    rows = []
    for name, f, env, x, desc in fixtures:
        k = E.primary(f); xi = np.r_[x, np.zeros(FS)]
        for model, base in MODELS:
            out = {}
            for tag, stage in (('base', base), ('C3', base | CAND)):
                r = render(lib, xi, stage)
                y = r['stem'][r['latency']:r['latency'] + len(x), 0]
                out[tag] = dict(short_metrics(y, env, f, k), limiter_gr_db=float(r['meters'][T.M['LIM_GR_DB']]))
            d = {key: (out['C3'][key] - out['base'][key]) if None not in (out['C3'][key], out['base'][key]) else None
                 for key in ('error_db', 'best_error_db', 'pitch_cents')}
            rows.append(dict(name=name, model=model, harmonic=k, input=desc, base=out['base'], C3=out['C3'], change=d))
            print('SHORT', name, f'{f:.1f}Hz k{k}', model, f"err {out['base']['error_db']:+.1f} -> {out['C3']['error_db']:+.1f} dB",
                  f"pitch {out['base']['pitch_cents']:.0f} -> {out['C3']['pitch_cents']:.0f} c", flush=True)
    return rows


def gl(values):
    """Study 1 G/L rule on per-waveform changes (dB, negative = better)."""
    v = [x for x in values if x is not None]
    if not v: return dict(G_db=None, L_db=None, reducing='0/0', verdict='not_established')
    G = float(np.median([-x for x in v])); L = float(max(0., max(v))); red = sum(x < 0 for x in v)
    ok = G >= NEAR_G and red * 3 >= 2 * len(v)
    verdict = 'near_adoption' if ok and L <= G / 2 else 'hold_option' if ok else 'not_established'
    return dict(G_db=G, L_db=L, reducing=f'{red}/{len(v)}', verdict=verdict)


def notes(lib):
    pad = np.zeros(FS // 2); out = []
    for name, sig in signals(FS, 3 * FS).items():
        x = np.r_[sig, pad]; n = len(sig); m = slice(FS // 2, n)
        for model, base in MODELS:
            r0, r1 = render(lib, x, base), render(lib, x, base | CAND)
            y0, y1 = S.aligned(r0, n, 'stem'), S.aligned(r1, n, 'stem')
            b0, b1 = render(lib, x, base, 1379), render(lib, x, base | CAND, 1379)
            out.append(dict(signal=name, model=model, layer_change_db=S.db(S.energy(y1[m]), S.energy(y0[m])),
                            max_abs_difference=float(np.max(np.abs(y1 - y0))), bit_identical=bool(np.array_equal(y0, y1)),
                            baseline_block_exact=bool(np.array_equal(r0['output'], b0['output'])),
                            candidate_block_exact=bool(np.array_equal(r1['output'], b1['output']))))
            print('NOTE', name, model, f"{out[-1]['layer_change_db']:+.4f} dB identical {out[-1]['bit_identical']}", flush=True)
    return out


def kicks(lib):
    """Study 2 interaction cohorts (development, preservation, regression), each model with and without C3."""
    cohorts = (('development', [f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)), S.LEVELS),
               ('preserve', list(CF.preserve_fixtures()), (-12, -6)),
               ('regression', list(CF.confirm_fixtures(seed=CF.CONFIRM_SEED)), (-12, -6)))
    names = ('attack',) + tuple(CF.WINDOWS); pad = np.zeros(FS // 2); rows = []
    for cohort, fixtures, levels in cohorts:
        for shape, _bed, t, b, z, onset, duration in fixtures:
            kind = next((k for k in ('kick', 'noise') if k in shape), None); n = len(t)
            for model, base in MODELS:
                rb = {s: render(lib, np.r_[b, pad], s) for s in (base, base | CAND)}
                for level in levels:
                    impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]; xi = np.r_[impact, pad]
                    e = {}
                    for tag, s in (('base', base), ('C3', base | CAND)):
                        rx, ri = render(lib, x, s), render(lib, xi, s)
                        y, yb, yi = S.aligned(rx, n, 'stem'), S.aligned(rb[s], n, 'stem'), S.aligned(ri, n, 'stem')
                        e[tag] = dict(E=CF.window_energy(y - yb - yi, t, onset, duration, names),
                                      layer=CF.window_energy(y, t, onset, duration, names),
                                      impact=CF.window_energy(yi, t, onset, duration, names),
                                      limiter_gr_db=[float(r_['meters'][T.M['LIM_GR_DB']]) for r_ in (rx, rb[s], ri)])
                    db = lambda v: 10 * np.log10(v) if v > 0 else -300.
                    row = dict(cohort=cohort, shape=shape, type=kind, model=model, impact_peak_dbfs=level,
                               base=e['base'], C3=e['C3'],
                               attack_change_db=S.db(e['C3']['layer']['attack'], e['base']['layer']['attack']))
                    for w in CF.WINDOWS:
                        eb, ec = e['base']['E'][w], e['C3']['E'][w]
                        floor = max(db(eb), db(ec)) < FLOOR_DB
                        row[f'{w}_relative_change_db'] = None if floor else \
                            (db(ec) - db(e['C3']['layer'][w])) - (db(eb) - db(e['base']['layer'][w]))
                        row[f'{w}_absolute_change_db'] = None if floor else db(ec) - db(eb)
                        row[f'{w}_layer_change_db'] = db(e['C3']['layer'][w]) - db(e['base']['layer'][w])
                        row[f'{w}_impact_only_change_db'] = db(e['C3']['impact'][w]) - db(e['base']['impact'][w])
                    rows.append(row)
                    print('KICK', cohort, shape, model, level, ' '.join(
                        f"{w}: rel {row[w + '_relative_change_db'] or 0:+.1f} abs {row[w + '_absolute_change_db'] or 0:+.1f}"
                        for w in CF.WINDOWS), f"atk {row['attack_change_db']:+.2f}", flush=True)
    return rows


def kick_summary(rows):
    out = []
    for model, _ in MODELS:
        for kind in ('kick', 'noise'):
            sub = [r for r in rows if (r['model'], r['type']) == (model, kind)]
            if not sub: continue
            shapes = sorted({(r['cohort'], r['shape']) for r in sub})
            for w in CF.WINDOWS:
                for measure in ('relative', 'absolute'):
                    per = [float(np.median(v)) for s in shapes
                           if (v := [r[f'{w}_{measure}_change_db'] for r in sub if (r['cohort'], r['shape']) == s
                                     and r[f'{w}_{measure}_change_db'] is not None])]
                    out.append(dict(model=model, type=kind, window=w, measure=measure, waveforms=len(per),
                                    worst_db=float(max(per)) if per else None, median_db=float(np.median(per)) if per else None))
            att = [float(np.median([r['attack_change_db'] for r in sub if (r['cohort'], r['shape']) == s])) for s in shapes]
            out.append(dict(model=model, type=kind, window='attack', measure='layer', waveforms=len(att),
                            median_db=float(np.median(att)), worst_db=float(min(att)),
                            within=bool(np.median(att) >= -1 and min(att) >= -3)))
    return out


def decide(short_rows, high_rows, note_rows, ksum):
    out = []
    for model, _ in MODELS:
        mine = [r for r in short_rows if r['model'] == model]
        prim = gl([r['change']['error_db'] for r in mine])
        pitch = [r['change']['pitch_cents'] for r in mine if r['change']['pitch_cents'] is not None]
        lagfree = gl([r['change']['best_error_db'] for r in mine])
        high = [abs(r['change']['error_db']) for r in high_rows if r['model'] == model and r['change']['error_db'] is not None]
        nts = [n for n in note_rows if n['model'] == model]
        kick_rel = [k for k in ksum if k['model'] == model and k['measure'] == 'relative' and k['worst_db'] is not None]
        attack = [k for k in ksum if k['model'] == model and k['window'] == 'attack']
        G = prim['G_db'] or 0.; reasons = []
        if pitch and float(np.median(pitch)) > LOWER_PITCH_CENTS: reasons.append(f'pitch +{np.median(pitch):.1f} cents')
        if high and max(high) > HIGH_DB: reasons.append(f'65-125 Hz note {max(high):.2f} dB')
        if any(abs(n['layer_change_db']) > NOTE_ANY_DB for n in nts): reasons.append('ordinary note > 0.5 dB')
        if any(abs(n['layer_change_db']) > NOTE_SINGLE_DB for n in nts if n['signal'] in SINGLE_NOTES):
            reasons.append('single-track note > 0.05 dB')
        if any(n['baseline_block_exact'] and not n['candidate_block_exact'] for n in nts): reasons.append('block exactness lost')
        worst_kick = max([k['worst_db'] for k in kick_rel], default=0.)
        if G > 0 and worst_kick > G / 2: reasons.append(f'impact interaction (relative) {worst_kick:.2f} dB > G/2')
        if any(not k['within'] for k in attack): reasons.append('attack budget exceeded')
        final = 'hold_option' if prim['verdict'] == 'near_adoption' and reasons else prim['verdict']
        out.append(dict(model=model, primary=prim, lag_free=lagfree,
                        pitch_change_median_cents=float(np.median(pitch)) if pitch else None,
                        pitch_change_worst_cents=float(max(pitch)) if pitch else None,
                        high_worst_db=max(high, default=0.), impact_relative_worst_db=worst_kick,
                        lowered_by=reasons, decision=final))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--cohort', choices=('development', 'confirm'), default='development')
    p.add_argument('--frozen', default='')
    p.add_argument('--frozen-sha', default='')
    p.add_argument('--candidate-flags', type=int, default=C3)
    a = p.parse_args()
    global CAND
    CAND = a.candidate_flags
    ident = CF.checkout_identity(a.frozen)
    if a.cohort == 'confirm':
        problems = []
        if not re.fullmatch(r'[0-9a-f]{40}', a.frozen_sha): problems.append('--frozen-sha is not a full commit SHA')
        if not a.frozen or ident['frozen_tag_sha'] is None: problems.append(f'tag {a.frozen!r} not found')
        elif ident['frozen_tag_sha'] != a.frozen_sha: problems.append(f"tag names {ident['frozen_tag_sha']}")
        if ident['checkout_sha'] != a.frozen_sha: problems.append(f"checkout is {ident['checkout_sha']}")
        if ident['tracked_changes'] is not False: problems.append('tracked files differ from the commit')
        if problems: raise SystemExit('the study 3 confirmation cohort stays closed: ' + '; '.join(problems))
    lib = P.api(a.library.resolve())
    seed = CONFIRM_SEED if a.cohort == 'confirm' else DEV_SEED
    short_rows = short_cohort(lib, list(short_notes(seed, 12, 35, 65)))
    high_rows = short_cohort(lib, list(short_notes(seed + 100, 4, 65, 125)))
    note_rows = notes(lib)
    kick_rows = kicks(lib); ksum = kick_summary(kick_rows)
    for k in ksum: print('KICKSUM', json.dumps(k), flush=True)
    decisions = decide(short_rows, high_rows, note_rows, ksum)
    for d in decisions: print('DECISION', json.dumps(d), flush=True)
    gr = [v for r in short_rows + high_rows for v in (r['base']['limiter_gr_db'], r['C3']['limiter_gr_db'])] + \
         [v for r in kick_rows for t_ in ('base', 'C3') for v in r[t_]['limiter_gr_db']]
    print('LIMITER', 'min', min(gr), 'max', max(gr), flush=True)
    result = dict(schema='rootnote.study3.candidate.v1', issue=4, cohort=a.cohort, seed=seed, checkout=ident,
                  frozen=a.frozen or None, frozen_sha=a.frozen_sha or None, confirmation_opened=a.cohort == 'confirm',
                  candidate_flags=CAND, models=[dict(name=m, base_stage=b) for m, b in MODELS], out_db=OUT_DB,
                  source_sha256=S.source_hashes(), library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  decisions=decisions, kick_summary=ksum, short=short_rows, high=high_rows, notes=note_rows,
                  kicks=kick_rows, limiter_gr_db=dict(min=min(gr), max=max(gr)))
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
