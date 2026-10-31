"""S19-D step 1: render songs with a row, save trace (selected fields) + 5 ms box energy of the 20-150 Hz layer. numbers only, no audio.
usage: s19_render.py ROW SONGIDX [SONGIDX...]  (cache in S19/cache)"""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
from pathlib import Path
from scipy.signal import sosfiltfilt
import p_primary as P
CA = P.CA
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/cache'); OUT.mkdir(exist_ok=True)
KEEP = ['hop', 'voice', 'state', 'f_track', 'f_osc', 'A', 'c', 'sigma', 'Np', 'a_2', 'a_3', 'theta_hat', 'psi_2', 'psi_3']
BOX = 240

def job(a):
    label, i = a
    f = OUT / f'r_{label}_s{i:02d}.npz'
    if f.exists():
        return a
    t = time.time()
    lay, tr = P.render_song(P.read_song(i), label)
    lo = sosfiltfilt(P.SOS_LO, lay)
    n = len(lo) // BOX
    eb = np.sum(lo[:n * BOX].reshape(n, BOX) ** 2, axis=1)
    np.savez_compressed(f, box=eb.astype(np.float64), **{k: tr[k].astype(np.float32 if k not in ('hop', 'voice', 'state') else np.int32) for k in KEEP})
    print(label, i, round(time.time() - t), flush=True)
    return a

if __name__ == '__main__':
    from multiprocessing import Pool
    rows = sys.argv[1].split(',')
    idx = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(len(P.MUSIC)))
    with Pool(int(__import__('os').environ.get('NP', 10))) as p:
        for _ in p.imap_unordered(job, [(l, i) for l in rows for i in idx]):
            pass