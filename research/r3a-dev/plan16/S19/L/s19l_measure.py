"""S19-L: leakage vs real low-band energy. usage: s19l_measure.py ROW[,ROW..] ; results in S19/L/res/ROW_sNN.npz / .json (numbers only)
run via ~/r3a-dev/plan16/V16A/runpy.sh"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
from pathlib import Path
from scipy.signal import sosfiltfilt, butter
from scipy.ndimage import median_filter
import p_primary as P
from b1_mod import mod_series
FS = 48000; BOX = 240
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/L/res'); OUT.mkdir(exist_ok=True)
BANDS = [(20, 60), (60, 100), (100, 130), (130, 150), (150, 200), (200, 300), (300, 600)]
SOS260 = butter(4, [150, 260], 'bandpass', fs=FS, output='sos')
USER_IDX = (6, 9)
EXC0, EXCLEN = 60.0, 30.0


def segs_for(i, n):
    if i in USER_IDX:
        sk = 'rem' if i == 6 else 'app'
        return [(t0, t1) for (s, t0, t1) in P.WINDOWS if s == sk]
    t0 = EXC0
    if t0 + EXCLEN > n / FS - 1.0:
        t0 = n / FS - 1.0 - EXCLEN
    return [(t0, t0 + EXCLEN)] if t0 >= 0 else []


def env_db(sig):
    n = len(sig) // BOX
    r = np.sqrt(np.mean(sig[:n * BOX].reshape(n, BOX) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), -90.0)


def ramp_mask(f, lo, hi, w=10.0):
    up = np.clip((f - (lo - w / 2)) / w, 0, 1); dn = np.clip(((hi + w / 2) - f) / w, 0, 1)
    return 0.5 * (1 - np.cos(np.pi * up)) * 0.5 * (1 - np.cos(np.pi * dn)) * 1.0


def measure(x, inp_mono=None):
    """x: mono float64 layer (or input). returns dict of per-segment results."""
    n = len(x)
    S = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / FS)
    ab = np.fft.irfft(np.where(f >= 150, S, 0), n); be = np.fft.irfft(np.where(f < 150, S, 0), n)
    lo = sosfiltfilt(P.SOS_LO, x); mid = sosfiltfilt(P.SOS_MID, x)
    lo_ab = sosfiltfilt(P.SOS_LO, ab); lo_be = sosfiltfilt(P.SOS_LO, be)
    m = ramp_mask(f, 20, 140)
    b14 = np.fft.irfft(S * m, n); del S
    nb = n // BOX
    eb = np.mean(b14[:nb * BOX].reshape(nb, BOX) ** 2, axis=1)
    rm = median_filter(eb, size=40, mode='nearest')
    env260 = env_db(sosfiltfilt(SOS260, x))
    return dict(lo=lo, mid=mid, lo_ab=lo_ab, lo_be=lo_be, eb=eb, rm=rm, env260=env260, env600=env_db(mid))


def fft_bands(seg):
    w = np.hanning(len(seg)); X = np.abs(np.fft.rfft(seg * w)) ** 2; f = np.fft.rfftfreq(len(seg), 1 / FS)
    bd = {f'{a}-{b}': float(X[(f >= a) & (f < b)].sum()) for a in (20, 60, 100, 130, 150, 200, 300) for b in (60, 100, 130, 150, 200, 300, 600) if (a, b) in BANDS}
    bd['150-260'] = float(X[(f >= 150) & (f < 260)].sum()); bd['20-140'] = float(X[(f >= 20) & (f < 140)].sum())
    return bd


def job(a):
    label, i = a
    f = OUT / f'{label}_s{i:02d}.json'
    if f.exists():
        return a
    t = time.time()
    xin = P.read_song(i)
    if label == 'inp':
        x = xin.astype(np.float64).mean(1)
    else:
        x, _ = P.render_song(xin, label, with_trace=False)
    xi = xin.astype(np.float64).mean(1)[:len(x)]
    n = min(len(x), len(xi)); x = x[:n]; xi = xi[:n]
    M = measure(x)
    env_in = env_db(sosfiltfilt(SOS260, xi))
    res = dict(label=label, song=i, n=n, segs=[])
    boxes = {}
    for k, (t0, t1) in enumerate(segs_for(i, n)):
        i0, i1 = int(t0 * FS), int(t1 * FS)
        d = dict(t0=t0, t1=t1)
        d['p_lo'] = float(np.mean(M['lo'][i0:i1] ** 2)); d['p_mid'] = float(np.mean(M['mid'][i0:i1] ** 2))
        d['e_ab'] = float(np.mean(M['lo_ab'][i0:i1] ** 2)); d['e_be'] = float(np.mean(M['lo_be'][i0:i1] ** 2))
        d['fft'] = fft_bands(x[i0:i1])
        b0, b1 = i0 // BOX, i1 // BOX
        eb = M['eb'][b0:b1]; rm = M['rm'][b0:b1]
        boxes[f'eb{k}'] = eb; boxes[f'rm{k}'] = rm
        # item 5 modulation: env at 200 Hz
        e0, e1 = int(round(t0 * 200)), int(round(t1 * 200))
        tt, Ml, pk, lev = mod_series(M['env260'][e0:e1]); _, Mi, _, levi = mod_series(env_in[e0:e1])
        levm = mod_series(M['env600'][e0:e1])[3]
        d['mod'] = dict(levm=levm.tolist(), t=(tt + t0).tolist(), Ml=Ml.tolist(), Mi=Mi.tolist(), lev=lev.tolist())
        res['segs'].append(d)
    np.savez_compressed(OUT / f'{label}_s{i:02d}_boxes.npz', **boxes)
    # level of the layer's 150-600 mean envelope power per 2 s window for eligibility (B1 uses sos 150-600 env): store mid-band env level
    res['sec'] = round(time.time() - t)
    json.dump(res, open(f, 'w'))
    print(label, i, res['sec'], flush=True)
    return a


if __name__ == '__main__':
    from multiprocessing import Pool
    rows = sys.argv[1].split(',')
    idx = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(len(P.MUSIC)))
    with Pool(int(__import__('os').environ.get('NP', 7))) as p:
        for _ in p.imap_unordered(job, [(l, i) for i in idx for l in rows]):
            pass

