#!/usr/bin/env python3
"""Study 2 development: when does the kick late cut happen? A grid over the bed frequency and the kick's end frequency.

The kick uses the fresh_fixtures/confirm_fixtures kick rule with fixed parameters (duration 0.15 s, jump 110 Hz,
tau 0.025 s, decay 0.04 s, no noise burst); the bed is a 0.018 cosine. Grid: kick end frequency 41-70 Hz x bed
frequency 43-103 Hz, impact -12/-6 dBFS, P1+ (flags 6). Per point: kick late E change of C1 against the unmodified
model, and the share of the late window where the unmodified gain is below 1. Deterministic grid, no confirmation seed.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import research_p1plus as P
import research_s1_counterfactual as CF
import research_s1_interaction as S
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS, CORE = S.FS, S.CORE
GAIN = COLUMNS.index('applied_gain')


def kick(t, onset, end, duration=.15, jump=110., tau=.025, decay=.04):
    u = t - onset; z = np.zeros_like(t); active = (u >= 0) & (u < duration)
    ph = 2 * np.pi * (end * u + jump * tau * (1 - np.exp(-np.maximum(u, 0) / tau)))
    env = (1 - np.exp(-np.maximum(u, 0) / .001)) * np.exp(-np.maximum(u, 0) / decay)
    env *= np.minimum(1, np.maximum(0, (duration - u) / .01))
    z[active] = env[active] * np.cos(ph[active])
    return z / np.max(np.abs(z)), duration


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve())
    t = np.arange(round(3.2 * FS)) / FS; onset = 1.25; pad = np.zeros(FS // 2); n = len(t); rows = []
    for end in (41, 48, 55, 62, 70):
        z, duration = kick(t, onset, end)
        for bf in range(43, 104, 6):
            b = .018 * np.cos(2 * np.pi * bf * t) * np.minimum(1, t / .05)
            rb = {s: P.render(lib, np.r_[b, pad], FS, 6, stage_flags=s) for s in (0, 8192)}
            for level in (-12, -6):
                impact = z * 10 ** (level / 20); e = {}; dip = None
                for s in (0, 8192):
                    rx = P.render(lib, np.r_[b + impact, pad], FS, 6, stage_flags=s)
                    ri = P.render(lib, np.r_[impact, pad], FS, 6, stage_flags=s)
                    inter = S.aligned(rx, n, 'stem') - S.aligned(rb[s], n, 'stem') - S.aligned(ri, n, 'stem')
                    e[s] = CF.window_energy(inter, t, onset, duration)['late']
                    if s == 0:
                        st = rx['stages']; idx = st[:, 0].astype(np.int64)
                        k0, k1 = int((onset + duration + .08) * CORE), int((onset + duration + .5) * CORE)
                        m = (idx >= k0) & (idx < k1); dip = float(np.mean(st[m, GAIN] < 1 - 1e-9))
                change = 10 * np.log10(e[8192] / e[0]) if e[0] > 0 and e[8192] > 0 else None
                rows.append(dict(kick_end_hz=end, bed_hz=bf, distance_hz=bf - end, level=level, late_base=e[0],
                                 c1_late_change_db=change, base_gain_below_one=dip))
                print(f'end {end} bed {bf} d {bf - end:+d} lvl {level} dip {dip:.2f} C1 late',
                      'NA' if change is None else f'{change:+.1f}', flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study2.sweep.v1', model='p1plus', rows=rows), indent=2) + '\n',
                        encoding='utf-8')


if __name__ == '__main__':
    main()
