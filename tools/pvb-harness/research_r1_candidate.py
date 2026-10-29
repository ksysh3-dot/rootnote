#!/usr/bin/env python3
"""Resultant R1 (#4 follow-up) development check: the crest-optimal unreferenced harmonic phases (stage 1048576)
against the same model without them. No fixture is held out and nothing here is a listening score.

Per fixture and model pair (P1 / P1 + R1, P1 + C1 / P1 + C1 + R1), on the generated layer (stem):
  peak_db, rms_db   whole-file true peak (48 kHz) and energy change; gain_db = rms_db - peak_db is the layer's level
                    gain at the same peak (the valid share is about 100 %, phase 0)
  steady window     crest factors, the largest change of a harmonic magnitude k = 2..8 (harmonics within 30 dB of the
                    strongest), the layer fundamental's change (cents), 50 ms RMS envelope change
  pitch salience    a summary autocorrelation proxy: 40 gammatone channels (ERB spaced, 80-2000 Hz, 16 kHz), half-wave
                    rectified and low-passed at 1 kHz, mean-removed autocorrelation summed over channels;
                    salience = SACF(T0) / SACF(0) (T0 = 1 / f within 3 %), dominance = SACF(T0) over the largest SACF
                    between 1.5 ms and 0.75 T0 (an octave-up or other competing period)
Fixtures: the phase 0 steady notes, AM notes, resolved pairs and short notes, plus harmonic-rich bass (the input has
its own partials, so R1 applies only to harmonics it lacks), an 808-like decaying sine with a falling glide, and a
vibrato note.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import butter, gammatone, lfilter, resample_poly, sosfilt
import research_p1plus as P
import research_r0_ceiling as R0
from p1plus_paths import default_library

FS, CORE, FSA = 48000, 3000, 16000
R1 = 1048576
PAIRS = (('p1', (0, 0), (0, R1)), ('p1_c1', (0, 8192), (0, 8192 | R1)))
K = np.arange(2, 9)


def fixtures():
    for f in R0.fixtures():
        if f['kind'] == 'pair' and abs(f['notes'][1] - f['notes'][0]) < R0.UNRESOLVED_HZ: continue
        yield f
    t = np.arange(round(R0.DUR * FS)) / FS
    for f in (41., 55., 82.):
        x = sum(np.cos(2 * np.pi * k * f * t + .3 * k * k) / k for k in range(1, 11))
        yield dict(name=f'saw_{f:g}', kind='harmonic', notes=[f], rate=0., x=.12 * x / np.max(np.abs(x)))
    x = np.zeros(len(t))
    for s in (.5, 1.5, 2.5, 3.5):
        u = t - s; on = u >= 0
        ph = 2 * np.pi * (49 * u + 49 * .12 * .03 * (1 - np.exp(-np.maximum(u, 0) / .03)))
        x += np.where(on, np.minimum(1, u / .002) * np.exp(-np.maximum(u, 0) / .6) * np.cos(ph), 0)
    yield dict(name='808_49', kind='808', notes=[49.], rate=0., x=.12 * x)
    ph = 2 * np.pi * 55 * t + .008 * 55 / 5.5 * np.sin(2 * np.pi * 5.5 * t)
    yield dict(name='vibrato_55', kind='vibrato', notes=[55.], rate=0., x=.12 * np.cos(ph))


def erb_space(lo, hi, n):
    e = lambda f: 21.4 * np.log10(1 + .00437 * f)
    return (10 ** (np.linspace(e(lo), e(hi), n) / 21.4) - 1) / .00437


LP = butter(2, 1000, fs=FSA, output='sos')
BANK = [gammatone(cf, 'iir', fs=FSA) for cf in erb_space(80, 2000, 40)]


def salience(y48, f0):
    y = resample_poly(np.asarray(y48, float), 1, 3); n = len(y)
    acc = np.zeros(n)
    for b, a in BANK:
        u = sosfilt(LP, np.maximum(lfilter(b, a, y), 0)); u -= u.mean()
        U = np.fft.rfft(u, 2 * n); acc += np.fft.irfft(np.abs(U) ** 2)[:n]
    if acc[0] <= 0: return None
    s = acc / acc[0]; t0 = FSA / f0
    lo, hi = int(t0 * .97), int(np.ceil(t0 * 1.03)) + 1
    peak = float(s[lo:hi].max())
    comp = float(s[int(.0015 * FSA):int(.75 * t0)].max())
    return dict(salience=peak, dominance=peak / comp if comp > 0 else None)


def harmonics(z, f):
    tt = np.arange(len(z)) / CORE
    design = np.column_stack([v for k in K for v in (np.cos(2 * np.pi * k * f * tt), np.sin(2 * np.pi * k * f * tt))])
    coef = np.linalg.lstsq(design, z, rcond=1e-10)[0]
    return np.abs(coef[0::2] - 1j * coef[1::2])


def rms_env(y, n=FS // 20):
    m = len(y) // n; return np.sqrt(np.mean(y[:m * n].reshape(m, n) ** 2, axis=1))


def compare(fx, rb, rc):
    yb, yc = (r['stem'][:, 0].astype(float) for r in (rb, rc))
    row = dict(peak_db=float(20 * np.log10(np.max(np.abs(yc)) / np.max(np.abs(yb)))),
               rms_db=float(10 * np.log10(np.sum(yc ** 2) / np.sum(yb ** 2))))
    row['gain_db'] = row['rms_db'] - row['peak_db']
    eb, ec = rms_env(yb), rms_env(yc); live = eb > eb.max() * 10 ** (-30 / 20)
    row['envelope_change_db'] = float(np.max(np.abs(20 * np.log10(ec[live] / eb[live]))))
    window = fx.get('window', R0.STEADY) if fx['kind'] in ('steady', 'am', 'pair', 'harmonic', 'vibrato') else None
    f0 = fx['notes'][0]
    if window:
        a, b = (int(q * FS) for q in window)
        zb, zc = (resample_poly(y[a:b], 1, 16) for y in (yb, yc))
        row['crest'] = [R0.crest(yb[a:b]), R0.crest(yc[a:b])]
        row['steady_gain_db'] = float(20 * np.log10(row['crest'][0] / row['crest'][1]))
        if fx['kind'] != 'pair':
            fb, fc = R0.layer_fundamental(zb, CORE, f0), R0.layer_fundamental(zc, CORE, f0)
            row['pitch_change_cents'] = float(1200 * np.log2(fc / fb))
            hb, hc = harmonics(zb, fb), harmonics(zc, fc); keep = hb >= hb.max() * 10 ** (-30 / 20)
            row['harmonic_change_db'] = float(np.max(np.abs(20 * np.log10(hc[keep] / hb[keep]))))
            sb, sc = salience(yb[a:a + FS], fb), salience(yc[a:a + FS], fc)
            row['salience'] = [sb, sc]
    elif fx['kind'] == '808':
        sb, sc = (salience(y[int(.55 * FS):int(1.35 * FS)], f0) for y in (yb, yc)); row['salience'] = [sb, sc]
    if fx['kind'] == 'short':
        d = fx['duration']; lat = rb['latency']; per = []
        for s in R0.SHORT_STARTS:
            a, b = int((s - .02) * FS) + lat, int((s + d + .3) * FS) + lat
            per.append(float(20 * np.log10(np.max(np.abs(yc[a:b])) / np.max(np.abs(yb[a:b])))))
        row['note_peak_change_db'] = per
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); pad = np.zeros(FS); rows = []
    for fx in fixtures():
        x = np.r_[fx['x'], pad]
        for model, base, cand in PAIRS:
            rb, rc = (P.render(lib, x, FS, fl, stage_flags=st) for fl, st in (base, cand))
            row = dict(model=model, fixture=fx['name'], kind=fx['kind'], **compare(fx, rb, rc)); rows.append(row)
            sal = row.get('salience')
            sal_txt = '' if not sal or None in sal else \
                f" sal {sal[0]['salience']:.3f}->{sal[1]['salience']:.3f} dom {sal[0]['dominance']:.2f}->{sal[1]['dominance']:.2f}"
            print('ROW', model, fx['name'], f"gain {row['gain_db']:+.2f} (peak {row['peak_db']:+.2f} rms {row['rms_db']:+.3f})",
                  f"steady {row['steady_gain_db']:+.2f}" if 'steady_gain_db' in row else '',
                  f"harm {row['harmonic_change_db']:.2f} dB pitch {row['pitch_change_cents']:+.2f}c" if 'harmonic_change_db' in row else '',
                  f"env {row['envelope_change_db']:.2f} dB", sal_txt,
                  f"notes {' '.join(f'{v:+.2f}' for v in row['note_peak_change_db'])}" if 'note_peak_change_db' in row else '',
                  flush=True)
    summary = {}
    for model, _, _ in PAIRS:
        sub = [q for q in rows if q['model'] == model]
        for kind in sorted({q['kind'] for q in sub}):
            g = [q['gain_db'] for q in sub if q['kind'] == kind]
            summary[f'{model}/{kind}'] = dict(gain_median=float(np.median(g)), gain_min=float(np.min(g)),
                                              gain_max=float(np.max(g)))
        sal = [(q['salience'][0], q['salience'][1]) for q in sub if q.get('salience') and None not in q['salience']]
        summary[f'{model}/all'] = dict(
            gain_min=float(min(q['gain_db'] for q in sub)),
            harmonic_change_max_db=float(max(q.get('harmonic_change_db', 0) for q in sub)),
            pitch_change_max_cents=float(max(abs(q.get('pitch_change_cents', 0)) for q in sub)),
            envelope_change_max_db=float(max(q['envelope_change_db'] for q in sub)),
            salience_change_median=float(np.median([c['salience'] - b['salience'] for b, c in sal])),
            salience_change_min=float(min(c['salience'] - b['salience'] for b, c in sal)),
            dominance_min=[float(min(b['dominance'] for b, _ in sal)), float(min(c['dominance'] for _, c in sal))])
    for k, v in summary.items(): print('SUMMARY', k, json.dumps(v), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r1_candidate.v1', issue=4, held_out=False,
                                        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
