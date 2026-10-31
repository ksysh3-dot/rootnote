"""HAUX Q1 supplementary (post-run addition, see CHOICES bottom): ROC operating points vs K2, pitch-stratified AUC, subset of songs with >= 1000 real hops."""
import glob
import numpy as np
from scipy.stats import rankdata
from pathlib import Path
HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')
BASS = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00025']


def load(key):
    zs = [np.load(p) for p in sorted(glob.glob(str(HX / 'cache' / f'feat_{key}_p*.npz')))]
    return {k: np.concatenate([z[k] for z in zs]) for k in zs[0].files}


def feats(d, W):
    E = d[f'E_t{W}'].astype(float); Ei = d[f'Ei_t{W}'].astype(float)
    with np.errstate(all='ignore'):
        fl12 = np.nanmean(Ei[:, :11], 1)
        h12 = 10 * np.log10((np.nanmean(E[:, :11], 1) + 1e-30) / (fl12 + 1e-30))
        nh = np.nansum(np.where(np.isfinite(E[:, :7]), E[:, :7] >= 4 * fl12[:, None], False), 1).astype(float)
    return dict(h12=h12, nhit=nh)


def auc(p, n):
    p = p[np.isfinite(p)]; n = n[np.isfinite(n)]
    if len(p) < 30 or len(n) < 30:
        return np.nan
    r = rankdata(np.concatenate([p, n])); return float((r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n)))


D = {k: load(k) for k in BASS}
L = []; P = lambda s='': L.append(s)
for W in (40, 85):
    Fz = {k: feats(D[k], W) for k in BASS}
    real = {k: (D[k]['cls'] == 0) & (D[k]['comp'] == 0) for k in BASS}
    ghost = {k: (D[k]['cls'] == 2) & (D[k]['comp'] >= 3) for k in BASS}
    P(f'\n## window {W} ms')
    # pooled ROC points
    r_h = np.concatenate([Fz[k]['h12'][real[k]] for k in BASS]); g_h = np.concatenate([Fz[k]['h12'][ghost[k]] for k in BASS])
    r_n = np.concatenate([Fz[k]['nhit'][real[k]] for k in BASS]); g_n = np.concatenate([Fz[k]['nhit'][ghost[k]] for k in BASS])
    r_k = np.concatenate([D[k]['K2'][real[k]] for k in BASS]).astype(float); g_k = np.concatenate([D[k]['K2'][ghost[k]] for k in BASS]).astype(float)
    P(f'pooled: K2 true in real {r_k.mean():.3f}, ghost {g_k.mean():.3f}')
    for nm, r, g in (('H_sal12', r_h, g_h), ('n_hit', r_n, g_n)):
        r = r[np.isfinite(r)]; g = g[np.isfinite(g)]
        thr = np.quantile(g, 1 - g_k.mean())                       # same ghost pass rate as K2
        thr2 = np.quantile(r, 1 - r_k.mean())                      # same real pass rate as K2
        P(f'{nm}: at the ghost pass rate of K2 ({g_k.mean():.3f}) real pass rate {(r >= thr).mean():.3f} (K2 {r_k.mean():.3f}); at the real pass rate of K2 ghost pass rate {(g >= thr2).mean():.3f} (K2 {g_k.mean():.3f}); at 50 % ghost pass rate real pass {(r >= np.quantile(g, .5)).mean():.3f}')
    # pitch strata (pooled, f_track bins)
    f_r = np.concatenate([D[k]['ftr'][real[k]] for k in BASS]); f_g = np.concatenate([D[k]['ftr'][ghost[k]] for k in BASS])
    P('pitch strata of f_track (Hz): bin | n_real | n_ghost | AUC H_sal12 | AUC n_hit | AUC K2')
    for lo, hi in ((0, 50), (50, 70), (70, 90), (90, 120), (120, 400)):
        mr = (f_r >= lo) & (f_r < hi); mg = (f_g >= lo) & (f_g < hi)
        P(f'{lo}-{hi} | {mr.sum()} | {mg.sum()} | {auc(r_h[mr], g_h[mg]):.3f} | {auc(r_n[mr], g_n[mg]):.3f} | {auc(r_k[mr], g_k[mg]):.3f}')
    P(f'f_track median: real {np.median(f_r):.1f}, ghost {np.median(f_g):.1f}')
    # songs with >= 1000 real hops and ghosts
    ks = [k for k in BASS if real[k].sum() >= 1000 and ghost[k].sum() >= 1000]
    for nm in ('h12', 'nhit'):
        a = [auc(Fz[k][nm][real[k]], Fz[k][nm][ghost[k]]) for k in ks]
        P(f'{nm}: songs with >= 1000 real and ghost hops {len(ks)} ({[k[-2:] for k in ks]}): median AUC {np.median(a):.3f}, range {min(a):.3f}-{max(a):.3f}')
    a = [auc(D[k]['K2'][real[k]].astype(float), D[k]['K2'][ghost[k]].astype(float)) for k in ks]
    P(f'K2: same songs median {np.median(a):.3f}')
open(HX / 'q1x_report.txt', 'w').write('\n'.join(L)); print('\n'.join(L))
