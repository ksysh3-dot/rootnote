#!/usr/bin/env python3
"""Study 1 phase B (#4), development cohort: counterfactual stage replacement.

For each case the mixture is rendered again with one stage's non-additive part removed and the generated-layer
error E (phase A definition, I = stem(x) - stem(bed) - stem(impact)) is compared with the unmodified mixture.
  B1  selected HPSS outputs (bh, bp) := bed + impact values, from 150 ms before the impact to the end
  B2  envelope targets (as, ps) := bed-only values, from the point where the impact-only render's own envelope
      target has fallen below 10 % of its peak (the impact's own amplitude is over) to the end
  B12 both
B3 (track acceptance) is not implemented yet. Before any counterfactual, self-injection (the mixture's own values)
must reproduce the mixture bit for bit; otherwise the run stops. The confirmation seed is not opened here.
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


def err(rx, rb, ri, n, t, onset, duration, e):
    y = S.aligned(rx, n, 'stem') - S.aligned(rb, n, 'stem') - S.aligned(ri, n, 'stem')
    w = S.windows(t, onset, duration)
    return {k: S.energy(y[m]) for k, m in w.items()}


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
                # integrity: the mixture's own values, both masks, whole render
                if len(integrity) < 4 or level == S.LEVELS[0]:
                    rs = injected(lib, x, flags, mode, 3, cx['selected_h'], cx['selected_p'], (0, nx),
                                  (cx['env_a'], cx['env_p']), (0, nx))
                    same = bool(np.array_equal(rs['stem'], rx['stem']) and np.array_equal(rs['output'], rx['output']))
                    integrity.append(dict(shape=shape, model=model, level=level, bit_identical=same))
                    if not same:
                        raise SystemExit(f'self-injection changed the output ({shape} {model} {level}); phase B stops')
                h0 = max(0, int(round((onset - .15) * CORE)))
                add_h = cb['selected_h'][:m] + ci['selected_h'][:m]
                add_p = cb['selected_p'][:m] + ci['selected_p'][:m]
                ea = ci['env_a'][:m]; k0 = int(round(onset * CORE)); kp = k0 + int(np.argmax(ea[k0:]))
                below = np.where(ea[kp:] < .1 * ea[kp])[0]
                e0 = kp + int(below[0]) if len(below) else m
                env_bed = (cb['env_a'][:m], cb['env_p'][:m])
                e_base = err(rx, rb, ri, n, t, onset, duration, S.energy(impact))
                variants = dict(
                    B1=injected(lib, x, flags, mode, 1, add_h, add_p, (h0, m)),
                    B2=injected(lib, x, flags, mode, 2, env=env_bed, e=(e0, m)),
                    B12=injected(lib, x, flags, mode, 3, add_h, add_p, (h0, m), env_bed, (e0, m)))
                row = dict(shape=shape, model=model, impact_peak_dbfs=level,
                           b2_start_ms_after_onset=float((e0 / CORE - onset) * 1000),
                           base_db_per_input={k: S.db(v, S.energy(impact)) for k, v in e_base.items()})
                for name, rv in variants.items():
                    ev = err(rv, rb, ri, n, t, onset, duration, S.energy(impact))
                    row[name] = {k: dict(db_per_input=S.db(ev[k], S.energy(impact)),
                                         change_db=S.db(ev[k], e_base[k]),
                                         reduction=float(1 - ev[k] / e_base[k]) if e_base[k] > 0 else None)
                                 for k in ev}
                cases.append(row)
                print(shape, model, level, 'b2@', round(row['b2_start_ms_after_onset']), 'ms',
                      ' '.join(f"{v}:{row[v]['early']['change_db']:+.1f}/{row[v]['late']['change_db']:+.1f}"
                               for v in variants), flush=True)
    result = dict(schema='rootnote.study1.phaseB.v1', issue=4, cohort='development', confirmation_opened=False,
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  integrity=integrity, b3='not implemented',
                  definition='change_db = E(variant)/E(mixture) per window; reduction = 1 - that ratio',
                  cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
