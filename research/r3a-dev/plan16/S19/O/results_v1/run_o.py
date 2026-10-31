"""S19-O main: per (row, song) all variants -> O/res/<row>_<song>.json  (class energy sums, deviation histograms)."""
import sys, json, time, os
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from s19o_lib import *
from multiprocessing import Pool
RES = O_DIR / 'res'; RES.mkdir(exist_ok=True)
FCS = [4, 8, 16, 32]
TS = [5, 10, 20, 40]
EDGES = np.concatenate([[0], np.geomspace(1e-3, 1e3, 241)])


def variants(row):
    v = {'base': ('base',)}
    if row == 'b0p0':
        return v
    for fc in FCS:
        v[f'a{fc}'] = ('sus', fc, True, False, False)
        v[f'b{fc}'] = ('sus', fc, False, True, False)
        v[f'c{fc}'] = ('sus', fc, True, True, False)
        v[f'ea{fc}'] = ('sus', fc, True, False, True)
        v[f'eb{fc}'] = ('sus', fc, False, True, True)
        v[f'ec{fc}'] = ('sus', fc, True, True, True)
    v['d1'] = ('sus', 1, True, True, False)
    for T in TS:
        v[f'xf{T}'] = ('xf', T)
    return v


def hist(arrs):
    if not arrs:
        return dict(n=0, ss=0.0, h=[0] * (len(EDGES) - 1))
    x = np.abs(np.concatenate(arrs))
    return dict(n=int(len(x)), ss=float((x ** 2).sum()), h=np.histogram(x, EDGES)[0].tolist())


def job(a):
    row, i = a
    f = RES / f'{row}_{i:02d}.json'
    if f.exists():
        return a
    t = time.time()
    d, boxes = load(row, i)
    cl = classify(d, boxes)
    sk = {v: k for k, v in P.SONG_IDX.items()}.get(i)
    ms = masks(cl, len(boxes), sk)
    runs = make_runs(d, cl)
    out = dict(row=row, song=i, name=P.MUSIC[i].name, nseg=int(sum(len(r['segs']) for r in runs)), seghops=int(sum(e - s + 1 for r in runs for (s, e) in r['segs'])),
               onhops=int(sum(int((r['state'][1:] == 2).sum()) for r in runs)), nxf=int(sum(len(r['xf']) for r in runs)), dur=float(len(d['hop']) * HOPS), v={})
    for name, var in variants(row).items():
        dev = {'cent': [], 'db': []} if (row == 'f4' and var[0] == 'sus') else None
        el, em = recon_bands(d, cl, runs, var, dev=dev)
        cs = class_sums(cl, el, em, ms, render=boxes if name == 'base' else None)
        out['v'][name] = cs
        if dev is not None:
            out['v'][name]['dev'] = dict(cent=hist(dev['cent']), db=hist(dev['db']))
    json.dump(out, open(f, 'w'))
    print(row, i, round(time.time() - t), flush=True)
    return a


if __name__ == '__main__':
    jobs = [(r, i) for r in ('f4', 'b3p2', 'b0p0') for i in range(14)]
    with Pool(int(os.environ.get('NP', 12))) as p:
        for _ in p.imap_unordered(job, jobs):
            pass
    print('done', flush=True)
