#!/usr/bin/env python3
"""Resultant phase 0 (#4 follow-up): how much more useful harmonic level can the generated layer give at the same
energy or at the same peak? A ceiling measurement on synthetic notes; no engine change, nothing here is a listening
score and no fixture is held out.

Per model and fixture, on the steady window (1.0-4.0 s) of the generated layer (stem) and of the core taps:
  valid         energy share of the harmonics k f (k >= 2) of the input notes (AM sidebands of them included), from a
                least-squares line fit at the layer's own fundamental (so a small mistuning is pitch, not invalid)
  fundamental   k = 1;  ghost  half-integer multiples (k + 1/2) f;  intermod  m f1 + n f2 of a pair (|m|+|n| <= 6)
  other         the fit residual (inharmonic energy, amplitude jitter skirts);  near_valid  periodogram energy within
                3 Hz (+ the AM rate) of a valid line, an upper bound on valid
  equal-energy ceiling  -10 log10(valid): the valid level if the layer held only its valid harmonics, same energy
  crest factors         actual stem (true peak at 48 kHz; also the median 50 ms block peak); the valid lines with
                        their fitted phases; the valid lines with phases optimised for the lowest peak (one phase per
                        harmonic, so each harmonic keeps its own envelope; Newman start, clip-and-project, restarts)
  equal-peak ceiling    20 log10(CF_actual / CF_optimised) - 10 log10(valid), split into the invalid-removal part and
                        the phase part. A pair's optimised peak is the sum of the two notes' optimised peaks (the
                        long-run peak of two unrelated periods), so the pair ceiling is conservative.
Short notes (attack/release 5 ms, four per fixture): drive kept by the HPSS harmonic part (original_h against the
band at the same delay, demodulated at f), coverage (the layer's valid energy over the note against the steady
note's valid power times the note's energy duration) and the note's stem peak against the steady stem peak.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve, firwin, resample_poly
import research_p1plus as P
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS, CORE = 48000, 3000
DUR = 4.5
STEADY = (1.0, 4.0)
TOP = 1450.
MODELS = (('p1', 0, 0), ('p1_c1', 0, 8192), ('p1plus', 6, 0))
TAPS = ('raw_grain', 'tonal_after_gain', 'percussion', 'pre_filter', 'post_filter')
SHORT_STARTS = (.6, 1.6, 2.6, 3.6)
OPT_FS = 12000
ITERS, RESTARTS = 300, 6
UNRESOLVED_HZ = 8.  # a pair closer than this is below any 128 ms analysis (reported, kept out of the pair summary)


def cosine(f, t, phase=.3):
    return np.cos(2 * np.pi * f * t + phase)


def short_env(t, d):
    env = np.zeros(len(t)); r = .005
    for s in SHORT_STARTS:
        u = t - s
        env += np.where((u >= 0) & (u < d), np.minimum(1, np.minimum(u, d - u) / r), 0)
    return np.clip(env, 0, 1) ** 2


def fixtures():
    t = np.arange(round(DUR * FS)) / FS
    for f in (35., 41., 46., 55., 65., 73., 82., 98., 110., 130.):
        yield dict(name=f'steady_{f:g}', kind='steady', notes=[f], rate=0., x=.12 * cosine(f, t))
    for f, rate in ((55., 3.), (55., 7.), (41., 5.)):
        yield dict(name=f'am_{f:g}_{rate:g}', kind='am', notes=[f], rate=rate,
                   x=.12 * (1 + .7 * np.sin(2 * np.pi * rate * t)) * cosine(f, t))
    # pairs run 9.5 s with an 8 s window: tempered intervals put harmonics of the two notes 0.2 Hz apart
    t2 = np.arange(round(9.5 * FS)) / FS
    for f1, f2 in ((55., 82.5), (41.2, 55.), (65.4, 82.4), (49., 73.4), (55., 58.)):
        yield dict(name=f'pair_{f1:g}_{f2:g}', kind='pair', notes=[f1, f2], rate=0., window=(1.0, 9.0),
                   x=.085 * cosine(f1, t2) + .085 * cosine(f2, t2, 1.1))
    for f in (41., 55., 82., 110.):
        for d in (.15, .4):
            env = short_env(t, d)
            yield dict(name=f'short_{f:g}_{d * 1000:g}ms', kind='short', notes=[f], rate=0., duration=d,
                       env=env, x=.12 * env * cosine(f, t))


def lines(notes, rate, guard=.4):
    """(frequency, class, group) with group = (note index, k) for harmonic lines; earlier classes win a clash
    (lines closer than the guard, about 1.2 / window length, are one line)."""
    out = []

    def add(fr, cls, group=None):
        if 1 < fr < TOP and all(abs(fr - q) > guard for q, _, _ in out): out.append((fr, cls, group))
    side = (-2, -1, 1, 2) if rate else ()
    for i, f in enumerate(notes):
        for k in range(2, int(TOP / f) + 1):
            add(k * f, 'valid', (i, k))
            for d in side: add(k * f + d * rate, 'valid', (i, k))
    for i, f in enumerate(notes):
        add(f, 'fundamental')
        for d in side: add(f + d * rate, 'fundamental')
    if len(notes) == 2:
        f1, f2 = notes
        for m in range(-6, 7):
            for n in range(-6, 7):
                if m and n and abs(m) + abs(n) <= 6: add(abs(m * f1 + n * f2), 'intermod')
    for f in notes:
        for k in range(0, int(TOP / f) + 1): add((k + .5) * f, 'ghost')
    return out


def fit(z, fs, ls):
    t = np.arange(len(z)) / fs
    design = np.column_stack([v for f, _, _ in ls for v in (np.cos(2 * np.pi * f * t), np.sin(2 * np.pi * f * t))])
    coef = np.linalg.lstsq(design, z, rcond=1e-10)[0]
    residual = z - design @ coef
    amp = coef[0::2] - 1j * coef[1::2]  # z ~ Re(amp e^{i w t})
    return amp, float(np.mean(residual ** 2))


def shares(z, fs, ls, rate):
    amp, res = fit(z, fs, ls)
    energy = {c: 0. for c in ('valid', 'fundamental', 'intermod', 'ghost')}
    for (f, c, _), a in zip(ls, amp): energy[c] += abs(a) ** 2 / 2
    energy['other'] = res
    total = sum(energy.values())
    out = {c: (v / total if total > 0 else None) for c, v in energy.items()}
    # periodogram bound: energy within 3 Hz (+ AM rate) of a valid line
    w = np.hanning(len(z)); X = np.abs(np.fft.rfft(z * w)) ** 2; fr = np.fft.rfftfreq(len(z), 1 / fs)
    near = np.zeros(len(fr), bool)
    for f, c, _ in ls:
        if c == 'valid': near |= abs(fr - f) <= 3 + rate
    out['near_valid'] = float(X[near].sum() / X.sum()) if X.sum() > 0 else None
    out['rms'] = float(np.sqrt(np.mean(z ** 2)))
    return out, amp


def layer_fundamental(z, fs, f):
    """Power-weighted fundamental of the layer's harmonics 2..8 near k f (parabolic peak on a padded spectrum)."""
    n = 1 << int(np.ceil(np.log2(len(z) * 8)))
    X = np.abs(np.fft.rfft(z * np.hanning(len(z)), n)); df = fs / n
    num = den = 0.
    for k in range(2, 9):
        if k * f >= TOP: break
        lo, hi = int((k * f * .97) / df), int((k * f * 1.03) / df) + 1
        j = lo + int(np.argmax(X[lo:hi]))
        if 0 < j < len(X) - 1:
            a, b, c = np.log(X[j - 1:j + 2] + 1e-30); p = .5 * (a - c) / (a - 2 * b + c)
            num += X[j] ** 2 * (j + p) * df / k; den += X[j] ** 2
    est = num / den if den > 0 else f
    return est if abs(est / f - 1) < .03 else f


