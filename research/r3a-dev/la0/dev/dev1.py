"""development run: train songs + synthetic signals only (no evaluation song is touched)"""
import sys, time, json
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import multiprocessing as mp
import numpy as np
from data import *
import pipeline as P, evaluate as E, labels

if __name__ == '__main__':
    t0 = time.time()
    keys = P.SYNTH + TRAIN
    jobs = [(k, s, L, 191) for k in keys for s in P.STREAMS for L in P.LS]
    with mp.get_context('fork').Pool(14) as pool:
        for i, _ in enumerate(pool.imap_unordered(P.compute_la, jobs)):
            pass
    print('stage A', round(time.time() - t0, 1), 's', flush=True)
    models = {}
    for s in P.STREAMS:
        for L in P.LS:
            m, info = P.train_models(s, L, 191)
            models[(s, L)] = (m, info)
            print('model', s, L, info, 'beta', np.round(m[2], 2).tolist(), flush=True)
    lags = E.load_lags()
    rows = E.row_names(with_all=False)
    res = {}
    for key in P.SYNTH:
        if key == 'bass8c':
            continue
        sig = Sig(key)
        for r in rows:
            o = E.eval_synthetic(r, key, sig, models, 191, lags)
            res.setdefault(r, {}).update(o or {})
    for r in rows:
        print(r, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res[r].items()})
    json.dump(res, open(LA0 / 'dev1.json', 'w'), indent=1, default=float)
    print('total', round(time.time() - t0, 1))
