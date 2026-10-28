#!/usr/bin/env python3
"""Study 2 development: candidate C1 (power-sum nominal amplitude) against the unmodified models.

Mechanism (research_s2_envelope.py, research_s2_tracks.py): after a kick the kick's own low tail stays as 1-2 extra
tracks next to the bed's track. The nominal amplitude ps adds the tracks linearly, while the music envelope as is a
closing (min of a 60 ms max) of the band's analytic envelope, which follows the dips of the beating sum. So as < ps
and the envelope imposition cuts the layer, although neither sound alone is cut. C1 (host stage flag 8192) sums the
nominal amplitudes as powers; a single track is unchanged.

Every model is rendered as a whole with and without C1 (mixture, bed-only and impact-only all with the same model):
  interaction  E change of the candidate against the unmodified model (study 1 definition, early/late windows)
  attack       attack-window generated energy change of the mixture (preservation cost, study 1 budget)
  beds         ordinary notes alone (R01 controls: steady, AM, gliss, two tones; development/preservation beds):
               generated-layer energy change and the largest sample difference
Development and preservation cohorts only; output -18 dB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
from p1plus_paths import default_library
from research_p1pp_track_controls import signals

FS = S.FS
C1 = 8192
CANDIDATES = {'C1': C1}


def render(lib, x, flags, mode, stage):
    return P.render(lib, x, FS, flags, impact_mode=mode, stage_flags=stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve())
    cohorts = {'development': ([f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)), S.LEVELS),
               'preserve': (list(CF.preserve_fixtures()), (-12, -6))}
    pad = np.zeros(FS // 2); cases, beds = [], []
    for name, sig in signals(FS, 3 * FS).items():
        for model, flags, mode in S.MODELS:
            x = np.r_[sig, pad]; r0 = render(lib, x, flags, mode, 0)
            for cand, stage in CANDIDATES.items():
                r1 = render(lib, x, flags, mode, stage); n = len(sig)
                y0, y1 = S.aligned(r0, n, 'stem'), S.aligned(r1, n, 'stem'); m = slice(FS // 2, n)
                beds.append(dict(signal=name, model=model, candidate=cand, layer_change_db=S.db(S.energy(y1[m]), S.energy(y0[m])),
                                 max_abs_difference=float(np.max(np.abs(y1 - y0))), bit_identical=bool(np.array_equal(y0, y1))))
                print('BED', name, model, cand, f"{beds[-1]['layer_change_db']:+.2f}dB", beds[-1]['bit_identical'], flush=True)
    for cohort, (fixtures, levels) in cohorts.items():
        for shape, _bed, t, b, z, onset, duration in fixtures:
            kind = next((k for k in ('kick', 'noise') if k in shape), None)
            n = len(t); xb = np.r_[b, pad]
            for model, flags, mode in S.MODELS:
                rb = {s: render(lib, xb, flags, mode, s) for s in (0, *CANDIDATES.values())}
                for cand, stage in CANDIDATES.items():
                    yb0, yb1 = S.aligned(rb[0], n, 'stem'), S.aligned(rb[stage], n, 'stem')
                    beds.append(dict(signal=f'{cohort}:{shape}', model=model, candidate=cand,
                                     layer_change_db=S.db(S.energy(yb1), S.energy(yb0)),
                                     max_abs_difference=float(np.max(np.abs(yb1 - yb0))),
                                     bit_identical=bool(np.array_equal(yb0, yb1))))
                for level in levels:
                    impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]; xi = np.r_[impact, pad]
                    row = dict(cohort=cohort, shape=shape, type=kind, model=model, impact_peak_dbfs=level)
                    e = {}
                    for s in (0, *CANDIDATES.values()):
                        rx, ri = render(lib, x, flags, mode, s), render(lib, xi, flags, mode, s)
                        inter = S.aligned(rx, n, 'stem') - S.aligned(rb[s], n, 'stem') - S.aligned(ri, n, 'stem')
                        e[s] = (CF.window_energy(inter, t, onset, duration),
                                CF.window_energy(S.aligned(rx, n, 'stem'), t, onset, duration, ('attack',))['attack'])
                    row['base_energy'] = e[0][0]
                    for cand, stage in CANDIDATES.items():
                        row[cand] = {w: (10 * np.log10(e[stage][0][w] / e[0][0][w])) if e[stage][0][w] > 0 and e[0][0][w] > 0 else None
                                     for w in CF.WINDOWS}
                        row[cand + '_attack_change_db'] = S.db(e[stage][1], e[0][1])
                    cases.append(row)
                    print(cohort, shape, model, level, ' '.join(
                        f"{c}: early {(row[c]['early'] or 0):+.1f} late {(row[c]['late'] or 0):+.1f} atk {row[c + '_attack_change_db']:+.2f}"
                        for c in CANDIDATES), flush=True)
    summary = []
    for cohort in cohorts:
        for model in sorted({c['model'] for c in cases}):
            for kind in ('kick', 'noise'):
                sub = [c for c in cases if (c['cohort'], c['model'], c['type']) == (cohort, model, kind)]
                if not sub: continue
                shapes = sorted({c['shape'] for c in sub})
                for cand in CANDIDATES:
                    row = dict(cohort=cohort, model=model, type=kind, candidate=cand)
                    for w in CF.WINDOWS:
                        per = [float(np.median(v)) for s in shapes if (v := [c[cand][w] for c in sub if c['shape'] == s and c[cand][w] is not None])]
                        row[f'{w}_G'] = float(np.median([-q for q in per])) if per else None
                        row[f'{w}_L'] = max([q for q in per if q > 0], default=0.0)
                        row[f'{w}_reducing'] = f"{sum(q < 0 for q in per)}/{len(per)}"
                    att = [c[cand + '_attack_change_db'] for c in sub]
                    row['attack_median_db'] = float(np.median(att)); row['attack_worst_db'] = float(min(att))
                    summary.append(row); print('SUMMARY', json.dumps(row), flush=True)
    for b_ in beds:
        if not b_['bit_identical'] and abs(b_['layer_change_db']) > .05:
            print('BEDCHANGE', b_['signal'], b_['model'], b_['candidate'], f"{b_['layer_change_db']:+.2f}dB", flush=True)
    result = dict(schema='rootnote.study2.candidate.v1', issue=4, candidates=CANDIDATES, out_db=-18,
                  confirmation_used=False, source_sha256=S.source_hashes(),
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  summary=summary, beds=beds, cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