def crest(x):
    return float(np.max(np.abs(x)) / np.sqrt(np.mean(x ** 2)))


def groups_of(ls, amp, note):
    """Per harmonic of one note: its lines with the carrier's phase taken out, and the carrier phase."""
    g = {}
    for (f, c, grp), a in zip(ls, amp):
        if c == 'valid' and grp[0] == note: g.setdefault(grp[1], []).append((f, a))
    out = []
    for k in sorted(g):
        carrier = max(g[k], key=lambda q: abs(q[1]))
        ph = np.angle(carrier[1])
        out.append(([(f, a * np.exp(-1j * ph)) for f, a in g[k]], ph))
    return out


def synth(groups, theta, n, fs):
    t = np.arange(n) / fs
    S = np.array([sum(a * np.exp(2j * np.pi * f * t) for f, a in g) for g, _ in groups])
    return np.real(np.exp(1j * np.asarray(theta)) @ S), S


def optimise(groups, window, iters=300, restarts=6, seed=2026102905):
    """Lowest crest factor over one phase per harmonic, magnitudes fixed. Returns (CF fitted phases at 48 kHz,
    CF optimised at 48 kHz, CF Newman phases at 48 kHz, peak and rms of the optimised waveform at 48 kHz)."""
    n = int(round(window * OPT_FS)); n48 = int(round(window * FS))
    fitted = np.array([ph for _, ph in groups])
    _, S = synth(groups, fitted, n, OPT_FS)
    p = np.array([sum(abs(a) ** 2 for _, a in g) for g, _ in groups]); p = p / p.sum()
    newman = np.array([-2 * np.pi * sum((k - l) * p[l] for l in range(k)) for k in range(len(p))])
    rng = np.random.default_rng(seed)
    starts = [newman, fitted] + [rng.uniform(-np.pi, np.pi, len(p)) for _ in range(restarts - 2)]
    best = (np.inf, newman)
    for theta in starts:
        theta = theta.copy()
        for _ in range(iters):
            x = np.real(np.exp(1j * theta) @ S); rms = np.sqrt(np.mean(x * x)); c = np.max(np.abs(x)) / rms
            if c < best[0]: best = (c, theta.copy())
            level = rms * max(1.02, .93 * c)
            theta = np.angle(S.conj() @ np.clip(x, -level, level))
    xf, _ = synth(groups, fitted, n48, FS); xo, _ = synth(groups, best[1], n48, FS); xn, _ = synth(groups, newman, n48, FS)
    return crest(xf), crest(xo), crest(xn), float(np.max(np.abs(xo))), float(np.sqrt(np.mean(xo ** 2)))


