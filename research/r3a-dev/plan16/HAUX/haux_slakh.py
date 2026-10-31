"""HAUX stage 0, Slakh part: aux features per voice-hop (CHOICES.md sections 1-2).  usage: runpy.sh haux_slakh.py  -> cache/feat_<song>_p<part>.npz"""
import os, sys, time
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import numpy as np
import multiprocessing as mp
import kcommon as K
from kcommon import *
import haux_lib as H
from pathlib import Path

OUT = Path('/home/ksysh/r3a-dev/plan16/HAUX/cache'); OUT.mkdir(exist_ok=True)
NPART = 3
MULTS = (0.5, 1.0, 2.0, 3.0)


def truth_f(segs, T, f):
    """segment sounding at T (lowest bass note) and the multiplier putting f nearest to m f_midi; returns (f_midi, m) or (nan, nan)"""
    for sg in segs:
        if sg['s'] <= T < sg['e']:
            best = (1e9, np.nan)
            for m in MULTS:
                c = abs(1200 * np.log2(f / (m * sg['f'])))
                if c < best[0]:
                    best = (c, m)
            return float(sg['f']), float(best[1])
    return np.nan, np.nan


def job(a):
    key, part = a
    t0 = time.time()
    ctx = K.SongCtx(key, probe_nobass=False)
    x = np.asarray(DATA.audio(key), float)
    x = x.mean(1) if x.ndim == 2 else x
    rows = []
    for vi, v in enumerate(ctx.voices):
        if not v['ok'] or vi % NPART != part:
            continue
        ctx.k_arrays(v)
        cls = v['cls']
        for i in range(len(v['T'])):
            if v['A'][i] <= 0 or v['ftr'][i] <= 0:
                continue
            j = int(np.clip(round(v['T'][i] * FSC) - v['i0'], 0, len(v['comp']) - 1))
            comp = int(v['comp'][j])
            if not ((cls == 0) or (cls == 1 and comp == 2) or (cls == 2 and comp >= 3)):
                continue
            rows.append((vi, i, cls, comp))
    n = len(rows)
    res = dict(vi=np.zeros(n, int), i=np.zeros(n, int), h=np.zeros(n, int), T=np.zeros(n), fosc=np.zeros(n), ftr=np.zeros(n), amp=np.zeros(n),
               cls=np.zeros(n, int), comp=np.zeros(n, int), w=np.zeros(n, int), ftrue=np.full(n, np.nan), mult=np.full(n, np.nan), K2=np.zeros(n, np.int8))
    for W in (40, 85):
        for nm in ('E_t', 'Ei_t', 'E_h', 'Ei_h'):
            res[f'{nm}{W}'] = np.full((n, H.NK), np.nan, np.float32)
        res[f'a1_t{W}'] = np.full(n, np.nan, np.float32)
        res[f'fh{W}'] = np.full(n, np.nan)
        res[f'sc{W}'] = np.full(n, np.nan)
    for r, (vi, i, cls, comp) in enumerate(rows):
        v = ctx.voices[vi]
        T = float(v['T'][i]); ftr = float(v['ftr'][i])
        res['vi'][r] = vi; res['i'][r] = i; res['h'][r] = int(v['hs'][i]); res['T'][r] = T
        res['fosc'][r] = float(v['f'][1:-1][i]); res['ftr'][r] = ftr; res['amp'][r] = float(v['A'][i])
        res['cls'][r] = cls; res['comp'][r] = comp; res['w'][r] = int(v.get('w', -1))
        res['ftrue'][r], res['mult'][r] = truth_f(ctx.segs, T, ftr)
        res['K2'][r] = int(k2_at(ctx, v, i))
        c = int(round(T * H.FS))
        for W in (40, 85):
            L = H.WINLEN[W]; w = H.hann(L)
            seg = H.segment(x, c, L)
            E, Ei, a = H.comb_fit(seg, w, ftr)
            res[f'E_t{W}'][r] = E; res[f'Ei_t{W}'][r] = Ei; res[f'a1_t{W}'][r] = a[0]
            X = H.spec_amp(seg, w)
            fh, sc = H.comb_f0(X, ftr)
            res[f'fh{W}'][r] = fh; res[f'sc{W}'][r] = sc
            E2, Ei2, _ = H.comb_fit(seg, w, fh)
            res[f'E_h{W}'][r] = E2; res[f'Ei_h{W}'][r] = Ei2
    np.savez_compressed(OUT / f'feat_{key}_p{part}.npz', **res)
    print(key, part, n, 'rows', round(time.time() - t0, 1), 's', flush=True)
    return key, part, n


if __name__ == '__main__':
    t0 = time.time()
    tasks = [(k, p) for k in SONGS for p in range(NPART)]
    with mp.get_context('fork').Pool(15) as pool:
        out = list(pool.imap_unordered(job, tasks))
    print('done', round(time.time() - t0, 1))
