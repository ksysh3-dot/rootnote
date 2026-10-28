#!/usr/bin/env python3
"""Study 2 development: which tracks inflate the nominal amplitude (ps) after a kick.

research_s2_envelope.py showed that the kick late interaction is carried by ps: replacing ps alone with the bed-only
value (B2p) removes it, the bed-only gain sits at 1 throughout while the mixture's gain falls below 1. Here the harmonic
trace (per 16-sample hop, up to 12 tracks: id, state, f, a, fade, life, missing, age) of the mixture and of the
bed-only render are compared over the late window (80-500 ms after the impact's end, core clock) for the kick cases of
the development and preservation cohorts. A mixture track is "extra" when no bed track lies within 3 % of its
frequency in the same hop. Output -18 dB; the study 1 confirmation cohort is not used.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
import numpy as np
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
import test_harmonic_continuity as H
from p1plus_paths import default_library

FS, CORE = S.FS, S.CORE
STATE = {1: 'birth', 2: 'tracked', 3: 'held', 4: 'release', 5: 'end'}


def hops(r):
    rows = r['rows']; ts = H.tracks(rows); k = H.core_indices(rows)
    return {int(c): [dict(id=int(t[0]) | (int(t[13]) << 16), state=int(t[1]), f=float(t[2]), a=float(t[4]),
                          fade=float(t[7]), age=int(t[8]), missing=int(t[9]), life=float(t[11]))
                     for t in tr if 1 <= int(t[1]) <= 4 and t[2] > 0] for c, tr in zip(k, ts)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); CF.bind(lib)
    cohorts = {'development': ([f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)), S.LEVELS),
               'preserve': (list(CF.preserve_fixtures()), (-12, -6))}
    pad = np.zeros(FS // 2); cases = []
    for cohort, (fixtures, levels) in cohorts.items():
        for shape, _bed, t, b, z, onset, duration in fixtures:
            if 'kick' not in shape: continue
            for model, flags, mode in S.MODELS:
                hb = hops(CF.render(lib, np.r_[b, pad], flags, mode, -18))
                for level in levels:
                    impact = z * 10 ** (level / 20)
                    hx = hops(CF.render(lib, np.r_[b + impact, pad], flags, mode, -18))
                    k0, k1 = int((onset + duration + .08) * CORE), int((onset + duration + .5) * CORE)
                    keys = sorted(k for k in hx if k0 <= k < k1 and k in hb)
                    n_mix = [len(hx[k]) for k in keys]; n_bed = [len(hb[k]) for k in keys]
                    nom = lambda trs: sum(t['a'] * t['fade'] * t['life'] for t in trs)
                    nom_mix = np.array([nom(hx[k]) for k in keys]); nom_bed = np.array([nom(hb[k]) for k in keys])
                    extra, extra_states, extra_nom, dup = [], Counter(), [], 0
                    for k in keys:
                        e = [t for t in hx[k] if not any(abs(t['f'] - u['f']) <= .03 * u['f'] for u in hb[k])]
                        extra += e; extra_nom.append(nom(e))
                        for t in e: extra_states[STATE[t['state']]] += 1
                        fs_ = sorted(t['f'] for t in hx[k])
                        dup += any(fs_[j + 1] - fs_[j] <= .03 * fs_[j] for j in range(len(fs_) - 1))
                    ids = Counter(t['id'] for t in extra)
                    row = dict(cohort=cohort, shape=shape, model=model, impact_peak_dbfs=level, late_hops=len(keys),
                               mean_tracks_mix=float(np.mean(n_mix)) if keys else None,
                               mean_tracks_bed=float(np.mean(n_bed)) if keys else None,
                               nominal_mix_vs_bed_db=S.db(float(np.sum(nom_mix ** 2)), float(np.sum(nom_bed ** 2))),
                               hops_with_extra=int(sum(x > 0 for x in extra_nom)),
                               extra_nominal_share=float(np.sum(extra_nom) / max(np.sum(nom_mix), 1e-30)),
                               extra_states=dict(extra_states), hops_with_near_duplicates=int(dup),
                               extra_tracks=[dict(id=i, hops=c, **{k_: v for k_, v in next(t for t in extra if t['id'] == i).items()
                                                                  if k_ in ('f', 'a', 'state', 'age', 'missing', 'life')})
                                             for i, c in ids.most_common(4)])
                    cases.append(row)
                    print(cohort, shape, model, level, f"hops {len(keys)} tracks {row['mean_tracks_mix']}/{row['mean_tracks_bed']}",
                          f"nom {row['nominal_mix_vs_bed_db']:+.1f}dB extraShare {row['extra_nominal_share']:.2f}",
                          f"extraHops {row['hops_with_extra']} dupHops {dup} states {dict(extra_states)}",
                          'extra', [(round(e['f'], 1), round(e['a'], 4), STATE[e['state']], e['hops']) for e in row['extra_tracks']],
                          flush=True)
    result = dict(schema='rootnote.study2.tracks.v1', issue=4, based_on_tag='s1-v2-final', confirmation_used=False,
                  source_sha256=S.source_hashes(), cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
