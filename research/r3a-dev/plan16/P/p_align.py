"""Time alignment of the captured output layer (cache/layer_*.npy, index i = output sample after removing the engine latency 7140)
against the trace-based layer (the 16.9 construction: voices shifted by LAGS, 3 kHz synthesis, F gain), per song and engine.
Also the energy scale kappa between the two (150-700 Hz band, t >= 0.5 s).  Reads/writes P/ only.
usage: ~/r3a-dev/plan16/D/runpy.sh ~/r3a-dev/plan16/P/p_align.py"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
import multiprocessing as mp
from scipy.signal import butter, sosfiltfilt
import dcommon as DC
from dcommon import *

P_DIR = HOME / 'r3a-dev/plan16/P'; CACHE = P_DIR / 'cache'
BAND = (150.0, 700.0)
SOS48 = butter(4, BAND, 'bandpass', fs=48000, output='sos')
SOS3 = butter(4, BAND, 'bandpass', fs=3000, output='sos')
MAXLAG = 120                  # +-40 ms at 3 kHz


def env3(x, fs_ratio):
    """band-limited squared signal, 10 ms boxcar, at 3 kHz"""
    return x


def one(key):
    sig = Sig(key); dur = 30.0
    out = {}
    for algo, rowf, lagk in ((15, R.voices_core, 'core'), (6, R.voices_p1, 'p1')):
        vo = E.shift(rowf(sig), LAGS[lagk])
        Y = render_multi(vo, dur + 0.3, lambda v, tt, f, a: np.zeros(len(tt), int), 1)[0]
        yt = sosfiltfilt(SOS3, Y)
        e_tr = yt ** 2
        lay = np.load(CACHE / f'layer_{key}_{algo}.npy').astype(np.float64)
        bl = sosfiltfilt(SOS48, lay)
        e_cap48 = bl ** 2
        # captured energy on the 3 kHz grid (mean of 16 samples), and envelopes with a 10 ms boxcar
        n3 = len(lay) // 16
        e_cap = e_cap48[:n3 * 16].reshape(n3, 16).mean(1)             # mean power per 3 kHz interval (sum over intervals is comparable to the 3 kHz sum of squares)
        k = np.ones(30) / 30
        a = np.convolve(e_cap, k, 'same'); b = np.convolve(e_tr, k, 'same')
        n = min(len(a), len(b))
        i0, i1 = int(4 * FSC), min(n, int(30 * FSC)) - MAXLAG
        a_ = a[i0:i1] ** 0.5; best = None; cc = []
        for d in range(-MAXLAG, MAXLAG + 1):
            b_ = b[i0 + d:i1 + d] ** 0.5                     # b_[t] = trace envelope at t + d
            cc.append(float(np.corrcoef(a_, b_)[0, 1]) if a_.std() > 0 and b_.std() > 0 else float('nan'))
        cc = np.array(cc)
        if np.isfinite(cc).any():
            j = int(np.nanargmax(cc)); d_best = j - MAXLAG
            # parabolic refinement
            if 0 < j < len(cc) - 1 and np.isfinite(cc[j - 1:j + 2]).all():
                den = cc[j - 1] - 2 * cc[j] + cc[j + 1]
                frac = 0.5 * (cc[j - 1] - cc[j + 1]) / den if den != 0 else 0.0
            else:
                frac = 0.0
            # d>0: trace envelope at t+d matches captured at t  => captured layer is EARLIER than trace by d/3000 s;  d<0 => captured later
            out[algo] = dict(d_samples=float(d_best + frac), delta_ms=float(-(d_best + frac) / 3.0), corr_at0=float(cc[MAXLAG]), corr_best=float(cc[j]))
        else:
            out[algo] = dict(d_samples=float('nan'), delta_ms=float('nan'), corr_at0=float('nan'), corr_best=float('nan'))
        m = slice(int(0.5 * FSC), min(n3, len(e_tr)))
        out[algo]['E_cap'] = float(e_cap[m].sum()); out[algo]['E_trace'] = float(e_tr[m].sum())
    print(key, {a: (round(v['delta_ms'], 2), round(v['corr_at0'], 3), round(v['corr_best'], 3)) for a, v in out.items()}, flush=True)
    return key, out


if __name__ == '__main__':
    songs = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
    with mp.get_context('fork').Pool(10) as pool:
        res = dict(pool.map(one, songs))
    json.dump(res, open(P_DIR / 'align_raw.json', 'w'), indent=1, default=float)
    for algo in (15, 6):
        d = np.array([res[k][algo]['delta_ms'] for k in songs])
        print('algo', algo, 'delta_ms (positive = captured layer LATER than the trace layer) per song', np.round(d, 2), 'median', np.nanmedian(d))
        ec = sum(res[k][algo]['E_cap'] for k in songs); et = sum(res[k][algo]['E_trace'] for k in songs)
        print('   pooled E_cap/E_trace', ec / et)
