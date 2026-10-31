"""Interval decision (section 14 (4)): features from the tracker information usable at t_on (hops from t_on up to the newest hop the lookahead allows;
the single newest usable hop when there is none), weighted logistic regression (weight = sum of A^2 of the interval), threshold p(note) < 0.5 -> OFF."""
import numpy as np
from data import stream_time, HOP_S, FSC
from la import GRID_A, TRK_LAG

FEATS = ['logf', 'jit_c', 'dfdt_rel', 'slope_dbs', 'raw', 'res', 'ev2', 'ev3', 'len', 'has_lower', 'lower_ratio', 'near_c', 'near_ratio', 'ntr']
RIDGE_L2 = 1.0


def interval_features(sig, res):
    """feature matrix (n_iv, len(FEATS)) for every interval of an LA result"""
    ts, tc = sig.ts, sig.tc1
    L_ms = res['L_ms']; Ls = int(round(3 * L_ms))
    valid = ts[:sig.nhop, :, 1] > 0
    ident = (ts[:sig.nhop, :, 0] + 65536 * ts[:sig.nhop, :, 13]).astype(np.int64)
    F = np.zeros((len(res['ivs']), len(FEATS)))
    for q, iv in enumerate(res['ivs']):
        ch = iv['ch']
        t_on = float(stream_time(iv['j_on'])); t_off = float(stream_time(iv['j_off']))
        c_hi = t_on + (Ls - res.get('trk_lag', TRK_LAG)) / FSC    # newest tracker hop centre usable at output time t_on
        c_hi = min(c_hi, t_off)
        m = (ch.t_real >= t_on - HOP_S) & (ch.t_real <= max(c_hi, ch.t_real[0]))
        if not m.any():
            k = np.searchsorted(ch.t_real, max(c_hi, ch.t_real[0]), 'right') - 1
            m = np.zeros(len(ch.t_real), bool); m[max(k, 0)] = True
        sel = np.flatnonzero(m)
        f = np.interp(ch.t_real[sel], ch.tc, ch.f) if False else ts[ch.hs[sel], ch.js[sel], 2]
        a = np.maximum(ch.a_real[sel], 1e-7)
        t = ch.t_real[sel]
        F[q, 0] = np.log2(np.median(f) / 100.0)
        F[q, 1] = float(np.std(1200 * np.log2(f / np.median(f)))) if len(f) > 1 else 0.0
        F[q, 2] = float(np.median(np.abs(ch.dfdt_real[sel]) / np.maximum(f, 1.0)))
        F[q, 3] = float(np.clip(np.polyfit(t, 20 * np.log10(a), 1)[0], -200, 200)) if len(sel) >= 3 and np.ptp(t) > 0 else 0.0
        F[q, 4] = float(np.clip(np.median(ch.raw_real[sel]), -60, 10))
        F[q, 5] = float(np.clip(np.median(ch.res_real[sel]), -60, 10))
        ev2 = ev3 = 0.0; has_low = 0.0; low_r = 0.0; near_c = 600.0; near_r = 0.0; ntr = []
        for s in sel:
            h = ch.hs[s]; j0 = ch.js[s]
            v = np.flatnonzero(valid[h]); v = v[v != j0]
            fo = ts[h, v, 2]; ao = np.maximum(ts[h, v, 4], 1e-7); f0 = ts[h, j0, 2]; a0 = max(ts[h, j0, 4], 1e-7)
            ntr.append(len(v) + 1)
            if not len(v):
                continue
            m2 = np.abs(fo - 2 * f0) <= 0.03 * 2 * f0
            m3 = np.abs(fo - 3 * f0) <= 0.03 * 3 * f0
            if m2.any():
                ev2 = max(ev2, float(np.log10(1 + min((ao[m2] / a0).max(), 100.0)) / 2))
            if m3.any():
                ev3 = max(ev3, float(np.log10(1 + min((ao[m3] / a0).max(), 100.0)) / 2))
            for mm in (2, 3, 4):
                ml = (fo < 0.9 * f0) & (np.abs(f0 - mm * fo) <= 0.03 * f0)
                if ml.any():
                    has_low = 1.0; low_r = max(low_r, float(np.clip(np.log10((ao[ml] / a0).max()), -2, 3)))
            cents = np.abs(1200 * np.log2(np.maximum(fo, 1e-3) / f0))
            k = int(np.argmin(cents))
            if cents[k] < near_c:
                near_c = float(cents[k]); near_r = float(np.clip(np.log10(ao[k] / a0), -2, 2))
        F[q, 6] = ev2; F[q, 7] = ev3
        F[q, 8] = float(np.log1p(min(t_off - t_on, L_ms / 1000.0) / HOP_S))
        F[q, 9] = has_low; F[q, 10] = low_r
        F[q, 11] = min(near_c, 600.0) / 600.0; F[q, 12] = near_r if near_c < 600 else 0.0
        F[q, 13] = float(np.median(ntr)) if ntr else 1.0
    return F


