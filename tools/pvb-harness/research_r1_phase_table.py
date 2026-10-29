#!/usr/bin/env python3
"""Resultant R1 (#4 follow-up): the crest-optimal phase table for unreferenced harmonics.

P1 gives a harmonic that has no partial of its own in the input the fixed offset kPsi = pi k^2 / 6 (a Schroeder
shape for six equal harmonics). The layer's real harmonic magnitudes (table weights times the output filter) and the
output filter's phases differ from that assumption, so the steady layer's crest factor is above the lowest one the
same magnitudes allow (phase 0: +0.3..+2.8 dB at the same peak). Here, per frequency f on the table grid, a pure tone
is rendered by P1 (flags 0), harmonics 2..8 of the layer (stem) are fitted, the phases with the lowest crest factor
for those magnitudes are found, and the table holds the offset change Delta_k(f) that turns the measured phases into
them. The time shift (k alpha) and time reversal that leave the crest factor unchanged are chosen so that Delta stays
closest to the previous grid point (the first point: closest to 0, i.e. to kPsi), and Delta is unwrapped along f.
Writes app/src/main/cpp/libpvb/pvb_vb_r1_tables.h and a JSON report.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
import research_p1plus as P
import research_r0_ceiling as R0
from p1plus_paths import default_library

FS, CORE = 48000, 3000
F0, STEP, F1 = 32., .5, 190.
K = np.arange(2, 9)
HEADER = Path(__file__).resolve().parents[2] / 'app/src/main/cpp/libpvb/pvb_vb_r1_tables.h'


def measure(lib, f):
    t = np.arange(round(2.6 * FS)) / FS
    r = P.render(lib, .12 * np.cos(2 * np.pi * f * t + .3), FS, 0)
    z = resample_poly(r['stem'][FS:round(2.5 * FS), 0].astype(float), 1, 16)
    fe = R0.layer_fundamental(z, CORE, f)
    tt = np.arange(len(z)) / CORE
    design = np.column_stack([v for k in K for v in (np.cos(2 * np.pi * k * fe * tt), np.sin(2 * np.pi * k * fe * tt))])
    coef = np.linalg.lstsq(design, z, rcond=1e-10)[0]
    return coef[0::2] - 1j * coef[1::2], fe


def crest(a, theta, n=1024):
    ph = 2 * np.pi * np.arange(n) / n
    x = (a[:, None] * np.cos(K[:, None] * ph[None, :] + theta[:, None])).sum(0)
    return np.max(np.abs(x)) / np.sqrt(np.mean(x * x))


def descend(a, theta, iters=400, n=256):
    """Clip-and-project over one period with the magnitudes fixed; returns the best phases seen."""
    ph = 2 * np.pi * np.arange(n) / n
    E = np.exp(1j * K[:, None] * ph[None, :])
    best = (crest(a, theta), theta.copy())
    for _ in range(iters):
        x = np.real((a * np.exp(1j * theta)) @ E); rms = np.sqrt(np.mean(x * x)); c = np.max(np.abs(x)) / rms
        level = rms * max(1.02, .93 * c)
        theta = np.angle(E.conj() @ np.clip(x, -level, level))
        cc = crest(a, theta)
        if cc < best[0]: best = (cc, theta.copy())
    return best


def wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


def align(theta, phi, prev, weight):
    """Delta = theta' - phi for the crest-equivalent theta' (k alpha shift, optional reversal) closest to prev."""
    best = None
    for sign in (1, -1):
        for alpha in np.linspace(0, 2 * np.pi, 1440, endpoint=False):
            d = wrap(sign * theta + K * alpha - phi - prev)
            cost = float(np.sum(weight * d * d))
            if best is None or cost < best[0]: best = (cost, prev + d)
    return best[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--header', type=Path, default=HEADER)
    a = p.parse_args()
    lib = P.api(a.library.resolve())
    grid = np.arange(F0, F1 + 1e-9, STEP)
    rng = np.random.default_rng(2026102906)
    rows, delta, theta, prev = [], [], None, np.zeros(7)
    for j, f in enumerate(grid):
        c, fe = measure(lib, f)
        amp, phi = np.abs(c), np.angle(c)
        if amp.max() <= 0:
            delta.append(prev.copy()); rows.append(dict(f=float(f), skipped=True)); continue
        cf_now = crest(amp, phi)
        starts = [] if theta is None else [theta]
        if theta is None or j % 8 == 0: starts += [np.pi * K ** 2 / 6] + [rng.uniform(-np.pi, np.pi, 7) for _ in range(12)]
        results = [descend(amp, s.copy()) for s in starts]
        cont = results[0] if theta is not None else None
        best = min(results, key=lambda q: q[0])
        jumped = cont is not None and best is not cont and 20 * np.log10(cont[0] / best[0]) > .05
        chosen = best if (cont is None or jumped) else cont
        theta = chosen[1]
        weight = (amp / amp.max()) ** 2
        d = align(theta, phi, prev, weight)
        cf_new = crest(amp, phi + d)
        delta.append(d); prev = d
        rows.append(dict(f=float(f), layer_f=float(fe), magnitudes=(amp / amp.max()).tolist(), crest_now=float(cf_now),
                         crest_table=float(cf_new), gain_db=float(20 * np.log10(cf_now / cf_new)), jumped=bool(jumped),
                         delta=d.tolist()))
        print(f"{f:6.1f} Hz CF {cf_now:.3f} -> {cf_new:.3f} ({20 * np.log10(cf_now / cf_new):+.2f} dB){' jump' if jumped else ''}",
              flush=True)
    delta = np.array(delta)
    steps = np.abs(np.diff(delta, axis=0)); w = np.array([q.get('magnitudes', [0] * 7) for q in rows])[1:]
    print('largest weighted step between grid points (rad):', float(np.max(steps * (w > .05))), flush=True)
    body = ',\n'.join('    {' + ', '.join(f'{v:.9f}' for v in d) + '}' for d in delta)
    a.header.write_text(
        '#pragma once\n'
        '// Resultant R1 (#4 follow-up), generated by tools/pvb-harness/research_r1_phase_table.py from P1 (flags 0):\n'
        '// per fundamental f (kF0 + i kStep), the change of the unreferenced harmonic offsets k = 2..8 from kPsi that\n'
        '// gives the steady layer the lowest crest factor its own harmonic magnitudes allow. Host research only.\n'
        'namespace pvb {\nnamespace vbr1 {\n'
        f'constexpr double kF0 = {F0:g}, kStep = {STEP:g};\nconstexpr int kN = {len(grid)};\n'
        f'static const double kDelta[kN][7] = {{\n{body}\n}};\n'
        '}  // namespace vbr1\n}  // namespace pvb\n', encoding='utf-8')
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r1_phase_table.v1', issue=4, rows=rows), indent=2) + '\n',
                        encoding='utf-8')


if __name__ == '__main__':
    main()
