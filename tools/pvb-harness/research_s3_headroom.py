#!/usr/bin/env python3
"""Study 3 development (#4 follow-up): how much of the envelope-target interaction is left once C1 is on?

Study 1 bounded the kick late (80-500 ms) interaction of the envelope target with oracle B2 (as and ps := bed-only
values from the B2 start onwards); study 2 found C1 (stage flag 8192) removes part of it. Per model, on the
development and preservation cohorts only (both confirmation cohorts stay closed), the kick/broadband E change
against the unmodified model of:
  C1      C1 alone (study 2 candidate)
  B2      study 1 oracle on the unmodified model (bed and impact renders unmodified)
  C1+B2   the oracle applied on top of C1 (bed-only as/ps taken from the C1 bed render; C1 bed and impact)
and the remainder C1+B2 against C1. A remainder near 0 means C1 already reaches the oracle for that model.
Output -18 dB. G = median over waveforms of the reduction (waveform value = median over levels), as in study 1.
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
from research_s2_candidate import MODELS
from research_s2_envelope import table

FS, CORE = S.FS, S.CORE
C1 = 8192
OUT_DB = -18


def render(lib, x, flags, mode, stage, env=None, e=(0, 0)):
    keep = []

    def ptr(a):
        a = np.ascontiguousarray(a, np.float64); keep.append(a); return a.ctypes.data_as(CF.DP)

    def hook(lib_, handle):
        assert lib_.pvb_set_stage_inject(handle, 2, None, None, 0, 0, ptr(env[0]), ptr(env[1]), e[0], e[1],
                                         len(env[0])) == 1, 'inject refused'
    return P.render(lib, x, FS, flags, impact_mode=mode, out_db=OUT_DB, stage_flags=stage,
                    before_process=hook if env is not None else None)


def change(ev, base):
    return {w: (10 * np.log10(ev[w] / base[w])) if ev[w] > 0 and base[w] > 0 else None for w in CF.WINDOWS}


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
            kind = next((k for k in ('kick', 'noise') if k in shape), None)
            n = len(t); xb = np.r_[b, pad]
            for model, flags, mode in MODELS:
                rb = {s: render(lib, xb, flags, mode, s) for s in (0, C1)}; tb = {s: table(rb[s]) for s in rb}
                for level in levels:
                    impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]; xi = np.r_[impact, pad]
                    row = dict(cohort=cohort, shape=shape, type=kind, model=model, impact_peak_dbfs=level)
                    inter = {}
                    for s in (0, C1):
                        rx, ri = render(lib, x, flags, mode, s), render(lib, xi, flags, mode, s)
                        (tx, nx), (ti, ni), (tbs, nb) = table(rx), table(ri), tb[s]; m = min(nb, nx, ni)
                        e0 = CF.b2_start(ti['env_a'][:m], onset)
                        sub = lambda r_: S.aligned(r_, n, 'stem') - S.aligned(rb[s], n, 'stem') - S.aligned(ri, n, 'stem')
                        inter[s] = CF.window_energy(sub(rx), t, onset, duration)
                        rv = render(lib, x, flags, mode, s, env=(tbs['env_a'][:m], tbs['env_p'][:m]), e=(e0, m))
                        inter[f'{s}+B2'] = CF.window_energy(sub(rv), t, onset, duration)
                    base = inter[0]
                    row['C1'] = change(inter[C1], base); row['B2'] = change(inter['0+B2'], base)
                    row['C1+B2'] = change(inter[f'{C1}+B2'], base); row['remainder'] = change(inter[f'{C1}+B2'], inter[C1])
                    cases.append(row)
                    print(cohort, shape, model, level, ' '.join(f"{v}:{(row[v]['late'] or 0):+.1f}"
                                                                for v in ('C1', 'B2', 'C1+B2', 'remainder')), flush=True)
    summary = []
    for cohort in cohorts:
        for model, _, _ in MODELS:
            for kind in ('kick', 'noise'):
                sub = [c for c in cases if (c['cohort'], c['model'], c['type']) == (cohort, model, kind)]
                if not sub: continue
                shapes = sorted({c['shape'] for c in sub}); row = dict(cohort=cohort, model=model, type=kind)
                for v in ('C1', 'B2', 'C1+B2', 'remainder'):
                    for w in CF.WINDOWS:
                        per = [float(np.median(vals)) for s in shapes
                               if (vals := [c[v][w] for c in sub if c['shape'] == s and c[v][w] is not None])]
                        row[f'{v}_{w}_G'] = float(np.median([-q for q in per])) if per else None
                        row[f'{v}_{w}_reducing'] = f"{sum(q < 0 for q in per)}/{len(per)}"
                summary.append(row); print('SUMMARY', json.dumps(row), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study3.headroom.v1', issue=4, out_db=OUT_DB,
                                        confirmation_used=False, summary=summary, cases=cases), indent=2) + '\n',
                        encoding='utf-8')


if __name__ == '__main__':
    main()
