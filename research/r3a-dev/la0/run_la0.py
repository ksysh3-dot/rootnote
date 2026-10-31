"""One script, end to end:   ./run.sh ../la0/run_la0.py [--dev]      (run from ~/r3a-dev/diag16, see la0/run_la0.sh)
 stage A  LA analysis for every (signal, stream, L)  (multiprocessing, cached pickles)
 stage B  per-(stream, L) decision models trained on the 5 TRAIN songs only (identical hyper-parameters at every L)
 stage C  rows -> proxy layers / V6b weights -> metrics        stage D  report.py (decision rule)
--dev: no evaluation song is touched (train songs + synthetic signals)."""
import sys, time, json, argparse
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import multiprocessing as mp
import numpy as np
from data import *
import pipeline as P, evaluate as E, labels, classify

LAG = 191
SYN_KEYS = [k for k in P.SYNTH if k != 'bass8c']


def songs_for(dev):
    return TRAIN if dev else TRAIN + EVAL


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dev', action='store_true'); ap.add_argument('--lag', type=int, default=LAG)
    ap.add_argument('--out', default='results'); a = ap.parse_args()
    lag = a.lag
    t0 = time.time()
    songs = songs_for(a.dev)
    keys = P.SYNTH + songs
    for k in keys:                       # make sure the caches exist (renders new synthetic signals once)
        Sig(k)
    jobs = [(k, s, L, lag) for k in keys for s in P.STREAMS for L in P.LS]
    with mp.get_context('fork').Pool(14) as pool:
        for _ in pool.imap_unordered(P.compute_la, jobs):
            pass
    print('stage A done', round(time.time() - t0, 1), flush=True)
    models = {}; minfo = {}
    for s in P.STREAMS:
        for L in P.LS:
            m, info = P.train_models(s, L, lag)
            models[(s, L)] = (m, info); minfo[f'{s}-{L}'] = dict(info, beta=np.round(m[2], 3).tolist(), mu=np.round(m[0], 3).tolist(), sd=np.round(m[1], 3).tolist())
    lags = E.load_lags()
    rows = E.row_names(with_all=True)
    out = dict(lag=lag, lags=lags, models=minfo, feats=classify.FEATS, synthetic={}, songs={}, classifier={}, ratios={})
    # ---- synthetic signals
    for key in SYN_KEYS:
        sig = Sig(key)
        for r in rows:
            if r.startswith('ALL'):
                continue
            o = E.eval_synthetic(r, key, sig, models, lag, lags)
            out['synthetic'].setdefault(r, {}).update(o or {})
        print('synthetic', key, round(time.time() - t0, 1), flush=True)
    # ---- songs: V6b per window
    for name in songs:
        sig = Sig(name); tr = labels.Truth(name, sig.tc1)
        out['songs'][name] = {}
        for r in rows:
            if r not in ('core', 'p1') and name in TRAIN and not a.dev:
                continue                                    # LA rows are only scored on the evaluation songs (in --dev they are scored in-sample on the train songs, sanity only)
            o = E.eval_song(r, name, sig, models, lag, lags, tr)
            if o is None:
                continue
            out['songs'][name][r] = dict(wrong=o['wrong'], right=o['right'], share=o['share'], win_wrong=o['win_wrong'].tolist(), win_right=o['win_right'].tolist())
        print('songs', name, round(time.time() - t0, 1), flush=True)
    # ---- classifier quality (evaluation songs) and joint/single ratios
    ev = [k for k in songs if k in EVAL] or list(songs)       # --dev: in-sample on the train songs (sanity only)
    for s in P.STREAMS:
        for L in P.LS:
            sc, lb, w, rat = [], [], [], []
            for k in ev:
                d = P.load_la(k, s, L, lag)
                if len(d['F']):
                    sc.append(classify.predict(models[(s, L)][0], d['F'])); lb.append(d['label']); w.append(d['W'])
                if len(d['res']['ratios']):
                    rat.append(d['res']['ratios'])
            if sc:
                sc, lb, w = np.concatenate(sc), np.concatenate(lb), np.concatenate(w)
                m = w > 0
                out['classifier'][f'{s}-{L}'] = dict(auc_w=classify.auc(sc[m], lb[m], w[m]), auc_unw=classify.auc(sc[m], lb[m]), n=int(m.sum()), frac_right_w=float((w * lb).sum() / w.sum()),
                                                      frac_on_w=float((w * (sc >= .5)).sum() / w.sum()))
            if rat:
                rat = np.vstack(rat)
                out['ratios'][f'{s}-{L}'] = dict(p95=float(np.percentile(rat[:, 0], 95)), p50=float(np.median(rat[:, 0])), n=int(len(rat)), frac_capped=float(np.mean(rat[:, 0] > 2.0)))
    json.dump(out, open(LA0 / f'{a.out}.json', 'w'), default=float)
    print('stage C done', round(time.time() - t0, 1), flush=True)


if __name__ == '__main__':
    main()
