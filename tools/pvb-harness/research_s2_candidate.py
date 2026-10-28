#!/usr/bin/env python3
"""Study 2 (#4 follow-up): candidate C1 (power-sum nominal amplitude) against the unmodified models.

Mechanism (development: research_s2_envelope.py, research_s2_tracks.py): after a kick the kick's own low tail stays
as 1-2 extra tracks next to the bed's track. The nominal amplitude ps adds the tracks linearly, while the music
envelope as is a closing (min of a 60 ms max) of the band's analytic envelope, which follows the dips of the beating
sum. So as < ps and the envelope imposition cuts the layer, although neither sound alone is cut. C1 (host stage flag
8192) sums the nominal amplitudes as powers; a single track is unchanged.

Each model is rendered as a whole with and without C1 (mixture, bed-only and impact-only all with the same model):
  interaction  E change of the candidate against the unmodified model (study 1 definition, early/late windows,
               rounding mask decided once on the unmodified mixture), judged with the study 1 G/L rule
  attack       attack-window generated energy change of the mixture; budget from the development and
               preservation cohorts (median >= -1 dB, worst >= -3 dB) lowers near-adoption to hold-option
  notes        ordinary notes alone (R01 controls, run in every cohort, and the cohort's beds): generated-layer total
               energy ratio change (not a waveform-difference energy; the largest sample difference is reported only),
               and for the R01 controls whether block-size exactness (4096 vs 1379) is kept
  limiter      LIM_GR_DB of the mixture, bed-only and impact-only renders, unmodified and with C1
  direct       descriptive only: each model unmodified and with C1 against the unmodified original P1
Cohorts: development, preservation, regression (study 1 confirmation fixtures, seed 2026102801; regression only, per
GPT gate 2) and confirmation (seed 2026102802, opened once from a frozen tag, like study 1). Output -18 dB.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
import test_engine as T
from p1plus_paths import default_library
from research_p1pp_track_controls import signals

FS = S.FS
OUT_DB = -18
CANDIDATES = {'C1': 8192}
MODELS = (('p1', 0, 0),) + S.MODELS
CONFIRM_SEED = 2026102802


def render(lib, x, flags, mode, stage, block=4096):
    return P.render(lib, x, FS, flags, block=block, impact_mode=mode, stage_flags=stage)


def notes(lib, cohort, fixtures):
    """Ordinary notes alone: layer change, largest difference, block-size exactness kept."""
    pad = np.zeros(FS // 2); out = []
    items = [(n, s) for n, s in signals(FS, 3 * FS).items()] if cohort == 'controls' else \
        [(f'{cohort}:{f[0]}', f[3]) for f in fixtures]
    for name, sig in items:
        x = np.r_[sig, pad]; n = len(sig)
        for model, flags, mode in MODELS:
            r0 = render(lib, x, flags, mode, 0)
            for cand, stage in CANDIDATES.items():
                r1 = render(lib, x, flags, mode, stage)
                y0, y1 = S.aligned(r0, n, 'stem'), S.aligned(r1, n, 'stem'); m = slice(FS // 2, n)
                row = dict(signal=name, model=model, candidate=cand,
                           layer_change_db=S.db(S.energy(y1[m]), S.energy(y0[m])),
                           max_abs_difference=float(np.max(np.abs(y1 - y0))), bit_identical=bool(np.array_equal(y0, y1)))
                if cohort == 'controls':
                    b0 = render(lib, x, flags, mode, 0, 1379); b1 = render(lib, x, flags, mode, stage, 1379)
                    row['baseline_block_exact'] = bool(np.array_equal(r0['output'], b0['output']))
                    row['candidate_block_exact'] = bool(np.array_equal(r1['output'], b1['output']))
                out.append(row)
                print('NOTE', name, model, cand, f"{row['layer_change_db']:+.3f}dB identical {row['bit_identical']}",
                      '' if 'candidate_block_exact' not in row else
                      f"block {row['baseline_block_exact']}->{row['candidate_block_exact']}", flush=True)
    return out


NOTE_ANY_DB, NOTE_SINGLE_DB, SINGLE_NOTES = .5, .05, ('steady_65hz', 'continuous_gliss_50_to_90hz')


def decide(summary, note_rows):
    """Pre-registration (docs/STUDY2_PREREG.md): per model and candidate, the primary verdict (kick late) is lowered
    from near-adoption to hold-option when a secondary window (kick early, broadband early/late) worsens by more than
    half the primary improvement (L > G/2), when an ordinary note moves the layer by more than 0.5 dB (0.05 dB for a
    single-track note), or when block-size exactness is lost; a hold-option stays and nothing is rejected for it."""
    out = []
    for model in sorted({s['model'] for s in summary}):
        for cand in sorted({s['oracle'] for s in summary}):
            rows = [s for s in summary if (s['model'], s['oracle']) == (model, cand)]
            prim = next(s for s in rows if (s['type'], s['window']) == ('kick', 'late'))
            sec = [s for s in rows if (s['type'], s['window']) != ('kick', 'late')]
            G = prim['G_db'] or 0.
            sec_worst = max([s['L_db'] or 0. for s in sec], default=0.)
            mine = [n for n in note_rows if (n['model'], n['candidate']) == (model, cand)]
            note_worst = max([abs(n['layer_change_db']) for n in mine], default=0.)
            single_worst = max([abs(n['layer_change_db']) for n in mine if n['signal'] in SINGLE_NOTES], default=0.)
            block_lost = [n['signal'] for n in mine if n.get('baseline_block_exact') and not n.get('candidate_block_exact', True)]
            reasons = []
            if G > 0 and sec_worst > G / 2: reasons.append(f'secondary L {sec_worst:.2f} > G/2')
            if note_worst > NOTE_ANY_DB: reasons.append(f'note {note_worst:.2f} dB')
            if single_worst > NOTE_SINGLE_DB: reasons.append(f'single-track note {single_worst:.3f} dB')
            if block_lost: reasons.append('block exactness lost: ' + ','.join(block_lost))
            final = 'hold_option' if prim['verdict'] == 'near_adoption' and reasons else prim['verdict']
            out.append(dict(model=model, candidate=cand, primary=prim['verdict'], primary_raw=prim['raw_verdict'],
                            G_db=prim['G_db'], L_db=prim['L_db'], reducing=f"{prim['reducing_waveforms']}/{prim['valid_waveforms']}",
                            secondary_worst_L_db=sec_worst, note_worst_db=note_worst, single_note_worst_db=single_worst,
                            block_exactness_lost=block_lost, lowered_by=reasons, decision=final))
    return out


DIRECT = ('vsP1_unmodified', 'vsP1_C1')


def direct_vs_p1(cases):
    """D2, descriptive: each model unmodified and with C1 against the unmodified original P1 (flags 0) on the same
    fixture and level, change_db = 10 log10(E_model / E_P1); a window is left out when either side is masked."""
    p1 = {(c['shape'], c['impact_peak_dbfs']): c for c in cases if c['model'] == 'p1'}
    out = []
    for c in cases:
        q = p1.get((c['shape'], c['impact_peak_dbfs']))
        if q is None: continue
        ch = lambda e, w: (10 * np.log10(e / q['base_energy'][w])) if e > 0 and q['base_energy'][w] > 0 else None
        out.append(dict(shape=c['shape'], type=c['type'], model=c['model'], out_db=c['out_db'],
                        impact_peak_dbfs=c['impact_peak_dbfs'], b3_valid=True,
                        masked={w: q['masked'][w] or c['masked'][w] for w in CF.WINDOWS},
                        vsP1_unmodified={w: dict(change_db=ch(c['base_energy'][w], w)) for w in CF.WINDOWS},
                        vsP1_C1={w: dict(change_db=ch(c['C1'][w]['energy'], w)) for w in CF.WINDOWS},
                        vsP1_unmodified_attack_change_db=0.0, vsP1_C1_attack_change_db=0.0))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--cohort', choices=('development', 'preserve', 'regression', 'confirm'), default='development')
    p.add_argument('--frozen', default='')
    p.add_argument('--frozen-sha', default='')
    p.add_argument('--budget-from', type=Path, nargs='*', default=[])
    a = p.parse_args()
    ident = CF.checkout_identity(a.frozen)
    budget_rows, budget_sources, imported_notes = [], [], []
    for f in a.budget_from:
        r = json.loads(f.read_text(encoding='utf-8'))
        if r.get('cohort') not in CF.BUDGET_COHORTS: raise SystemExit(f'{f}: not a development/preservation report')
        budget_rows += [b for b in r['attack_budget'] if b['cohort'] == r['cohort']]
        imported_notes += [dict(n, source=r['cohort']) for n in r['notes']]
        budget_sources.append(dict(cohort=r['cohort'], file=f.name, checkout_sha=r['checkout']['checkout_sha']))
    if a.cohort == 'confirm':
        problems = []
        if not re.fullmatch(r'[0-9a-f]{40}', a.frozen_sha): problems.append('--frozen-sha is not a full commit SHA')
        if not a.frozen or ident['frozen_tag_sha'] is None: problems.append(f'tag {a.frozen!r} not found')
        elif ident['frozen_tag_sha'] != a.frozen_sha: problems.append(f"tag names {ident['frozen_tag_sha']}")
        if ident['checkout_sha'] != a.frozen_sha: problems.append(f"checkout is {ident['checkout_sha']}")
        if ident['tracked_changes'] is not False: problems.append('tracked files differ from the commit')
        if sorted(s['cohort'] for s in budget_sources) != sorted(CF.BUDGET_COHORTS):
            problems.append('needs --budget-from with one development and one preservation report')
        if any(s['checkout_sha'] != ident['checkout_sha'] for s in budget_sources):
            problems.append('budget reports come from another commit')
        if problems: raise SystemExit('the study 2 confirmation cohort stays closed: ' + '; '.join(problems))
    lib = P.api(a.library.resolve())
    if a.cohort == 'development':
        fixtures = [f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)); levels = S.LEVELS
    elif a.cohort == 'preserve':
        fixtures = list(CF.preserve_fixtures()); levels = (-12, -6)
    elif a.cohort == 'regression':
        fixtures = list(CF.confirm_fixtures(seed=CF.CONFIRM_SEED)); levels = (-12, -6)
    else:
        fixtures = list(CF.confirm_fixtures(seed=CONFIRM_SEED)); levels = (-12, -6)
    # D1: the R01 controls (with the block-size check) run in every cohort; the decision also uses the notes of the
    # development and preservation reports given with --budget-from (same commit, checked for confirm)
    note_rows = [dict(n, source=a.cohort) for n in notes(lib, a.cohort, fixtures) + notes(lib, 'controls', None)]
    pad = np.zeros(FS // 2); cases = []
    for shape, _bed, t, b, z, onset, duration in fixtures:
        kind = next((k for k in ('kick', 'noise') if k in shape), None)
        n = len(t); xb = np.r_[b, pad]
        for model, flags, mode in MODELS:
            rb = {s: render(lib, xb, flags, mode, s) for s in (0, *CANDIDATES.values())}
            for level in levels:
                impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]; xi = np.r_[impact, pad]
                assert np.max(abs(x)) < 1, 'no input clipping'
                e = {}
                for s in (0, *CANDIDATES.values()):
                    rx, ri = render(lib, x, flags, mode, s), render(lib, xi, flags, mode, s)
                    inter = S.aligned(rx, n, 'stem') - S.aligned(rb[s], n, 'stem') - S.aligned(ri, n, 'stem')
                    e[s] = (CF.window_energy(inter, t, onset, duration),
                            CF.window_energy(S.aligned(rx, n, 'stem'), t, onset, duration, ('attack',))['attack'], rx,
                            {k: float(r_['meters'][T.M['LIM_GR_DB']]) for k, r_ in (('mixture', rx), ('bed', rb[s]), ('impact', ri))})
                x32 = (b.astype(np.float32) + impact.astype(np.float32)).astype(np.float64)
                rr = render(lib, np.r_[x32, pad], flags, mode, 0)
                e_round = CF.window_energy(S.aligned(e[0][2], n, 'stem') - S.aligned(rr, n, 'stem'), t, onset, duration)
                base = e[0][0]
                row = dict(shape=shape, type=kind, model=model, out_db=OUT_DB, impact_peak_dbfs=level, b3_valid=True,
                           base_energy=base, rounding_energy=e_round,
                           limiter_gr_db=dict(unmodified=e[0][3], **{c: e[s_][3] for c, s_ in CANDIDATES.items()}),
                           masked={w: bool(base[w] <= 0 or e_round[w] > base[w] * 10 ** (-20 / 10)) for w in CF.WINDOWS})
                for cand, stage in CANDIDATES.items():
                    row[cand] = {w: dict(energy=e[stage][0][w],
                                         change_db=(10 * np.log10(e[stage][0][w] / base[w])) if e[stage][0][w] > 0 and base[w] > 0 else None)
                                 for w in CF.WINDOWS}
                    row[cand + '_attack_change_db'] = S.db(e[stage][1], e[0][1])
                cases.append(row)
                print(shape, model, level, ' '.join(
                    f"{c}: early {(row[c]['early']['change_db'] or 0):+.1f} late {(row[c]['late']['change_db'] or 0):+.1f} "
                    f"atk {row[c + '_attack_change_db']:+.2f}" for c in CANDIDATES), flush=True)
    own_budget = CF.attack_budget(cases, list(CANDIDATES), a.cohort)
    budget_rows += [b for b in own_budget if b['cohort'] in CF.BUDGET_COHORTS]
    summary = CF.verdicts(cases, list(CANDIDATES), budget_rows)
    secondary = CF.verdicts([c for c in cases if c['impact_peak_dbfs'] == -6], list(CANDIDATES), budget_rows)
    for s in summary:
        print('VERDICT', s['model'], s['type'], s['oracle'], s['window'], s['verdict'], f"(raw {s['raw_verdict']})",
              'G', None if s['G_db'] is None else round(s['G_db'], 2), 'L', None if s['L_db'] is None else round(s['L_db'], 2),
              f"red {s['reducing_waveforms']}/{s['valid_waveforms']} need {s['needed']} excl {s['excluded_settings']}", flush=True)
    decisions = decide(summary, note_rows + imported_notes)
    for d in decisions:
        print('DECISION', json.dumps(d), flush=True)
    direct = direct_vs_p1(cases)
    direct_verdicts = [dict(v, verdict=None) for v in CF.verdicts(direct, list(DIRECT), [])]  # descriptive: raw only
    for s in direct_verdicts:
        if (s['type'], s['window']) == ('kick', 'late'):
            print('DIRECT', s['model'], s['oracle'], s['raw_verdict'], 'G', None if s['G_db'] is None else round(s['G_db'], 2),
                  'L', None if s['L_db'] is None else round(s['L_db'], 2), f"red {s['reducing_waveforms']}/{s['valid_waveforms']}", flush=True)
    gr = [v for c in cases for d_ in c['limiter_gr_db'].values() for v in d_.values()]
    print('LIMITER', 'min', min(gr), 'max', max(gr), flush=True)
    for b_ in own_budget:
        print('BUDGET', b_['model'], b_['type'], 'within' if b_['within'] else 'OVER', round(b_['median_db'], 3),
              round(b_['worst_setting_db'], 3), flush=True)
    result = dict(schema='rootnote.study2.candidate.v2', issue=4, cohort=a.cohort, checkout=ident,
                  frozen=a.frozen or None, frozen_sha=a.frozen_sha or None, confirmation_opened=a.cohort == 'confirm',
                  candidates=CANDIDATES, models=[dict(name=m, flags=f, impact_mode=i) for m, f, i in MODELS],
                  levels=list(levels), out_db=OUT_DB, source_sha256=S.source_hashes(),
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  budget=dict(sources=budget_sources), attack_budget=own_budget, decisions=decisions, verdicts=summary,
                  secondary_minus6_verdicts=secondary, direct_vs_p1_verdicts=direct_verdicts,
                  notes=note_rows, imported_notes=imported_notes, cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