def weights_labels(res, truth, sig, tc_hops):
    """per interval: weight W = sum of Af^2 (un-gated smoothed amplitude), right / wrong weight by the V6b label, majority label.
    truth: Truth object (or None)."""
    n = len(res['ivs'])
    W = np.zeros(n); Wr = np.zeros(n); Ww = np.zeros(n)
    for q, iv in enumerate(res['ivs']):
        Af = iv['Af']
        if not len(Af):
            continue
        w = Af ** 2
        W[q] = w.sum()
        if truth is not None and truth.ok:
            t = stream_time((iv['m0'] + np.arange(len(Af))) * GRID_A)
            ch = iv['ch']
            shift = max(ch.D, 0) / FSC
            f = np.interp(t - shift, ch.tc, ch.f)
            wr = truth.wrong(truth.hop_of(t), f)
            Ww[q] = w[wr].sum(); Wr[q] = w[~wr].sum()
    label = (Wr >= Ww).astype(float)                         # 1 = right (weight majority; ties -> right)
    return W, Wr, Ww, label


def fit_logistic(X, y, w, lam=RIDGE_L2, iters=50):
    """weighted L2 logistic regression (Newton / IRLS) on standardised features.  returns (mu, sd, beta)"""
    mu = np.average(X, axis=0, weights=np.maximum(w, 1e-30)); sd = np.sqrt(np.average((X - mu) ** 2, axis=0, weights=np.maximum(w, 1e-30)))
    sd = np.where(sd < 1e-9, 1.0, sd)
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    wn = w / max(w.sum(), 1e-30) * len(w)                    # weights normalised to mean 1
    beta = np.zeros(Z.shape[1]); R = lam * np.eye(Z.shape[1]); R[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ beta, -30, 30)))
        g = Z.T @ (wn * (p - y)) + R @ beta
        H = (Z * (wn * p * (1 - p))[:, None]).T @ Z + R + 1e-8 * np.eye(Z.shape[1])
        step = np.linalg.solve(H, g); beta -= step
        if np.abs(step).max() < 1e-7:
            break
    return mu, sd, beta


def predict(model, X):
    mu, sd, beta = model
    z = beta[0] + ((X - mu) / sd) @ beta[1:]
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def auc(score, label, w=None):
    """(weighted) AUC of score for label==1; ties count half"""
    score = np.asarray(score, float); label = np.asarray(label) > 0.5
    w = np.ones(len(score)) if w is None else np.asarray(w, float)
    pos = label & (w > 0); neg = ~label & (w > 0)
    if not pos.any() or not neg.any():
        return float('nan')
    order = np.argsort(score, kind='stable'); s = score[order]; ww = w[order]; lab = label[order]
    # group ties
    uniq, start = np.unique(s, return_index=True)
    cneg = np.cumsum(np.where(lab, 0, ww)); tot_neg = cneg[-1]
    acc = 0.0; prev_neg = 0.0
    ends = np.r_[start[1:], len(s)]
    for a, b in zip(start, ends):
        pw = ww[a:b][lab[a:b]].sum(); nw_in = ww[a:b][~lab[a:b]].sum()
        acc += pw * (prev_neg + 0.5 * nw_in); prev_neg += nw_in
    return float(acc / (ww[lab].sum() * tot_neg))
