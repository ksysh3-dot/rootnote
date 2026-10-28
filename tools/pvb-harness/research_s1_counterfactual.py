#!/usr/bin/env python3
"""Study 1 phase B (#4), development cohort: counterfactual oracle comparison.

For each case the mixture is rendered again with one stage replaced by an oracle and the non-additive interaction
energy E (phase A definition, I = stem(x) - stem(bed) - stem(impact); early/late windows start at the impact's end)
is compared with the unmodified mixture.
  B1   additive oracle: selected HPSS outputs (bh, bp) := bed + impact values, from 150 ms before the onset
  B2*  bed-only oracle for the envelope targets (as, ps) from a start point; three start rules are compared on the
       development cohort (one is frozen before the confirmation run):
         env10    the impact-only envelope target has fallen below 10 % of its peak (phase B v1 rule)
         env50    ... below 50 % of its peak
         aligned  the impact's end shifted by the envelope stage's own arrival lag (first rise of the impact-only
                  envelope target above 1 % of its peak after the onset)
  B12* B1 together with B2*
B3 (track acceptance) is not implemented yet. Self-injection (the mixture's own values) must reproduce the mixture
bit for bit; otherwise the run stops. Windows whose input-rounding sensitivity R exceeds E - 20 dB (decided once on
the unmodified mixture) are excluded from the verdicts. The confirmation seed is not opened here.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
import research_p1pp_impacts as I
import research_p1plus as P
import research_s1_interaction as S
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS, CORE = S.FS, S.CORE
DP = C.POINTER(C.c_double)
COL = {k: COLUMNS.index(k) for k in ('selected_h', 'selected_p', 'env_a', 'env_p')}
B2_RULES = ('env10', 'env50', 'aligned')
WINDOWS = ('early', 'late')


def bind(lib):
    lib.pvb_set_stage_inject.argtypes = [C.c_void_p, C.c_uint, DP, DP, C.c_longlong, C.c_longlong,
                                         DP, DP, C.c_longlong, C.c_longlong, C.c_longlong]
    lib.pvb_set_stage_inject.restype = C.c_int


def columns(r):
    """Stage columns as full arrays indexed by core sample."""
    s = r['stages']
    idx = (s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32))
    n = int(idx.max()) + 1
    out = {}
    for k, c in COL.items():
        a = np.zeros(n); a[idx] = s[:, c]; out[k] = a
    return out, n


def injected(lib, x, flags, mode, mask, bh=None, bp=None, h=(0, 0), env=None, e=(0, 0)):
    keep = []  # host buffers must outlive processing

    def ptr(a):
        if a is None: return None
        a = np.ascontiguousarray(a, np.float64); keep.append(a); return a.ctypes.data_as(DP)

    def hook(lib_, handle):
        n = max(len(v) for v in (bh, env[0] if env else None) if v is not None)
        ok = lib_.pvb_set_stage_inject(handle, mask, ptr(bh), ptr(bp), h[0], h[1],
                                       ptr(env[0] if env else None), ptr(env[1] if env else None), e[0], e[1], n)
        assert ok == 1, 'inject refused'
    return P.render(lib, x, FS, flags, impact_mode=mode, before_process=hook)


def window_energy(y, t, onset, duration):
    return {k: S.energy(y[m]) for k, m in S.windows(t, onset, duration).items() if k in WINDOWS}


def b2_start(ea, onset, rule, end_core):
    k0 = int(round(onset * CORE)); kp = k0 + int(np.argmax(ea[k0:])); peak = ea[kp]
    if peak <= 0: return len(ea)
    if rule in ('env10', 'env50'):
        below = np.where(ea[kp:] < (.1 if rule == 'env10' else .5) * peak)[0]
        return kp + int(below[0]) if len(below) else len(ea)
    rise = np.where(ea[k0:] > .01 * peak)[0]
    lag = int(rise[0]) if len(rise) else 0
    return min(len(ea), end_core + lag)


def verdicts(cases, variants):
    """Pre-registration v2: per oracle x model x window x type, waveform values = median over levels of the dB
    change (rounding-masked windows and non-finite values left out); G = median waveform reduction, L = largest
    waveform worsening; near-adoption if G >= 3, reducing waveforms >= 2/3 and L <= G/2."""
    out = []
    for model in sorted({c['model'] for c in cases}):
        for kind in ('kick', 'noise'):
            sub = [c for c in cases if c['model'] == model and kind in c['shape']]
            shapes = sorted({c['shape'] for c in sub})
            need = int(np.ceil(len(shapes) * 2 / 3))
            for v in variants:
                for w in WINDOWS:
                    per, excluded, worst_setting = [], 0, None
                    for s in shapes:
                        vals = []
                        for c in sub:
                            if c['shape'] != s: continue
                            ch = c[v][w]['change_db']
                            if c['masked'][w] or ch is None or not np.isfinite(ch): excluded += 1; continue
                            vals.append(ch)
                            worst_setting = ch if worst_setting is None else max(worst_setting, ch)
                        if vals: per.append(float(np.median(vals)))
                    if len(per) < need:
                        verdict, G, L, red = 'not_established(insufficient)', None, None, None
                    else:
                        G = float(np.median([-p for p in per])); red = sum(p < 0 for p in per)
                        L = max([p for p in per if p > 0], default=0.0)
                        if G >= 3 and red >= need:
                            verdict = 'near_adoption' if L <= G / 2 else 'hold_option'
                        else:
                            verdict = 'not_established'
                    out.append(dict(model=model, type=kind, oracle=v, window=w, waveforms=len(shapes),
                                    valid_waveforms=len(per), excluded_settings=excluded, G_db=G, L_db=L,
                                    reducing_waveforms=red, needed=need, worst_setting_db=worst_setting,
                                    verdict=verdict))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); bind(lib)
    fixtures = [f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS))
    pad = np.zeros(FS // 2)
    cases, integrity = [], []
    for shape, _bed, t, b, z, onset, duration in fixtures:
        n = len(t)
        for model, flags, mode in S.MODELS:
            rb = P.render(lib, np.r_[b, pad], FS, flags, impact_mode=mode)
            cb, nb = columns(rb)
            for level in S.LEVELS:
                impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]
                rx = P.render(lib, x, FS, flags, impact_mode=mode)
                ri = P.render(lib, np.r_[impact, pad], FS, flags, impact_mode=mode)
                cx, nx = columns(rx); ci, ni = columns(ri)
                m = min(nb, nx, ni)
                if len(integrity) < 4 or level == S.LEVELS[0]:
                    rs = injected(lib, x, flags, mode, 3, cx['selected_h'], cx['selected_p'], (0, nx),
                                  (cx['env_a'], cx['env_p']), (0, nx))
                    same = bool(np.array_equal(rs['stem'], rx['stem']) and np.array_equal(rs['output'], rx['output']))
                    integrity.append(dict(shape=shape, model=model, level=level, bit_identical=same))
                    if not same:
                        raise SystemExit(f'self-injection changed the output ({shape} {model} {level}); phase B stops')
                base_inter = S.aligned(rx, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                e_base = window_energy(base_inter, t, onset, duration)
                # rounding mask, decided once on the unmodified mixture
                x32 = (b.astype(np.float32) + impact.astype(np.float32)).astype(np.float64)
                rr = P.render(lib, np.r_[x32, pad], FS, flags, impact_mode=mode)
                e_round = window_energy(S.aligned(rx, n, 'stem') - S.aligned(rr, n, 'stem'), t, onset, duration)
                masked = {w: bool(e_base[w] <= 0 or e_round[w] > e_base[w] * 10 ** (-20 / 10)) for w in WINDOWS}
                h0 = max(0, int(round((onset - .15) * CORE)))
                add_h = cb['selected_h'][:m] + ci['selected_h'][:m]
                add_p = cb['selected_p'][:m] + ci['selected_p'][:m]
                env_bed = (cb['env_a'][:m], cb['env_p'][:m])
                end_core = int(round((onset + duration) * CORE))
                starts = {r: b2_start(ci['env_a'][:m], onset, r, end_core) for r in B2_RULES}
                renders = {'B1': injected(lib, x, flags, mode, 1, add_h, add_p, (h0, m))}
                for r, e0 in starts.items():
                    renders['B2_' + r] = injected(lib, x, flags, mode, 2, env=env_bed, e=(e0, m))
                    renders['B12_' + r] = injected(lib, x, flags, mode, 3, add_h, add_p, (h0, m), env_bed, (e0, m))
                row = dict(shape=shape, model=model, impact_peak_dbfs=level, masked=masked,
                           b2_start_ms_after_onset={r: float((e0 / CORE - onset) * 1000) for r, e0 in starts.items()},
                           base_energy=e_base, rounding_energy=e_round,
                           base_db_per_input={k: S.db(v, S.energy(impact)) for k, v in e_base.items()})
                for name, rv in renders.items():
                    y = S.aligned(rv, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                    ev = window_energy(y, t, onset, duration)
                    row[name] = {k: dict(energy=ev[k],
                                         change_db=(10 * np.log10(ev[k] / e_base[k])) if ev[k] > 0 and e_base[k] > 0 else None,
                                         reduction=float(1 - ev[k] / e_base[k]) if e_base[k] > 0 else None)
                                 for k in WINDOWS}
                cases.append(row)
                print(shape, model, level, 'b2@', {r: round(v) for r, v in row['b2_start_ms_after_onset'].items()},
                      ' '.join(f"{v}:{(row[v]['late']['change_db'] or 0):+.1f}" for v in renders), flush=True)
    variants = ['B1'] + [p + r for r in B2_RULES for p in ('B2_', 'B12_')]
    summary = verdicts(cases, variants)
    for s in summary:
        print('VERDICT', s['model'], s['type'], s['oracle'], s['window'], s['verdict'],
              'G', None if s['G_db'] is None else round(s['G_db'], 2), 'L', None if s['L_db'] is None else round(s['L_db'], 2),
              f"red {s['reducing_waveforms']}/{s['valid_waveforms']} need {s['needed']} excl {s['excluded_settings']}", flush=True)
    result = dict(schema='rootnote.study1.phaseB.v2', issue=4, cohort='development', confirmation_opened=False,
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  source_sha256=S.source_hashes(), integrity=integrity, b3='not implemented',
                  definition='change_db = 10 log10(E(variant)/E(mixture)) per window, raw energies kept; '
                             'verdicts per pre-registration v2 (G/L, waveform medians over levels, rounding mask)',
                  verdicts=summary, cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
