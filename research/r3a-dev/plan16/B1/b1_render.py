"""Render all 14 songs x 3 engines; keep only 5 ms envelopes (not audio) in cache/, traces + layers (tmp, deleted later) for Apparition."""
import sys, os, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1common import *
from multiprocessing import Pool
OUT = B1 / 'cache'; OUT.mkdir(exist_ok=True)
APP = [i for i, p in enumerate(MUSIC) if '08. Apparition' in p][0]


def job(a):
    i, eng = a
    f = OUT / f's{i:02d}_{eng}.npz'
    if f.exists():
        return a, 0
    t = time.time()
    x = read_song(i)
    lay, tr, lat = render(x, eng, trace=(i == APP))
    d = dict(env=band_env(lay, SOS_L).astype(np.float32), lat=lat, n=len(lay))
    if i == APP:
        np.save(OUT / f'app_layer_{eng}.npy', lay.astype(np.float32))
        if tr is not None:
            np.savez_compressed(OUT / f'app_trace_{eng}.npz', **{k: v.astype(np.float32) for k, v in tr.items()})
    np.savez(f, **d)
    if eng == 'P1':
        np.savez(OUT / f's{i:02d}_input.npz', env=band_env(x.mean(1).astype(np.float64), SOS_I).astype(np.float32))
    return a, time.time() - t


if __name__ == '__main__':
    jobs = [(i, e) for i in range(len(MUSIC)) for e in ENGINES]
    jobs.sort(key=lambda a: a[0] != APP)
    with Pool(10) as p:
        for a, dt in p.imap_unordered(job, jobs):
            print(a, round(dt, 1), flush=True)
