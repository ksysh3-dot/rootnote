#!/usr/bin/env python3
"""Study 2 development (#4 follow-up): which half of the envelope target carries the kick late interaction.

Study 1 (tag s1-v2-final) attributed the kick late (80-500 ms after the impact) non-additive energy to stage 4, the
envelope target: gain = as / ps (cut only), as = smoothed closing of the harmonic-band analytic envelope (the music),
ps = smoothed nominal amplitude of the generated grains. B2 replaced both with bed-only values from env10 onwards.
Here the two halves are replaced separately on the development and preservation cohorts only (the study 1
confirmation cohort is closed and is not used):
  B2   as := bed, ps := bed      (study 1 oracle, for reference)
  B2a  as := bed, ps := mixture  (music envelope only)
  B2p  as := mixture, ps := bed  (generated amplitude only)
Per case it also records, over the late window, how far the mixture's env_a, env_p, nominal amplitude, raw grain
and applied gain sit from the bed-only render (dB of mean square, 3 kHz core clock), and how often the gain is
clamped at 1. Output -18 dB only (study 1: -18 and -3 dB gave identical results, limiter gain reduction 0).
"""
import argparse
import json
from pathlib import Path
import numpy as np
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS, CORE = S.FS, S.CORE
TRACE = ('env_a', 'env_p', 'nominal_amplitude', 'raw_grain', 'applied_gain', 'tonal_after_gain')
VARIANTS = {'B2': ('bed', 'bed'), 'B2a': ('bed', 'mix'), 'B2p': ('mix', 'bed')}


def table(r):
    s = r['stages']
    idx = (s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32))
    out = {}
    for k in TRACE:
        a = np.zeros(int(idx.max()) + 1); a[idx] = s[:, COLUMNS.index(k)]; out[k] = a
    return out, int(idx.max()) + 1


def ms_db(a, b):
    return S.db(float(np.mean(np.asarray(a) ** 2)), float(np.mean(np.asarray(b) ** 2)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); CF.bind(lib)
    cohorts = {'development': ([f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)), S.LEVELS),
               'preserve': (list(CF.preserve_fixtures()), (-12, -6))}
    pad = np.zeros(FS // 2); out_db = -18; cases = []
    for cohort, (fixtures, levels) in cohorts.items():
        for shape, _bed, t, b, z, onset, duration in fixtures:
            kind = next((k for k in ('kick', 'noise') if k in shape), None)
            n = len(t); xb = np.r_[b, pad]
            for model, flags, mode in S.MODELS:
                rb = CF.render(lib, xb, flags, mode, out_db); tb, nb = table(rb)
                for level in levels:
                    impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]
                    rx = CF.render(lib, x, flags, mode, out_db); ri = CF.render(lib, np.r_[impact, pad], flags, mode, out_db)
                    tx, nx = table(rx); ti, ni = table(ri); m = min(nb, nx, ni)
                    base = S.aligned(rx, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                    e_base = CF.window_energy(base, t, onset, duration)
                    e0 = CF.b2_start(ti['env_a'][:m], onset)
                    k0 = int(round((onset + duration + .08) * CORE)); k1 = min(m, int(round((onset + duration + .5) * CORE)))
                    late = slice(k0, k1)
                    row = dict(cohort=cohort, shape=shape, type=kind, model=model, impact_peak_dbfs=level,
                               b2_start_ms_after_onset=float((e0 / CORE - onset) * 1000), base_energy=e_base,
                               late_mix_vs_bed_db={k: ms_db(tx[k][late], tb[k][late]) for k in TRACE},
                               late_gain_clamped_mix=float(np.mean(tx['applied_gain'][late] >= 1 - 1e-12)),
                               late_gain_clamped_bed=float(np.mean(tb['applied_gain'][late] >= 1 - 1e-12)))
                    src = {'bed': tb, 'mix': tx}
                    for name, (sa, sp) in VARIANTS.items():
                        rv = CF.render(lib, x, flags, mode, out_db, 2, env=(src[sa]['env_a'][:m], src[sp]['env_p'][:m]),
                                       e=(e0, m))
                        y = S.aligned(rv, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                        ev = CF.window_energy(y, t, onset, duration)
                        row[name] = {w: (10 * np.log10(ev[w] / e_base[w])) if ev[w] > 0 and e_base[w] > 0 else None
                                     for w in CF.WINDOWS}
                    cases.append(row)
                    print(cohort, shape, model, level, ' '.join(f"{v}:{(row[v]['late'] or 0):+.1f}" for v in VARIANTS),
                          ' '.join(f"{k}:{row['late_mix_vs_bed_db'][k]:+.1f}" for k in TRACE),
                          f"clamp {row['late_gain_clamped_mix']:.2f}/{row['late_gain_clamped_bed']:.2f}", flush=True)
    summary = []
    for cohort in cohorts:
        for model in sorted({c['model'] for c in cases}):
            for kind in ('kick', 'noise'):
                sub = [c for c in cases if (c['cohort'], c['model'], c['type']) == (cohort, model, kind)]
                if not sub: continue
                shapes = sorted({c['shape'] for c in sub}); row = dict(cohort=cohort, model=model, type=kind)
                for v in VARIANTS:
                    for w in CF.WINDOWS:
                        per = [float(np.median(vals)) for s in shapes
                               if (vals := [c[v][w] for c in sub if c['shape'] == s and c[v][w] is not None])]
                        row[f'{v}_{w}_G'] = float(np.median([-q for q in per])) if per else None
                        row[f'{v}_{w}_reducing'] = f"{sum(q < 0 for q in per)}/{len(per)}"
                for k in TRACE:
                    row[f'late_{k}_median_db'] = float(np.median([c['late_mix_vs_bed_db'][k] for c in sub]))
                summary.append(row); print('SUMMARY', json.dumps(row), flush=True)
    result = dict(schema='rootnote.study2.envelope_split.v1', issue=4, based_on_tag='s1-v2-final', out_db=out_db,
                  cohorts=list(cohorts), confirmation_used=False, source_sha256=S.source_hashes(),
                  library_sha256=__import__('hashlib').sha256(a.library.read_bytes()).hexdigest(),
                  summary=summary, cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
