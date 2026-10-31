"""Render Apparition + Reminiscence x {P1, v15, v16b}; keep layer (tmp), trace (npz), P1 harmonic rows near windows."""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12common import *
from multiprocessing import Pool

TMP.mkdir(exist_ok=True)


def job(a):
    sk, eng = a
    t = time.time()
    x = read_song(SONG_IDX[sk])
    lay, tr, h, lat = render(x, eng, [w for w in WINDOWS + EXT if w[0] == sk])
    np.save(TMP / f'{sk}_{eng}_layer.npy', lay.astype(np.float32))
    if tr is not None:
        np.savez_compressed(TMP / f'{sk}_{eng}_trace.npz', **{k: v.astype(np.float32) for k, v in tr.items()})
    if h is not None:
        np.savez_compressed(TMP / f'{sk}_{eng}_harm.npz', rows=h)
    return a, time.time() - t, lat


if __name__ == '__main__':
    jobs = [(s, e) for s in SONG_IDX for e in ENGINES]
    with Pool(6) as p:
        for r in p.imap_unordered(job, jobs):
            print(r, flush=True)