def lowpass(x, cutoff):
    return fftconvolve(x, firwin(901, cutoff, fs=CORE, window=('kaiser', 8)), mode='same')


def demod_power(x, centre, cutoff):
    t = np.arange(len(x)) / CORE
    return abs(lowpass(2 * x * np.exp(-2j * np.pi * centre * t), cutoff)) ** 2 / 2


def harmonic_power(z, f):
    cut = .35 * f
    return sum(demod_power(z, k * f, cut) for k in range(2, int(TOP / f) + 1))


def taps(r):
    s = r['stages']; idx = s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32); n = int(idx.max()) + 1
    out = {}
    for k in TAPS + ('band_delayed191', 'original_h', 'original_p'):
        a = np.zeros(n); a[idx] = s[:, COLUMNS.index(k)]; out[k] = a
    return out


def db(v):
    return None if v is None or v <= 0 else float(10 * np.log10(v))


def steady_row(fx, r):
    stem = r['stem'][:, 0].astype(float)
    window = fx.get('window', STEADY)
    a, b = (int(q * FS) for q in window)
    w48 = stem[a:b]; z = resample_poly(w48, 1, 16)
    hi = np.fft.rfft(w48 * np.hanning(len(w48))); fr = np.fft.rfftfreq(len(w48), 1 / FS)
    above = float(np.sum(abs(hi[fr > TOP]) ** 2) / np.sum(abs(hi) ** 2))
    notes = [layer_fundamental(z, CORE, f) if fx['kind'] != 'pair' else f for f in fx['notes']]
    ls = lines(notes, fx['rate'], 1.2 / (window[1] - window[0]))
    stem_sh, amp = shares(z, CORE, ls, fx['rate'])
    row = dict(layer_fundamental_cents=[float(1200 * np.log2(q / f)) for q, f in zip(notes, fx['notes'])],
               stem=stem_sh, above_core_share=above)
    tp = taps(r); ca, cb = (int(q * CORE) for q in window)
    row['taps'] = {k: shares(tp[k][ca:cb], CORE, ls, fx['rate'])[0] for k in TAPS}
    pre = row['taps']['pre_filter']['rms']; perc = row['taps']['percussion']['rms']
    row['percussion_share_of_pre_filter'] = float(perc ** 2 / pre ** 2) if pre > 0 else None
    # valid energy by output band (device-independent description; no speaker model)
    bands = {'<150': 0., '150-300': 0., '300-600': 0., '>=600': 0.}
    for (f, c, _), q in zip(ls, amp):
        if c != 'valid': continue
        key = '<150' if f < 150 else '150-300' if f < 300 else '300-600' if f < 600 else '>=600'
        bands[key] += abs(q) ** 2 / 2
    tot = sum(bands.values()); row['valid_by_band'] = {k: (v / tot if tot else None) for k, v in bands.items()}
    # crest factors
    cf_act = crest(w48)
    blocks = [np.max(np.abs(w48[j:j + FS // 20])) for j in range(0, len(w48) - FS // 20, FS // 20)]
    cf_typ = float(np.median(blocks) / np.sqrt(np.mean(w48 ** 2)))
    peaks, rms2, cf_fit, cf_new = 0., 0., [], []
    for i, f in enumerate(notes):
        g = groups_of(ls, amp, i)
        if not g: continue

        span = 1.0 if fx['rate'] else max(2, round(.05 * f)) / f
        cf_f, cf_o, cf_n, pk, rm = optimise(g, span, ITERS, RESTARTS)
        peaks += pk; rms2 += rm ** 2; cf_fit.append(cf_f); cf_new.append(cf_n)
    v = stem_sh['valid']; nv = stem_sh['near_valid']
    cf_opt = peaks / np.sqrt(rms2) if rms2 > 0 else None
    row['crest'] = dict(actual=cf_act, actual_typical_block=cf_typ, valid_fitted_phase=cf_fit, valid_newman=cf_new,
                        valid_optimised=cf_opt)
    if v and cf_opt:
        inv = -10 * np.log10(v)
        row['ceiling_db'] = dict(
            equal_energy=inv, equal_energy_near_valid=-10 * np.log10(nv) if nv else None,
            equal_peak=20 * np.log10(cf_act / cf_opt) + inv,
            equal_peak_typical_block=20 * np.log10(cf_typ / cf_opt) + inv,
            equal_peak_near_valid=20 * np.log10(cf_act / cf_opt) - 10 * np.log10(nv) if nv else None,
            phase_part=(20 * np.log10(cf_fit[0] / cf_opt) if len(cf_fit) == 1 else None),
            newman_phase_part=(20 * np.log10(cf_fit[0] / cf_new[0]) if len(cf_fit) == 1 else None))
    return row


def short_row(fx, r, steady_power):
    f = fx['notes'][0]; d = fx['duration']
    stem = resample_poly(r['stem'][r['latency']:, 0].astype(float), 1, 16)
    hp = harmonic_power(stem, f)
    tp = taps(r); band = demod_power(tp['band_delayed191'], f, .35 * f); h = demod_power(tp['original_h'], f, .35 * f)
    env2 = resample_poly(fx['env'], 1, 16) ** 2 * .12 ** 2 / 2  # the input's power at f
    steady_in = .12 ** 2 / 2
    notes = []
    for s in SHORT_STARTS:
        a, b = int((s - .02) * CORE), int((s + d + .3) * CORE)
        e_note = float(hp[a:b].sum() / CORE); e_dur = float(env2[a:b].sum() / CORE / steady_in)
        peak = float(np.max(np.abs(r['stem'][r['latency']:, 0][int((s - .02) * FS):int((s + d + .3) * FS)])))
        notes.append(dict(coverage_db=db(e_note / (steady_power['valid_power'] * e_dur)),
                          drive_db=db(h[a:b].sum() / band[a:b].sum()) if band[a:b].sum() > 0 else None,
                          peak_vs_steady_db=float(20 * np.log10(peak / steady_power['peak'])) if peak > 0 else None))
    med = lambda key: float(np.median([q[key] for q in notes if q[key] is not None]))
    return dict(notes=notes, coverage_db=med('coverage_db'), drive_db=med('drive_db'),
                peak_vs_steady_db=med('peak_vs_steady_db'))


def main():
    global ITERS, RESTARTS
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--models', default=','.join(m for m, _, _ in MODELS))
    p.add_argument('--iters', type=int, default=ITERS)
    p.add_argument('--restarts', type=int, default=RESTARTS)
    p.add_argument('--only', default='', help='comma-separated fixture names (development checks)')
    a = p.parse_args()
    ITERS, RESTARTS = a.iters, a.restarts
    lib = P.api(a.library.resolve()); pad = np.zeros(FS)
    models = [m for m in MODELS if m[0] in a.models.split(',')]
    fx = [q for q in fixtures() if not a.only or q['name'] in a.only.split(',')]; rows = []; steady_power = {}
    for model, flags, stage in models:
        for f_ in fx:
            r = P.render(lib, np.r_[f_['x'], pad], FS, flags, stage_flags=stage)
            kind = f_['kind']
            if kind == 'pair' and abs(f_['notes'][1] - f_['notes'][0]) < UNRESOLVED_HZ: kind = 'pair_unresolved'
            row = dict(model=model, fixture=f_['name'], kind=kind, notes=f_['notes'], rate=f_['rate'])
            if f_['kind'] == 'short':
                row.update(short_row(f_, r, steady_power[(model, f_['notes'][0])]))
                print('SHORT', model, f_['name'], f"coverage {row['coverage_db']:+.1f} dB drive {row['drive_db']:+.1f} dB"
                      f" peak {row['peak_vs_steady_db']:+.1f} dB", flush=True)
            else:
                row.update(steady_row(f_, r))
                if f_['kind'] == 'steady':
                    a0, b0 = (int(q * FS) for q in STEADY)
                    z = resample_poly(r['stem'][a0:b0, 0].astype(float), 1, 16)
                    steady_power[(model, f_['notes'][0])] = dict(
                        valid_power=float(np.mean(harmonic_power(z, f_['notes'][0])[300:-300])),
                        peak=float(np.max(np.abs(r['stem'][a0:b0, 0]))))
                s = row['stem']; c = row.get('ceiling_db', {})
                print('ROW', model, f_['name'], ' '.join(f"{k}:{100 * s[k]:.1f}%" for k in
                                                       ('valid', 'fundamental', 'intermod', 'ghost', 'other', 'near_valid')),
                      f"| CF act {row['crest']['actual']:.2f} opt {row['crest']['valid_optimised'] or 0:.2f}",
                      f"| ceiling E {c.get('equal_energy', 0):+.2f} P {c.get('equal_peak', 0):+.2f}"
                      f" (typ {c.get('equal_peak_typical_block', 0):+.2f}) phase {c.get('phase_part') or 0:+.2f}"
                      f" pitch {row['layer_fundamental_cents'][0]:+.1f}c", flush=True)
            rows.append(row)
    summary = {}
    for model, _, _ in models:
        for kind in ('steady', 'am', 'pair', 'pair_unresolved'):
            sub = [q for q in rows if q['model'] == model and q['kind'] == kind and 'ceiling_db' in q]
            if not sub: continue
            summary[f'{model}/{kind}'] = {k: dict(median=float(np.median(v)), min=float(np.min(v)), max=float(np.max(v)))
                                          for k in ('equal_energy', 'equal_peak', 'equal_peak_typical_block',
                                                    'equal_peak_near_valid')
                                          if (v := [q['ceiling_db'][k] for q in sub if q['ceiling_db'][k] is not None])}
        sub = [q for q in rows if q['model'] == model and q['kind'] == 'short']
        if sub:
            summary[f'{model}/short'] = {k: float(np.median([q[k] for q in sub])) for k in
                                         ('coverage_db', 'drive_db', 'peak_vs_steady_db')}
    for k, v in summary.items(): print('SUMMARY', k, json.dumps(v), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r0_ceiling.v1', issue=4, held_out=False,
                                        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
