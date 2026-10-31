"""HAUX cost estimate (CHOICES.md section 6): alive voices per hop (Slakh traces, user-song traces), flop counts of the comb LS at decimated rates, numpy wall time sanity check."""
import os, sys, time
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import numpy as np
from scipy.signal import resample_poly
import haux_lib as H
import kcommon as K
from kcommon import *
from pathlib import Path
HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')
L = []
P = lambda s='': L.append(s)
# alive voices per hop
allc = []
P('## alive voices per hop (amp > 0) in the Slakh core v1.5 traces (30 s each): song | mean | p95 | max')
for key in SONGS:
    ctx = K.SongCtx(key, probe_nobass=False)
    cnt = np.zeros(len(ctx.tc), int)
    for v in ctx.voices:
        h = v['hs'][v['A'] > 0]
        np.add.at(cnt, h, 1)
    allc.append(cnt)
    P(f'{key} | {cnt.mean():.2f} | {np.percentile(cnt, 95):.0f} | {cnt.max()}')
ac = np.concatenate(allc)
P(f'pooled | {ac.mean():.2f} | {np.percentile(ac, 95):.0f} | {ac.max()}')
for sk in ('app', 'rem'):
    z = np.load(HX / 'tmp' / f'{sk}_v15_trace.npz')
    st = z['state']; n_on = (st >= 2).sum(1)
    P(f'user song {sk} (v1.5 trace, state >= 2 slots per hop): mean {n_on.mean():.2f}, p95 {np.percentile(n_on, 95):.0f}, max {n_on.max()}')
mean_v = float(ac.mean()); p95_v = float(np.percentile(ac, 95))
HOPS_PER_S = 3000 / 16
P(f'\nhops per second {HOPS_PER_S:.1f}')


def flops_fit(Ls, kmax):
    n = 1 + 2 * kmax; n2 = 2 * (kmax - 1)
    # harmonic fit: basis (recurrence, ~4 flop/element), Gram (symmetric, L n^2 incl. both mult/add), rhs 2 L n, Cholesky n^3/3 + 2 n^2, residual 2 L n
    a = Ls * n * 4 + Ls * n * n + 2 * Ls * n + n ** 3 / 3 + 2 * n * n + 2 * Ls * n
    # inter fit on the residual
    b = Ls * n2 * 4 + Ls * n2 * n2 + 2 * Ls * n2 + n2 ** 3 / 3 + 2 * n2 * n2
    return a + b, n, n2


def flops_B(Ls, kmax):
    """projection-only: Gram from the closed-form window transform (n^2/2 table lookups, ~20 flops each), projections 2 L n, solve, residual energy from the normal equations (no L-length residual)"""
    n = 1 + 2 * kmax; n2 = 2 * (kmax - 1)
    a = 20 * n * n / 2 + 2 * Ls * n + n ** 3 / 3 + 2 * n * n
    b = 20 * n2 * n2 / 2 + 2 * Ls * n2 + n2 ** 3 / 3 + 2 * n2 * n2 + 2 * n * n2 * 4
    return a + b


P('\n## flops per fit and per second (kmax = 12: f <= 166 Hz; fits on every hop for every alive voice)')
P('fs | window | L | cols (harm/inter) | A: Mflop per fit | A: MFLOP/s at mean voices | A: at p95 voices | B (projection-only, analytic Gram): MFLOP/s at mean | at p95 | B with fit every 2nd hop (mean)')
for fs in (8000, 12000):
    for W in (40, 85):
        Ls = int(W * fs / 1000)
        fa, n, n2 = flops_fit(Ls, 12)
        fb = flops_B(Ls, 12)
        P(f'{fs} | {W} ms | {Ls} | {n}/{n2} | {fa / 1e6:.3f} | {fa * HOPS_PER_S * mean_v / 1e6:.0f} | {fa * HOPS_PER_S * p95_v / 1e6:.0f} | {fb * HOPS_PER_S * mean_v / 1e6:.0f} | {fb * HOPS_PER_S * p95_v / 1e6:.0f} | {fb * HOPS_PER_S * mean_v / 2e6:.0f}')
# numpy wall time sanity check
rng = np.random.default_rng(0)
x48 = rng.standard_normal(48000)
P('\nnumpy wall time per comb_fit (harmonic + inter, f = 80 Hz, kmax 12), single thread, this PC (includes python overhead):')
for fs in (48000, 12000, 8000):
    xd = resample_poly(x48, fs // 4000, 48000 // 4000) if fs != 48000 else x48
    for W in (40, 85):
        Ls = int(W * fs / 1000); w = H.hann(Ls); seg = H.segment(xd, len(xd) // 2, Ls)
        t0 = time.time()
        for _ in range(40):
            H.comb_fit(seg, w, 80.0, fs=fs)
        P(f'fs {fs} W{W}: {(time.time() - t0) / 40 * 1e3:.2f} ms/fit')
open(HX / 'cost_report.txt', 'w').write('\n'.join(L)); print('\n'.join(L))
