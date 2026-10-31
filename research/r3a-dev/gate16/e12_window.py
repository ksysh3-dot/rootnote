"""gate16 E1/E2: (E1) frequency response of the core's skewed Hann window vs the D1 resolution limit 2*kappa*fs/(N_J+N_f);
(E2) D2 cap min(A_joint, 2*A_single) on genuinely beating two-tone inputs (exact frequencies, noise free)."""
import numpy as np

FS = 3000.0


def window(Np, Nf):
    ms = np.arange(-Np, Nf + 1)
    w = np.where(ms <= 0, 0.5 * (1 + np.cos(np.pi * ms / (Np + 1))), 0.5 * (1 + np.cos(np.pi * ms / (Nf + 1))))
    return ms, w


def resp(Np, Nf, df, sym=False):
    """|sum w e^{j 2 pi df m/fs}| / sum w   (window main-lobe response at an offset df)"""
    if sym:
        L = Np + Nf + 1
        ms = np.arange(L) - (L - 1) / 2
        w = 0.5 * (1 + np.cos(np.pi * ms / (L / 2 + 0.5)))
    else:
        ms, w = window(Np, Nf)
    z = (w * np.exp(2j * np.pi * df * ms / FS)).sum() / w.sum()
    return abs(z)


print('== E1: |W(df)|/W(0) of the skewed window vs the D1 limit 2*kappa*fs/(N_J+N_f)  (kappa=1)')
for Np, Nf in ((320, 24), (200, 24), (100, 24), (57, 24), (30, 24)):
    lim = 2 * FS / (Np + Nf)
    row = []
    for dfx in (lim * 0.25, lim * 0.5, lim * 0.75, lim, lim * 1.25, lim * 1.5):
        a = resp(Np, Nf, dfx); b = resp(Np, Nf, dfx, sym=True)
        row.append(f'{dfx:5.1f}Hz skew {20*np.log10(a+1e-12):6.1f} / hann {20*np.log10(b+1e-12):6.1f} dB')
    print(f'N_J={Np:3d} N_f={Nf}: D1 limit {lim:5.1f} Hz | ' + ' | '.join(row))

print('\n== noise amplification of the joint 2-tone LS vs single: 1/sqrt(1-rho^2), rho = |W(df)|/W(0)  (N_J=320, N_f=24)')
for dfx in (1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 17.4, 20):
    r = resp(320, 24, dfx)
    print(f'  df {dfx:5.1f} Hz: |W| {r:.3f}  amplification {1/np.sqrt(1-min(r,0.9999)**2):5.2f}x ({20*np.log10(1/np.sqrt(1-min(r,0.9999)**2)):4.1f} dB)')


def ls(x, ms, w, freqs):
    cols = []
    for f in freqs:
        ph = 2 * np.pi * f * ms / FS
        cols += [np.cos(ph), np.sin(ph)]
    B = np.stack(cols, 1)
    G = (B * w[:, None]).T @ B
    G += 1e-4 * np.trace(G) / G.shape[0] * np.eye(G.shape[0])
    s = np.linalg.solve(G, (B * w[:, None]).T @ x)
    return np.hypot(s[0::2], s[1::2])


print('\n== E2: D2 cap min(A_joint, 2*A_single) on a genuinely beating pair, exact f_b, noise free.')
print('   window N_J=320,N_f=24 (stage-1 voices). A_single = single-voice LS on the raw x with the same window (no self harmonics).')
rng = np.random.default_rng(1)
ms, w = window(320, 24)
res = {}
for df in (3, 4, 6, 8, 10, 14, 17):
    for ratio in (1.0, 0.5, 0.25):
        errs1, errs2, bite1, bite2 = [], [], 0, 0
        n = 0
        for trial in range(2000):
            ph1, ph2 = rng.uniform(0, 2 * np.pi, 2)
            t0 = rng.uniform(0, 1)              # arbitrary position inside the beat cycle
            x = np.cos(2 * np.pi * 100 * (ms + t0 * 3000) / FS + ph1) + ratio * np.cos(2 * np.pi * (100 + df) * (ms + t0 * 3000) / FS + ph2)
            fb = (100.0, 100.0 + df)
            Aj = ls(x, ms, w, fb)
            As = np.array([ls(x, ms, w, (f,))[0] for f in fb])
            Ac = np.minimum(Aj, 2 * As)
            truth = np.array([1.0, ratio])
            e = 20 * np.log10(np.maximum(Ac, 1e-9) / truth)
            errs1.append(e[0]); errs2.append(e[1])
            bite1 += Ac[0] < Aj[0] - 1e-9; bite2 += Ac[1] < Aj[1] - 1e-9
            n += 1
        res[(df, ratio)] = (np.array(errs1), np.array(errs2), bite1 / n, bite2 / n)
        e1, e2 = np.array(errs1), np.array(errs2)
        print(f'  df {df:2d} Hz  amp ratio {ratio:4.2f}: cap bites strong {100*bite1/n:5.1f}% / weak {100*bite2/n:5.1f}% of beat phases; '
              f'bias of the capped A re truth: strong p5 {np.percentile(e1,5):6.1f} dB median {np.median(e1):5.2f} | weak p5 {np.percentile(e2,5):6.1f} median {np.median(e2):5.2f}')

print('\n== E2b: same pair but stage-2 style: window N_v = N_lo (30 or 57) for a 100 Hz voice, residual = x - neighbour stage-1 component (stage-1 exact here)')
for Nv in (30, 57, 120):
    ms2, w2 = window(Nv, 24)
    for df in (4, 8, 14):
        ratio = 1.0
        bites, cnt, mins = 0, 0, []
        for trial in range(2000):
            ph1, ph2 = rng.uniform(0, 2 * np.pi, 2); t0 = rng.uniform(0, 1)
            m = ms2 + t0 * 3000
            x = np.cos(2 * np.pi * 100 * m / FS + ph1) + ratio * np.cos(2 * np.pi * (100 + df) * m / FS + ph2)
            A2 = 1.0
            As_raw = ls(x, ms2, w2, (100.0,))[0]                      # A_single on the raw x (same window)
            cap_raw = min(A2, 2 * As_raw)
            bites += cap_raw < A2 - 1e-9; cnt += 1; mins.append(20 * np.log10(cap_raw / A2))
        mins = np.array(mins)
        print(f'  N_v={Nv:3d} df {df:2d} Hz equal amplitudes: cap on raw-x A_single bites in {100*bites/cnt:5.1f}% of beat phases, worst {mins.min():6.1f} dB, p5 {np.percentile(mins,5):6.1f} dB')
