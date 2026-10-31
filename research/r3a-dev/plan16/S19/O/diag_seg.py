"""S19-O extra diagnostic (not in the spec, added after seeing the main result): where does the baseline no-event recon energy sit relative to the sustain segments,
and how much do the d / b32 / c32 variants change it inside vs outside segments. Row f4."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from s19o_lib import *
from multiprocessing import Pool
db = lambda x: 10 * np.log10(max(x, 1e-300))


def job(i):
    d, boxes = load('f4', i)
    cl = classify(d, boxes)
    sk = {v: k for k, v in P.SONG_IDX.items()}.get(i)
    ms = masks(cl, len(boxes), sk)
    runs = make_runs(d, cl)
    H, S = d['state'].shape
    inseg = np.zeros((H, S), bool)
    for r in runs:
        for (s0, s1) in r['segs']:
            inseg[r['idx'][s0:s1 + 1], r['s']] = True
    w = d['_E']; hn = cl['hn']
    top = np.argmax(w[hn], 1)
    cat = np.where(inseg[hn, top], 0, np.where(d['state'][hn, top] == 2, 1, np.where(d['state'][hn, top] == 3, 2, 3)))   # 0 seg, 1 ON outside seg, 2 REL, 3 other
    base = recon_bands(d, cl, runs, ('base',))[0]
    res = {}
    vs = {'base': base}
    for nm, v in (('d1', ('sus', 1, True, True, False)), ('b32', ('sus', 32, False, True, False)), ('b4', ('sus', 4, False, True, False))):
        vs[nm] = recon_bands(d, cl, runs, v)[0]
    for mk, m in ms.items():
        ne = m & (cl['ex'] == NT)
        r = {}
        for c in range(4):
            mm = ne & (cat == c)
            r[f'cat{c}'] = {k: float(v[hn][mm].sum()) for k, v in vs.items()}
        r['all_ne'] = {k: float(v[hn][ne].sum()) for k, v in vs.items()}
        r['n_ne'] = int(ne.sum())
        res[mk] = r
    return i, res


if __name__ == '__main__':
    with Pool(12) as p:
        R = dict(p.map(job, range(14)))
    names = ['in sustain segment', 'ON, outside segment (warm-up/cut)', 'REL', 'other(CAND)']
    def agg(keys):
        out = {}
        for mk, idxs in keys:
            tot = {c: {k: sum(R[i][mk][c][k] for i in idxs) for k in ('base', 'd1', 'b32', 'b4')} for c in ('cat0', 'cat1', 'cat2', 'cat3', 'all_ne')}
            out[mk] = tot
        return out
    lines = []
    for label, mk, idxs in (('7 windows pooled', 'win', (9, 6)), ('14 songs pooled (energy-weighted)', 'song', tuple(range(14)))):
        T = {c: {k: sum(R[i][mk][c][k] for i in idxs) for k in ('base', 'd1', 'b32', 'b4')} for c in ('cat0', 'cat1', 'cat2', 'cat3', 'all_ne')}
        lines.append(f'[{label}] baseline noevent recon energy by state of the top voice; dB change of d1 / b32 / b4 in that part')
        for c, nm in zip(('cat0', 'cat1', 'cat2', 'cat3'), names):
            lines.append(f'  {nm:36s} share {100*T[c]["base"]/T["all_ne"]["base"]:5.1f}%   d1 {db(T[c]["d1"]/max(T[c]["base"],1e-300)):+.2f}  b32 {db(T[c]["b32"]/max(T[c]["base"],1e-300)):+.2f}  b4 {db(T[c]["b4"]/max(T[c]["base"],1e-300)):+.2f} dB')
        lines.append(f'  all noevent: d1 {db(T["all_ne"]["d1"]/T["all_ne"]["base"]):+.2f} b32 {db(T["all_ne"]["b32"]/T["all_ne"]["base"]):+.2f} b4 {db(T["all_ne"]["b4"]/T["all_ne"]["base"]):+.2f} dB')
    open('/home/ksysh/r3a-dev/plan16/S19/O/diag_seg.txt', 'w').write('\n'.join(lines))
    print('\n'.join(lines))
