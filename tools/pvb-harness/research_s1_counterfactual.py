#!/usr/bin/env python3
"""Study 1 phase B (#4): counterfactual oracle comparison (development cohort unless --cohort confirm).

For each case the mixture is rendered again with stages replaced by oracles and the non-additive interaction
energy E (phase A definition, I = stem(x) - stem(bed) - stem(impact); early/late windows start at the impact's end)
is compared with the unmodified mixture.
  B1  additive oracle: selected HPSS outputs (bh, bp) := bed + impact values, from 150 ms before the onset
  B2  bed-only oracle for the envelope targets (as, ps) from the point where the impact-only envelope target has
      fallen below 10 % of its peak (start rule frozen as env10: env10/env50/aligned gave identical results)
  B3  bed-only oracle for track acceptance: from the onset to 80 ms after the impact's end, each mixture track
      within 3 % of a track of the bed-only render takes that track's recorded state; taped tracks without a
      counterpart are added; every other (impact) track is kept
All seven combinations (leave-one-out / leave-one-in) are rendered. Integrity: self-injection and a self-recorded
track tape must reproduce the mixture bit for bit, otherwise the run stops. B3 preconditions are reported per case:
the correspondence counts (replaced/added/kept), state consistency (duplicate ids, overflow) and normal-impact
preservation (the same B3 applied to the impact-only render must change its generated layer by <= -20 dB).
A replaced track keeps the mixture's id; an added bed track gets a marked id. Windows whose input-rounding
sensitivity R exceeds E - 20 dB (decided once on the unmodified mixture) are excluded from the verdicts.
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
HOP = 16
DP = C.POINTER(C.c_double)
COL = {k: COLUMNS.index(k) for k in ('selected_h', 'selected_p', 'env_a', 'env_p')}
WINDOWS = ('early', 'late')
COMBOS = {'B1': (1, 0, 0), 'B2': (0, 1, 0), 'B3': (0, 0, 1), 'B12': (1, 1, 0), 'B13': (1, 0, 1), 'B23': (0, 1, 1),
          'B123': (1, 1, 1)}


def bind(lib):
    lib.pvb_set_stage_inject.argtypes = [C.c_void_p, C.c_uint, DP, DP, C.c_longlong, C.c_longlong,
                                         DP, DP, C.c_longlong, C.c_longlong, C.c_longlong]
    lib.pvb_set_stage_inject.restype = C.c_int
    lib.pvb_track_tape_create.argtypes = [C.c_int]; lib.pvb_track_tape_create.restype = C.c_void_p
    lib.pvb_track_tape_destroy.argtypes = [C.c_void_p]
    lib.pvb_set_track_tape.argtypes = [C.c_void_p, C.c_void_p, C.c_int, C.c_longlong, C.c_longlong, C.c_double]
    lib.pvb_set_track_tape.restype = C.c_int
    lib.pvb_track_tape_stats.argtypes = [C.c_void_p, C.POINTER(C.c_longlong), C.c_int]
    lib.pvb_track_tape_stats.restype = C.c_int


class Tape:
    def __init__(self, lib, n_samples):
        self.lib = lib; self.h = lib.pvb_track_tape_create(n_samples // (FS // CORE) // HOP + 64)
        assert self.h, 'tape create failed'

    def stats(self):
        out = (C.c_longlong * 7)()
        assert self.lib.pvb_track_tape_stats(self.h, out, 7) == 7
        return dict(zip(('recorded', 'replaced', 'added', 'kept', 'dup_ids', 'overflow', 'window_hops'), out))

    def close(self):
        if self.h: self.lib.pvb_track_tape_destroy(self.h); self.h = None


def columns(r):
    s = r['stages']
    idx = (s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32))
    out = {}
    for k, c in COL.items():
        a = np.zeros(int(idx.max()) + 1); a[idx] = s[:, c]; out[k] = a
    return out, int(idx.max()) + 1


def render(lib, x, flags, mode, mask=0, bh=None, bp=None, h=(0, 0), env=None, e=(0, 0), tape=None):
    """tape = (Tape, mode 1 record / 2 replay, start hop, end hop)"""
    keep = []

    def ptr(a):
        if a is None: return None
        a = np.ascontiguousarray(a, np.float64); keep.append(a); return a.ctypes.data_as(DP)

    def hook(lib_, handle):
        if mask:
            n = max(len(v) for v in (bh, env[0] if env else None) if v is not None)
            assert lib_.pvb_set_stage_inject(handle, mask, ptr(bh), ptr(bp), h[0], h[1], ptr(env[0] if env else None),
                                             ptr(env[1] if env else None), e[0], e[1], n) == 1, 'inject refused'
        if tape:
            assert lib_.pvb_set_track_tape(handle, tape[0].h, tape[1], tape[2], tape[3], .03) == 1, 'tape refused'
    return P.render(lib, x, FS, flags, impact_mode=mode, before_process=hook if (mask or tape) else None)


def window_energy(y, t, onset, duration, names=WINDOWS):
    return {k: S.energy(y[m]) for k, m in S.windows(t, onset, duration).items() if k in names}


def b2_start(ea, onset):
    k0 = int(round(onset * CORE)); kp = k0 + int(np.argmax(ea[k0:])); peak = ea[kp]
    if peak <= 0: return len(ea)
    below = np.where(ea[kp:] < .1 * peak)[0]
    return kp + int(below[0]) if len(below) else len(ea)


def verdicts(cases, variants):
    """Pre-registration v2: per oracle x model x window x type, waveform values = median over levels of the dB
    change (rounding-masked windows, invalid B3 cases and non-finite values left out); G = median waveform
    reduction, L = largest waveform worsening; near-adoption if G >= 3, reducing waveforms >= 2/3 and L <= G/2,
    hold-option if L > G/2."""
    out = []
    for model in sorted({c['model'] for c in cases}):
        for kind in ('kick', 'noise'):
            sub = [c for c in cases if c['model'] == model and kind in c['shape']]
            shapes = sorted({c['shape'] for c in sub})
            need = int(np.ceil(len(shapes) * 2 / 3))
            for v in variants:
                for w in WINDOWS:
                    per, excluded, worst = [], 0, None
                    for s in shapes:
                        vals = []
                        for c in sub:
                            if c['shape'] != s: continue
                            ch = c[v][w]['change_db']
                            bad = c['masked'][w] or ch is None or not np.isfinite(ch) or \
                                  ('3' in v and not c['b3_valid'])
                            if bad: excluded += 1; continue
                            vals.append(ch); worst = ch if worst is None else max(worst, ch)
                        if vals: per.append(float(np.median(vals)))
                    if len(per) < need:
                        verdict, G, L, red = 'not_established(insufficient)', None, None, None
                    else:
                        G = float(np.median([-p for p in per])); red = sum(p < 0 for p in per)
                        L = max([p for p in per if p > 0], default=0.0)
                        verdict = ('near_adoption' if L <= G / 2 else 'hold_option') if G >= 3 and red >= need \
                            else 'not_established'
                    out.append(dict(model=model, type=kind, oracle=v, window=w, waveforms=len(shapes),
                                    valid_waveforms=len(per), excluded_settings=excluded, G_db=G, L_db=L,
                                    reducing_waveforms=red, needed=need, worst_setting_db=worst, verdict=verdict))
    return out


CONFIRM_SEED = 2026102801


def confirm_fixtures(fs=FS, seed=CONFIRM_SEED):
    """Confirmation cohort (#4 v2): the fresh_fixtures generator rule with a new seed, 8 kicks + 4 broadband."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(seed); t = np.arange(round(3.2 * fs)) / fs; onset = 1.25; u = t - onset
    for j in range(12):
        duration = float(rng.uniform(.08, .22) if j < 8 else rng.uniform(.02, .08))
        active = (u >= 0) & (u < duration); z = np.zeros_like(t)
        if j < 8:
            end = float(rng.uniform(41, 70)); jump = float(rng.uniform(65, 155))
            tau = float(rng.uniform(.015, .035)); decay = float(rng.uniform(.02, .06))
            ph = 2 * np.pi * (end * u + jump * tau * (1 - np.exp(-np.maximum(u, 0) / tau)))
            env = (1 - np.exp(-np.maximum(u, 0) / .001)) * np.exp(-np.maximum(u, 0) / decay)
            env *= np.minimum(1, np.maximum(0, (duration - u) / .01))
            z[active] = env[active] * np.cos(ph[active])
            z[active] += .12 * rng.normal(size=len(t))[active] * np.exp(-u[active] / .004)
            kind = 'kick'
        else:
            noise = sosfilt(butter(2, [30, 4000], btype='bandpass', fs=fs, output='sos'), rng.normal(size=len(t)))
            z[active] = noise[active] * np.sin(np.pi * u[active] / duration) ** 2; kind = 'noise'
        z /= np.max(abs(z)); bf = float(rng.uniform(43, 103)); phase = float(rng.uniform(-np.pi, np.pi))
        b = .018 * np.cos(2 * np.pi * bf * t + phase) * np.minimum(1, t / .05)
        yield f'confirm_{kind}_{j}', True, t, b, z, onset, duration


def preserve_fixtures(fs=FS):
    """Preservation cohort (#4 v2): R01 regression fixtures with a bed that truly ends at the kick, or travels."""
    from research_p1pp_recovery import new_fixtures
    inspected = {x[0]: x for x in new_fixtures(fs, seed=2026102609, count=12)}
    for name in ('new_kick_2', 'new_kick_3', 'new_broadband_7'):
        _, _, t, bed, z, onset, duration, desc = inspected[name]
        kind = 'noise' if 'broadband' in name else 'kick'
        yield f'preserve_{kind}_{name}_ends', True, t, bed * np.clip((onset + .01 - t) / .01, 0, 1), z, onset, duration
        yield (f'preserve_{kind}_{name}_travels', True, t,
               .018 * np.minimum(1, t / .05) * np.cos(2 * np.pi * (65 * t + 6 * t * t) + desc['bed_phase']), z, onset,
               duration)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--cohort', choices=('development', 'preserve', 'confirm'), default='development')
    p.add_argument('--frozen', default='', help='must name the frozen pre-registration (e.g. v2-final) to run confirm')
    p.add_argument('--with-b3', action='store_true', help='also render B3 combinations (excluded from #4 verdicts)')
    a = p.parse_args()
    if a.cohort == 'confirm' and not a.frozen:
        raise SystemExit('the confirmation cohort opens only after the pre-registration is frozen (--frozen <tag>)')
    lib = P.api(a.library.resolve()); bind(lib)
    if a.cohort == 'development':
        fixtures = [f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS)); levels = S.LEVELS
    elif a.cohort == 'preserve':
        fixtures = list(preserve_fixtures()); levels = (-12, -6)
    else:
        fixtures = list(confirm_fixtures()); levels = (-12, -6)
    combos = {k: v for k, v in COMBOS.items() if a.with_b3 or not v[2]}
    pad = np.zeros(FS // 2)
    cases, integrity = [], []
    for shape, _bed, t, b, z, onset, duration in fixtures:
        n = len(t); xb = np.r_[b, pad]
        for model, flags, mode in S.MODELS:
            tape_bed = Tape(lib, len(xb))
            rb = render(lib, xb, flags, mode, tape=(tape_bed, 1, 0, 0))
            cb, nb = columns(rb)
            for level in levels:
                impact = z * 10 ** (level / 20); x = np.r_[b + impact, pad]
                rx = render(lib, x, flags, mode)
                ri = render(lib, np.r_[impact, pad], flags, mode)
                cx, nx = columns(rx); ci, ni = columns(ri)
                m = min(nb, nx, ni)
                if len(integrity) < 4 or level == S.LEVELS[0]:
                    rs = render(lib, x, flags, mode, 3, cx['selected_h'], cx['selected_p'], (0, nx),
                                (cx['env_a'], cx['env_p']), (0, nx))
                    tape_self = Tape(lib, len(x))
                    render(lib, x, flags, mode, tape=(tape_self, 1, 0, 0))
                    rt = render(lib, x, flags, mode, tape=(tape_self, 2, 0, 1 << 40))
                    tape_self.close()
                    same = bool(np.array_equal(rs['stem'], rx['stem']) and np.array_equal(rs['output'], rx['output']))
                    same_tape = bool(np.array_equal(rt['stem'], rx['stem']) and np.array_equal(rt['output'], rx['output']))
                    integrity.append(dict(shape=shape, model=model, level=level, inject_bit_identical=same,
                                          tape_bit_identical=same_tape))
                    if not (same and same_tape):
                        raise SystemExit(f'self-injection/tape changed the output ({shape} {model} {level}); phase B stops')
                base_inter = S.aligned(rx, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                e_base = window_energy(base_inter, t, onset, duration)
                x32 = (b.astype(np.float32) + impact.astype(np.float32)).astype(np.float64)
                rr = render(lib, np.r_[x32, pad], flags, mode)
                e_round = window_energy(S.aligned(rx, n, 'stem') - S.aligned(rr, n, 'stem'), t, onset, duration)
                masked = {w: bool(e_base[w] <= 0 or e_round[w] > e_base[w] * 10 ** (-20 / 10)) for w in WINDOWS}
                h0 = max(0, int(round((onset - .15) * CORE)))
                add_h = cb['selected_h'][:m] + ci['selected_h'][:m]
                add_p = cb['selected_p'][:m] + ci['selected_p'][:m]
                env_bed = (cb['env_a'][:m], cb['env_p'][:m])
                e0 = b2_start(ci['env_a'][:m], onset)
                hop_window = (int(onset * CORE) // HOP, int(np.ceil((onset + duration + .08) * CORE / HOP)))
                row = dict(shape=shape, model=model, impact_peak_dbfs=level, masked=masked,
                           b2_start_ms_after_onset=float((e0 / CORE - onset) * 1000), b3_hops=hop_window,
                           base_energy=e_base, rounding_energy=e_round,
                           base_db_per_input={k: S.db(v, S.energy(impact)) for k, v in e_base.items()})
                attack_mix = window_energy(S.aligned(rx, n, 'stem'), t, onset, duration, ('attack',))['attack']
                for name, (u1, u2, u3) in combos.items():
                    mask = (1 if u1 else 0) | (2 if u2 else 0)
                    tape = (tape_bed, 2, *hop_window) if u3 else None
                    if u3:
                        before = tape_bed.stats()
                    rv = render(lib, x, flags, mode, mask, add_h if u1 else None, add_p if u1 else None, (h0, m),
                                env_bed if u2 else None, (e0, m), tape)
                    y = S.aligned(rv, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
                    ev = window_energy(y, t, onset, duration)
                    row[name + '_attack_change_db'] = S.db(window_energy(S.aligned(rv, n, 'stem'), t, onset, duration,
                                                                         ('attack',))['attack'], attack_mix)
                    row[name] = {k: dict(energy=ev[k],
                                         change_db=(10 * np.log10(ev[k] / e_base[k])) if ev[k] > 0 and e_base[k] > 0 else None,
                                         reduction=float(1 - ev[k] / e_base[k]) if e_base[k] > 0 else None)
                                 for k in WINDOWS}
                    if name == 'B3':
                        after = tape_bed.stats()
                        d = {k: after[k] - before[k] for k in ('replaced', 'added', 'kept', 'dup_ids', 'overflow',
                                                               'window_hops')}
                        att = window_energy(S.aligned(rv, n, 'stem'), t, onset, duration, ('attack',))['attack']
                        d['attack_generated_change_db'] = S.db(att, attack_mix)
                        # normal-impact preservation (pre-registration v2): the same B3 on the impact-only render
                        # must leave its generated layer (attack + 80 ms) essentially unchanged
                        rc = render(lib, np.r_[impact, pad], flags, mode, tape=(tape_bed, 2, *hop_window))
                        seg = S.windows(t, onset, duration); keep_m = seg['attack'] | seg['early']
                        yi = S.aligned(ri, n, 'stem'); yc = S.aligned(rc, n, 'stem')
                        d['impact_only_change_db'] = S.db(S.energy((yc - yi)[keep_m]), S.energy(yi[keep_m]))
                        after2 = tape_bed.stats()
                        d['impact_only_replaced'] = after2['replaced'] - after['replaced']
                        row['b3_preconditions'] = d
                        row['b3_valid'] = bool(d['dup_ids'] == 0 and d['overflow'] == 0 and d['window_hops'] > 0
                                               and d['impact_only_change_db'] <= -20)
                import test_engine as T
                row['limiter_gr_db'] = {k: float(r['meters'][T.M['LIM_GR_DB']]) for k, r in (('mixture', rx), ('bed', rb), ('impact', ri))}
                if a.cohort != 'development':
                    row['limiter_gr_db_out3'] = {k: float(P.render(lib, v, FS, flags, impact_mode=mode, out_db=-3)['meters'][T.M['LIM_GR_DB']])
                                                 for k, v in (('mixture', x), ('bed', xb), ('impact', np.r_[impact, pad]))}
                cases.append(row)
                pc = row.get('b3_preconditions')
                print(shape, model, level, '' if pc is None else f"B3 dup {pc['dup_ids']} impOnly {pc['impact_only_change_db']:+.1f} valid {row['b3_valid']}",
                      ' '.join(f"{v}:{(row[v]['early']['change_db'] or 0):+.1f}/{(row[v]['late']['change_db'] or 0):+.1f}"
                               for v in combos), flush=True)
            tape_bed.close()
    summary = verdicts(cases, list(combos))
    secondary = verdicts([c for c in cases if c['impact_peak_dbfs'] == -6], list(combos))  # pre-registered subgroup
    for s in summary:
        print('VERDICT', s['model'], s['type'], s['oracle'], s['window'], s['verdict'],
              'G', None if s['G_db'] is None else round(s['G_db'], 2), 'L', None if s['L_db'] is None else round(s['L_db'], 2),
              f"red {s['reducing_waveforms']}/{s['valid_waveforms']} need {s['needed']} excl {s['excluded_settings']}",
              flush=True)
    result = dict(schema='rootnote.study1.phaseB.v4', issue=4, cohort=a.cohort, frozen=a.frozen or None,
                  confirmation_opened=a.cohort == 'confirm', levels=list(levels), oracles=list(combos),
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  source_sha256=S.source_hashes(), integrity=integrity,
                  definition='change_db = 10 log10(E(variant)/E(mixture)) per window, raw energies kept; '
                             'verdicts per pre-registration v2 (G/L, waveform medians over levels, rounding mask)',
                  verdicts=summary, secondary_minus6_verdicts=secondary, cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
