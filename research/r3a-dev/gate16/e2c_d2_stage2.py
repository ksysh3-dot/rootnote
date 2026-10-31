"""gate16 E2c: D2 on stage-2 voices with A_single taken on the RAW signal (literal 'same signal'): probability that min(A, 2*A_single) bites on a clean voice whose
neighbour (another clean voice, exactly separated by stage 1) is df away, as a function of df, the neighbour/own amplitude ratio r and the stage-2 window N_v.
Closed form + Monte Carlo check: A_single = |A + r A W(df) e^{j psi}|, psi uniform; W from the skewed window."""
import numpy as np

FS = 3000.0


def W(Np, Nf, df):
    ms = np.arange(-Np, Nf + 1)
    w = np.where(ms <= 0, .5 * (1 + np.cos(np.pi * ms / (Np + 1))), .5 * (1 + np.cos(np.pi * ms / (Nf + 1))))
    return abs((w * np.exp(2j * np.pi * df * ms / FS)).sum() / w.sum())


rng = np.random.default_rng(3)
print('P(cap bites) [and median dB loss when it bites] for clean voice pairs, own amplitude 1, neighbour r; A_single on raw x; stage-2 window N_v (N_f=24)')
for Nv in (30, 40, 57, 100):
    print(f'N_v = {Nv}')
    for r in (1.0, 0.7, 0.5):
        row = []
        for df in (5, 10, 20, 30, 40, 55, 80):
            rho = W(Nv, 24, df)
            psi = rng.uniform(0, 2 * np.pi, 200000)
            a_single = np.abs(1 + r * rho * np.exp(1j * psi))
            cap = np.minimum(1.0, 2 * a_single)
            bite = cap < 1 - 1e-9
            loss = -20 * np.log10(cap[bite]) if bite.any() else np.array([0.0])
            row.append(f'df{df:3d}: {100*bite.mean():4.1f}% ({np.median(loss):4.1f} dB, p95 {np.percentile(loss,95):4.1f})')
        print(f'  r={r:3.1f}  ' + ' | '.join(row))
