"""SUPPLEMENTARY (post hoc, flagged): same renders, 20-150 Hz layer band envelope (+ input 40-150 Hz). Not in CHOICES' registered measure."""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1common import *
from multiprocessing import Pool
OUT = B1 / 'cache'
SOS_LO = butter(4, [20, 150], 'bandpass', fs=FS, output='sos')
SOS_IL = butter(4, [40, 150], 'bandpass', fs=FS, output='sos')


def job(a):
    i, eng = a
    f = OUT / f's{i:02d}_{eng}_lo.npz'
    if f.exists():
        return a, 0
    t = time.time()
    x = read_song(i)
    lay, _, lat = render(x, eng)
    np.savez(f, env=band_env(lay, SOS_LO).astype(np.float32))
    if eng == 'P1':
        np.savez(OUT / f's{i:02d}_input_lo.npz', env=band_env(x.mean(1).astype(np.float64), SOS_IL).astype(np.float32))
    return a, time.time() - t


if __name__ == '__main__':
    jobs = [(i, e) for i in range(len(MUSIC)) for e in ENGINES]
    with Pool(10) as p:
        for a, dt in p.imap_unordered(job, jobs):
            print(a, round(dt, 1), flush=True)
