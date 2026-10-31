"""R3 front end: the clean bass stem SUM of each ladder song, rendered through the same engine capture as the mix (bh = selected_h, det = band_delayed191),
so the stem streams share the mix streams' time axis and processing.  Songs: the 10 V6 TRAIN songs (0-30 s) and the T60 V5a excerpt (36-48 s).  Slakh TRAIN only.
usage (from diag16): ./run.sh ../plan16/A/stems.py"""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import multiprocessing as mp
import numpy as np
from data import *

OUTD = HOME / 'r3a-dev/plan16/A'
CACHE_A = OUTD / 'cache'; CACHE_A.mkdir(exist_ok=True)
SONGS = TRAIN + EVAL


def stem_audio(key):
    name, a, b = ('Track00060', 36.0, 48.0) if key == 't60_36_48' else (key, 0.0, 30.0)
    guard(X.SLAKH / name)
    bz, _ = X.bass_stems_and_notes(name)
    seg = np.asarray(bz[int(round(a * FS)):int(round(b * FS))], float)
    seg = np.pad(seg, (0, max(0, int(round((b - a) * FS)) - len(seg))))
    return np.clip(np.stack([seg, seg], 1), -1, 1).astype(np.float32)


def stem_streams(key):
    p = CACHE_A / f's_stem_{key}.npz'
    if p.exists():
        z = np.load(p); return z['bh'], z['det']
    import research_core_metrics as M
    from vb_quality.stage_capture import INDEX as SI
    ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
    r = ctx.render('stem_' + key, stem_audio(key), 0.0, voice=False, stage=True)
    st = r['stage']
    core = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
    bh = np.zeros(core.max() + 1); det = np.zeros_like(bh)
    bh[core] = st[:, SI['selected_h']]; det[core] = st[:, SI['band_delayed191']]
    np.savez_compressed(p, bh=bh, det=det)
    return bh, det


def _j(k):
    stem_streams(k); return k


if __name__ == '__main__':
    t0 = time.time()
    with mp.get_context('fork').Pool(5) as pool:
        for k in pool.imap_unordered(_j, SONGS + ['t60_36_48']):
            print('done', k, round(time.time() - t0, 1), flush=True)
