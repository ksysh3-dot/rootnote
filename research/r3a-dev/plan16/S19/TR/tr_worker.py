"""S19-TR worker: tr_worker.py IDX. Saves numbers to res/. Definitions: CHOICES.md"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/LIM')
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfiltfilt, sosfilt
import lim_lib as Z
import soundfile as sf
from scipy.signal import resample_poly
FS = Z.FS
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/TR/res'); OUT.mkdir(exist_ok=True)
RAY = Path('/mnt/c/Users/ksysh/Music/Rayark 10th Anniversary Concert Collection(Origina [214852792] [2022]/')
VAN = Path('/mnt/c/Users/ksysh/Music/vanila')
SONGS = [('v', p) for p in sorted(VAN.glob('*.flac'))] + [('r', p) for p in sorted(RAY.glob('*.flac'))]
ROWS = ['p1', 'v15', 'v16c']
B = {k: butter(4, v, 'bandpass', fs=FS, output='sos') for k, v in {'mid': [150, 600], 'a': [150, 200], 'b': [200, 300]}.items()}
FR = 4800
# BS.1770 K-weighting at 48 kHz
KS = np.array([[1.53512485958697, -2.69169618940638, 1.19839281085285, 1.0, -1.69065929318241, 0.73248077421585],
               [1.0, -2.0, 1.0, 1.0, -1.99004745483398, 0.99007225036621]])


def kw(x):
    return sosfilt(KS, x)


def read(p):
    assert 'slakh2100' not in str(p)
    x, fs = sf.read(str(p), always_2d=True, dtype='float64'); x = x[:, :2]
    g = np.gcd(fs, FS)
    return np.clip(resample_poly(x, FS // g, fs // g, axis=0), -1, 1).astype(np.float32)


def main(idx):
    t = time.time(); g, p = SONGS[idx]
    x = read(p); dur = len(x) / FS
    if dur < 90:
        t0, t1 = 0.0, dur
    else:
        t0, t1 = 30.0, 90.0
    x = x[:int(t1 * FS)]
    R = {}
    for row in ROWS:
        yL, grL, _, lat = Z.run(x, row, 0.0, twin=False)
        yU, grU, lay, lat2 = Z.run(x, row, 0.0, twin=True, capture=True)
        assert lat == lat2
        a, b = int(t0 * FS), int(t1 * FS)
        m = lay.mean(1).astype(np.float64)[lat:]
        d = {}
        for k in B:
            d[k] = sosfiltfilt(B[k], m)[a:b]
        d['yL'] = yL.mean(1).astype(np.float64)[lat:][a:b]; d['yU'] = yU.mean(1).astype(np.float64)[lat:][a:b]
        R[row] = d
    n = min(len(R[r]['mid']) for r in ROWS)
    nf = n // FR
    fm = R['p1']['mid'][:nf * FR].reshape(nf, FR)
    lev = 10 * np.log10(np.mean(fm ** 2, 1) + 1e-20)
    el = lev > -70.0

    def fe(s):
        return np.sum(s[:nf * FR].reshape(nf, FR)[el] ** 2)
    res = dict(song=idx, group=g, name=p.name, dur=dur, nframes=int(nf), n_elig=int(el.sum()), t0=t0, t1=t1)
    for row in ROWS:
        d = R[row]
        res[row] = dict(E={k: float(fe(d[k])) for k in B})
        for o in ('yL', 'yU'):
            kx = kw(d[o])
            res[row][o] = dict(rms_el=float(fe(d[o])), rms_all=float(np.sum(d[o][:nf * FR] ** 2)), k_el=float(fe(kx)), k_all=float(np.sum(kx[:nf * FR] ** 2)))
    json.dump(res, open(OUT / f's{idx:02d}.json', 'w'))
    print(idx, g, p.name, round(time.time() - t), 'elig', int(el.sum()), '/', nf, flush=True)


if __name__ == '__main__':
    main(int(sys.argv[1]))
