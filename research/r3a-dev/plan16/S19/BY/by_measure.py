"""S19-BY: per-window (2 s, hop 0.5 s) metrics over a whole song, for rows. numbers only (+ trace/box cache for trace rows on the two test songs).
usage: by_measure.py ROW[,ROW] SONG[,SONG]   ROW in inp,p1,v15,b3p2,hp8_150c1 ; SONG in beyond,beyondE,lastcarn,v00..v13
run via ~/r3a-dev/plan16/V16A/runpy.sh"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/HP'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/L')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly, sosfiltfilt
from scipy.ndimage import median_filter
import p_primary as P
import s19l_measure as L
import s19hp_measure as HM
from b1_mod import mod_series
FS = 48000; BOX = 240; WN = 2 * FS; HOPN = FS // 2
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/BY/res'); OUT.mkdir(exist_ok=True)
CACHE = Path('/home/ksysh/r3a-dev/plan16/S19/BY/cache'); CACHE.mkdir(exist_ok=True)
TW = '/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/'
PATHS = {'beyond': TW + '10. Beyond.flac', 'beyondE': TW + '31 Beyond (English ver.) (Ending Movie).mp3.flac',
         'lastcarn': '/mnt/c/Users/ksysh/Downloads/Norihiro_Tsuru_-_Last_Carnival_Acoustic_Cafe_(mp3.pm).mp3'}
KEEP = ['hop', 'voice', 'state', 'f_track', 'f_osc', 'A', 'c', 'sigma', 'Np', 'a_2', 'a_3', 'theta_hat', 'psi_2', 'psi_3']
TRACE_ROWS = ('b3p2', 'hp8_150c1')


def read(song):
    if song.startswith('v') and song[1:].isdigit():
        return P.read_song(int(song[1:]))
    p = PATHS[song]; assert 'slakh2100' not in p
    x, fs = sf.read(p, always_2d=True, dtype='float64')
    x = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, 1)
    g = np.gcd(fs, FS)
    return np.clip(resample_poly(x, FS // g, fs // g, axis=0), -1, 1).astype(np.float32)


def band_p(X, f, a, b, norm):
    return 2 * float(X[(f >= a) & (f < b)].sum()) / norm


def metrics(x, tag):
    n = len(x); nw = (n - WN) // HOPN + 1
    w = np.hanning(WN); norm = WN * float(np.sum(w ** 2)); f = np.fft.rfftfreq(WN, 1 / FS)
    m140 = (f >= 20) & (f < 140); m150 = (f >= 20) & (f < 150); m600 = (f >= 150) & (f < 600); m260 = (f >= 150) & (f < 260)
    m100 = (f >= 20) & (f < 100)
    R = {k: np.zeros(nw) for k in ('p140', 'p150', 'p100', 'p600', 'p260', 'rms')}
    for k in range(nw):
        seg = x[k * HOPN:k * HOPN + WN]
        X = np.abs(np.fft.rfft(seg * w)) ** 2
        R['p140'][k] = 2 * X[m140].sum() / norm; R['p150'][k] = 2 * X[m150].sum() / norm; R['p100'][k] = 2 * X[m100].sum() / norm
        R['p600'][k] = 2 * X[m600].sum() / norm; R['p260'][k] = 2 * X[m260].sum() / norm; R['rms'][k] = float(np.mean(seg ** 2))
    # burst share of the linear-phase 20-140 band, 5 ms boxes
    S = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / FS)
    b14 = np.fft.irfft(S * L.ramp_mask(fr, 20, 140), n); del S
    nb = n // BOX
    eb = np.mean(b14[:nb * BOX].reshape(nb, BOX) ** 2, axis=1); del b14
    rm = median_filter(eb, size=40, mode='nearest')
    bs = np.zeros(nw)
    for k in range(nw):
        b0 = k * 100; e = eb[b0:b0 + 400]; r = rm[b0:b0 + 400]
        bs[k] = e[e > 2 * r].sum() / max(e.sum(), 1e-30)
    R['burst2'] = bs
    # 2-12 Hz pulsing of the 20-150 Hz envelope
    env = L.env_db(sosfiltfilt(P.SOS_LO, x))
    _, M, _, lev = mod_series(env)
    Mf = np.full(nw, np.nan); Lf = np.full(nw, np.nan); m = min(nw, len(M)); Mf[:m] = M[:m]; Lf[:m] = lev[:m]
    R['M'] = Mf; R['lev150'] = Lf
    return R


def job(a):
    label, song = a
    f = OUT / f'{label}_{song}.npz'
    if f.exists():
        return a
    t = time.time()
    xin = read(song)
    if label == 'inp':
        x = xin.astype(np.float64).mean(1); tr = None
    else:
        x, tr = HM.render_song(xin, label)
        if label not in TRACE_ROWS or song in ('beyondE',) and False:
            tr = None
    n = len(x)
    R = metrics(x, label)
    R['n'] = np.array(n)
    if tr is not None and song in ('beyond', 'lastcarn', 'beyondE') and label in TRACE_ROWS:
        d = H_trace(tr)
        lo = sosfiltfilt(P.SOS_LO, x); nb = len(lo) // BOX
        eb = np.sum(lo[:nb * BOX].reshape(nb, BOX) ** 2, axis=1)
        np.savez_compressed(CACHE / f'tr_{label}_{song}.npz', box=eb, **d)
    np.savez_compressed(f, **R)
    print(label, song, round(time.time() - t), flush=True)
    return a


def H_trace(tr):
    d = HM.CA.trace_dict(tr)
    return {k: d[k].astype(np.float32 if k not in ('hop', 'voice', 'state') else np.int32) for k in KEEP}


if __name__ == '__main__':
    from multiprocessing import Pool
    rows = sys.argv[1].split(','); songs = sys.argv[2].split(',')
    if songs == ['vall']:
        songs = [f'v{i:02d}' for i in range(14)]
    with Pool(int(__import__('os').environ.get('NP', 8))) as p:
        for _ in p.imap_unordered(job, [(l, s) for s in songs for l in rows]):
            pass
