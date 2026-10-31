"""S19-H: causal high-pass counterfactual on rendered layers. usage: s19h_measure.py ROW[,ROW] [songs]; run via runpy.sh. numbers only."""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/L'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
from pathlib import Path
from scipy.signal import sosfilt, sosfiltfilt, butter
from scipy.ndimage import median_filter
import p_primary as P
import s19l_measure as L
FS = 48000; BOX = 240
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/H/res'); OUT.mkdir(exist_ok=True)


def variants():
    v = {'none': None}
    for fc in (120, 135, 150):
        for n in (4, 8):
            v[f'bw{n}_{fc}'] = butter(n, fc, 'highpass', fs=FS, output='sos')
    s2 = butter(2, 150, 'highpass', fs=FS, output='sos'); v['lr4_150'] = np.vstack([s2, s2])
    return v


def job(a):
    label, i = a
    f = OUT / f'{label}_s{i:02d}.json'
    if f.exists():
        return a
    t = time.time()
    xin = P.read_song(i)
    x, _ = P.render_song(xin, label, with_trace=False); del xin
    res = dict(label=label, song=i, n=len(x), var={})
    segs = L.segs_for(i, len(x))
    for name, sos in variants().items():
        y = x if sos is None else sosfilt(sos, x)
        lo = sosfiltfilt(P.SOS_LO, y); mid = sosfiltfilt(P.SOS_MID, y)
        S = np.fft.rfft(y); fr = np.fft.rfftfreq(len(y), 1 / FS)
        b14 = np.fft.irfft(S * L.ramp_mask(fr, 20, 140), len(y)); del S
        nb = len(y) // BOX
        eb = np.mean(b14[:nb * BOX].reshape(nb, BOX) ** 2, axis=1); rm = median_filter(eb, size=40, mode='nearest')
        sl = []
        for (t0, t1) in segs:
            i0, i1 = int(t0 * FS), int(t1 * FS); b0, b1 = i0 // BOX, i1 // BOX
            e = eb[b0:b1]; r = rm[b0:b1]
            sl.append(dict(t0=t0, p_lo=float(np.mean(lo[i0:i1] ** 2)), p_mid=float(np.mean(mid[i0:i1] ** 2)), fft=L.fft_bands(y[i0:i1]),
                           e140=float(e.mean()), emed=float(np.median(e)),
                           b2=float(e[e > 2 * r].sum() / e.sum()) if e.sum() > 0 else 0.0, eb=e.tolist(), rm=r.tolist()))
        res['var'][name] = sl
    res['sec'] = round(time.time() - t)
    json.dump(res, open(f, 'w')); print(label, i, res['sec'], flush=True)
    return a


if __name__ == '__main__':
    from multiprocessing import Pool
    rows = sys.argv[1].split(',')
    idx = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(14))
    with Pool(int(__import__('os').environ.get('NP', 7))) as p:
        for _ in p.imap_unordered(job, [(l, i) for i in idx for l in rows]):
            pass
