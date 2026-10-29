#!/usr/bin/env python3
"""Resultant R3-a (#4): do the R3 frame cues combine into a rule that holds on both development sets? Reads the frame
dumps of research_r3a_harmonic (BabySlakh, MUSDB) and reports, trained on one set and scored on the other:
  logistic   AUC of a logistic model on the standardised mix-only cues (good = correct restoration vs bad = wrong halving)
  rules      simple added conditions on R3 (each threshold grid point): share of good restorations kept, share of wrong
             halvings removed, and the frame balance (kept good - remaining bad) per set, which is what tracking sees
Mix-only cues (the engine could compute them): half, h_half, x15, half_peak, h_spread, comod, f_err_half, f_err_15."""
import itertools, json, sys
import numpy as np

CUES = ('half', 'h_half', 'x15', 'half_peak', 'h_spread', 'comod', 'f_err_half', 'f_err_15')


def load(path):
    d = json.load(open(path))
    X = {k: np.array([[x[c] for c in CUES] for x in d[k]], float) for k in ('good', 'bad')}
    return X


def auc(s_pos, s_neg):
    s = np.r_[s_pos, s_neg]; r = np.argsort(np.argsort(s)) + 1.
    return float((r[:len(s_pos)].sum() - len(s_pos) * (len(s_pos) + 1) / 2) / (len(s_pos) * len(s_neg)))


def prep(X, mu=None, sd=None):
    A = np.r_[X['good'], X['bad']]; y = np.r_[np.ones(len(X['good'])), np.zeros(len(X['bad']))]
    med = np.nanmedian(A, axis=0); A = np.where(np.isfinite(A), A, med)
    if mu is None: mu, sd = A.mean(0), A.std(0) + 1e-9
    return (A - mu) / sd, y, mu, sd


def fit(A, y, l2=1e-2, it=500):
    w = np.zeros(A.shape[1] + 1); Ab = np.c_[A, np.ones(len(A))]
    for _ in range(it):
        p = 1 / (1 + np.exp(-Ab @ w)); g = Ab.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0]
        Hm = (Ab * (p * (1 - p))[:, None]).T @ Ab / len(y) + l2 * np.eye(len(w)); w -= np.linalg.solve(Hm, g)
    return w


sets = {'slakh': load(sys.argv[1]), 'musdb': load(sys.argv[2])}
for c in CUES:
    i = CUES.index(c)
    print(f'{c:12s} AUC slakh {auc(*(np.nan_to_num(sets["slakh"][k][:, i], nan=np.nanmedian(sets["slakh"][k][:, i])) for k in ("good", "bad"))):.3f}'
          f'  musdb {auc(*(np.nan_to_num(sets["musdb"][k][:, i], nan=np.nanmedian(sets["musdb"][k][:, i])) for k in ("good", "bad"))):.3f}')
for tr, te in (('slakh', 'musdb'), ('musdb', 'slakh')):
    A, y, mu, sd = prep(sets[tr]); w = fit(A, y); B, yb, _, _ = prep(sets[te], mu, sd)
    s = np.c_[B, np.ones(len(B))] @ w
    print(f'logistic trained on {tr}: AUC on {te} {auc(s[yb == 1], s[yb == 0]):.3f}  (in-set {auc(*(lambda s2: (s2[y == 1], s2[y == 0]))(np.c_[A, np.ones(len(A))] @ w)):.3f})'
          f'  weights ' + ' '.join(f'{c}={v:+.2f}' for c, v in zip(CUES, w)))
# frame counts before sampling (diagnosis): slakh good 4411 bad 5485, musdb good 8846 bad 1331
N = {'slakh': (4411, 5485), 'musdb': (8846, 1331)}
grid = dict(half=(-20, -14, -10, -6), comod=(-1, 0, .2, .4, .6), x15=(-20, -10, -6, -3))
print('\nadded conditions (half >= a, comod >= c, x15 >= x): per set good kept / bad removed / frame balance vs R3 and vs P1')
rows = []
for a, c, x in itertools.product(*grid.values()):
    out = []
    for n, X in sets.items():
        def keep(M):
            h, cm, x15 = M[:, CUES.index('half')], M[:, CUES.index('comod')], M[:, CUES.index('x15')]
            return (h >= a) & ((np.nan_to_num(cm, nan=1.) >= c)) & (x15 >= x)
        gk, br = keep(X['good']).mean(), 1 - keep(X['bad']).mean(); G, Bn = N[n]
        out.append((n, gk, br, G * gk - Bn * (1 - br), G - Bn))
    rows.append(((a, c, x), out))
rows.sort(key=lambda r: -min(o[3] / (abs(o[4]) + 1e3) for o in r[1]))
for (a, c, x), out in rows[:12]:
    print(f'half>={a:4d} comod>={c:4.1f} x15>={x:4d} | ' + ' | '.join(f'{n}: good {gk:.2f} bad-removed {br:.2f} net {net:+6.0f} (R3 {r3:+6.0f})'
                                                               for n, gk, br, net, r3 in out))
