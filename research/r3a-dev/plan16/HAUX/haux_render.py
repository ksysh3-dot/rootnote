"""render Apparition + Reminiscence through v1.5 (build_core, algo 15, default16 params), keep the voice trace only (no layer, no audio).  -> tmp/<sk>_v15_trace.npz"""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12common import *
from multiprocessing import Pool
OUT = Path('/home/ksysh/r3a-dev/plan16/HAUX/tmp'); OUT.mkdir(exist_ok=True)


def job(sk):
    t = time.time()
    x = read_song(SONG_IDX[sk])
    lay, tr, h, lat = render(x, 'v15', None)
    np.savez_compressed(OUT / f'{sk}_v15_trace.npz', **{k: v.astype(np.float32) if k not in ('hop',) else v.astype(np.float64) for k, v in tr.items()})
    return sk, time.time() - t, lat, len(x) / FS


if __name__ == '__main__':
    with Pool(2) as p:
        for r in p.imap_unordered(job, list(SONG_IDX)):
            print(r, flush=True)
