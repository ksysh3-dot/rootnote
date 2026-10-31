"""Stage A (LA analysis per signal x stream x L, cached) and the row/metric evaluation."""
import os, pickle, time, sys
import numpy as np
from data import *
import la, classify, labels, rows as R, metrics as MT
import research_core_metrics as M

LS = [0, 64, 120, 217]
STREAMS = ['bh', 'det']
SYNTH = ['bare100', 'step25', 'bass9', 'bkp_0', 'bass8c', 'steady8', 'pink10', 't60_36_48', 'logoff_37_49']
SONGS_TRAIN, SONGS_EVAL = TRAIN, EVAL
_DUR = {}


def duration(key):
    if key not in _DUR:
        _DUR[key] = len(audio(key)) / FS if not key.startswith('Track') else 30.0
    return _DUR[key]


def cache_path(key, stream, L, lag):
    return CACHE / f'la_{key}_{stream}_{L}_{lag}.pkl'


def strip(res):
    for ch in res['chunks']:
        ch.PH = None; ch.fj = None
    return res


def compute_la(args):
    key, stream, L, lag = args
    p = cache_path(key, stream, L, lag)
    if p.exists():
        return str(p)
    t0 = time.time()
    sig = Sig(key)
    res = la.run_la(sig, stream, L, lag)
    tr = labels.Truth(key, sig.tc1)
    F = classify.interval_features(sig, res)
    W, Wr, Ww, lab = classify.weights_labels(res, tr if tr.ok else None, sig, sig.tc1)
    res = strip(res)
    pickle.dump(dict(res=res, F=F, W=W, Wr=Wr, Ww=Ww, label=lab, truth_ok=tr.ok, secs=time.time() - t0), open(p, 'wb'), protocol=4)
    return str(p)


def prep(key):
    Sig(key)
    return key


def load_la(key, stream, L, lag):
    return pickle.load(open(cache_path(key, stream, L, lag), 'rb'))


# ------------------------------------------------------------------------------------------------ classifier
def train_models(stream, L, lag, train_keys=SONGS_TRAIN):
    Fs, ys, ws = [], [], []
    for k in train_keys:
        d = load_la(k, stream, L, lag)
        m = d['W'] > 0
        Fs.append(d['F'][m]); ys.append(d['label'][m]); ws.append(d['W'][m])
    F, y, w = np.vstack(Fs), np.concatenate(ys), np.concatenate(ws)
    return classify.fit_logistic(F, y, w), dict(n=int(len(y)), right_w=float((w * y).sum() / w.sum()))


# ------------------------------------------------------------------------------------------------ V6b per row and song
def hop_weights(voices, tc, truth, tmin=0.5):
    """per-voice-hop (hop index, f, weight = amp^2) at the hop centres tc (tc > tmin)"""
    hs, fs, ws = [], [], []
    for v in voices:
        t, a, f = v['t'], v['amp'], v['f']
        lo = np.searchsorted(tc, t[0], 'left'); hi = np.searchsorted(tc, t[-1], 'right')
        if hi <= lo:
            continue
        h = np.arange(lo, hi)
        am = np.interp(tc[h], t, a, left=0.0, right=0.0)
        m = (am > 0) & (tc[h] > tmin)
        if m.any():
            hs.append(h[m]); fs.append(np.interp(tc[h[m]], t, f)); ws.append(am[m] ** 2)
    if not hs:
        return np.zeros(0, int), np.zeros(0), np.zeros(0)
    return np.concatenate(hs), np.concatenate(fs), np.concatenate(ws)


def v6b_row(voices, tc, truth):
    h, f, w = hop_weights(voices, tc, truth)
    bad = truth.wrong(h, f) if len(h) else np.zeros(0, bool)
    nwin = int(tc[-1] // 5.0) + 2
    win = np.minimum((tc[h] // 5.0).astype(int), nwin - 1) if len(h) else np.zeros(0, int)
    ww = np.bincount(win, weights=w * bad, minlength=nwin); wr = np.bincount(win, weights=w * ~bad, minlength=nwin)
    return dict(wrong=float(ww.sum()), right=float(wr.sum()), share=float(ww.sum() / max(ww.sum() + wr.sum(), 1e-30)), win_wrong=ww, win_right=wr)
