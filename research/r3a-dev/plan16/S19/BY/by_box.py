"""S19-BY: 5 ms box sums of the linear-phase 20-140 Hz band of the v1.6-c layer (whole song), numbers only. usage: by_box.py SONG[,SONG] ; run via runpy.sh"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/BY')
import numpy as np
import by_measure as M
L = M.L; HM = M.HM


def job(song):
    x, _ = HM.render_song(M.read(song), 'hp8_150c1')
    n = len(x); S = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / M.FS)
    b = np.fft.irfft(S * L.ramp_mask(fr, 20, 140), n); nb = n // M.BOX
    np.save(M.CACHE / f'box140_{song}.npy', np.sum(b[:nb * M.BOX].reshape(nb, M.BOX) ** 2, axis=1))
    print(song, flush=True)
    return song


if __name__ == '__main__':
    from multiprocessing import Pool
    ss = sys.argv[1].split(',')
    with Pool(len(ss)) as p:
        list(p.imap_unordered(job, ss))
