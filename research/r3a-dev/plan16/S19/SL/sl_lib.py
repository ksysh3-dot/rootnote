"""S19-SL helpers (definitions: CHOICES.md). Numbers only; no audio is written."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/BY')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/HP'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/L')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import butter, sosfilt, sosfiltfilt, lfilter, lfilter_zi, resample_poly
import by_measure as BM
import s19hp_measure as HM
import s19_attr as A
import p_primary as P

FS = 48000; CFS = 3000; HOPS = 16; T0 = 1359.0 / 48000.0; OFF = 398
SL = Path('/home/ksysh/r3a-dev/plan16/S19/SL'); RES = SL / 'res'; RES.mkdir(exist_ok=True)
RAY = Path('/mnt/c/Users/ksysh/Music/Rayark 10th Anniversary Concert Collection(Origina [214852792] [2022]/')
BASE = dict(HM.H.B3P2, layerHpHz=150, layerHpOrder=8, layerHpComp=1)
HM.ROWS['v16c'] = ('build_core19', 15, BASE, 22)
HM.ROWS['nf48'] = ('build_core19', 15, dict(BASE, nFuture=48), 22)
BP260_48 = butter(4, [150, 260], 'bandpass', fs=FS, output='sos')
BP260_3 = butter(4, [150, 260], 'bandpass', fs=CFS, output='sos')
HP3 = butter(8, 150, 'highpass', fs=CFS, output='sos')
# core output band filter (pvb_vb_tables.h kOutSos, 3 kHz): the engine applies it before the layer HP; by_attr.rebuild omitted it
OUT3 = np.array([0.6620158372026176, -1.3240316744052352, 0.6620158372026176, 1.0, -1.4796742169311934, 0.5558215432824889,
                 1.0, -2.0, 1.0, 1.0, -1.7009643319435257, 0.7884997398152979,
                 0.20657208382614792, 0.41314416765229584, 0.20657208382614792, 1.0, -0.3695273773512414, 0.19581571265583306]).reshape(3, 6)
TW = '/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/'
USER = [('v09', 52.0), ('v09', 88.5), ('v09', 123.5), ('v09', 201.0), ('v09', 203.0), ('v06', 96.0), ('v06', 113.0)]
BEY = [('beyond', t) for t in (193.0, 237.0, 239.5, 91.5)]       # 3:13.0 3:57.0 3:59.5 1:31.5
LCA = [('lastcarn', t) for t in (63.5, 137.0, 56.5, 178.0)]      # 1:03.5 2:17.0 0:56.5 2:58.0
DEV = USER + BEY + LCA
DEVSONGS = ['v09', 'v06', 'beyond', 'lastcarn']
WIN = 2.0
db = lambda p: 10 * np.log10(np.maximum(p, 1e-30))


# ------------------------------------------------------------------ reading
def read_any(key):
    if key.startswith('r') and key[1:].isdigit():
        p = sorted(RAY.glob('*.flac'))[int(key[1:])]
        assert 'slakh2100' not in str(p)
        x, fs = sf.read(str(p), always_2d=True, dtype='float64'); x = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, 1)
        g = np.gcd(fs, FS)
        return np.clip(resample_poly(x, FS // g, fs // g, axis=0), -1, 1).astype(np.float32)
    return BM.read(key)      # vNN / beyond / lastcarn


# ------------------------------------------------------------------ metrics
def hann_bands(seg, fs):
    """Hann-FFT band levels as BY/by_measure.metrics: 2*sum|X|^2/(N*sum w^2). returns dict of power (linear)"""
    n = len(seg); w = np.hanning(n); norm = n * float(np.sum(w ** 2)); f = np.fft.rfftfreq(n, 1 / fs)
    X = np.abs(np.fft.rfft(seg * w)) ** 2
    bp = lambda a, b: 2 * float(X[(f >= a) & (f < b)].sum()) / norm
    return dict(m1=bp(20, 140), m4=bp(150, 600), b260=bp(150, 260))


def env_db_box(sig, box):
    n = len(sig) // box
    r = np.sqrt(np.mean(sig[:n * box].reshape(n, box) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), -90.0)


_ER = 200.0; _WIN = 400; _NFFT = 2048; _W = np.hanning(_WIN); _FR = np.fft.rfftfreq(_NFFT, 1 / _ER)
_BAND = (_FR >= 2) & (_FR <= 30); _BAND12 = (_FR >= 2) & (_FR <= 12)


def modM(env):
    """M (dB-rms units) of one 2 s envelope window (400 samples @200 Hz), band 2-30 Hz; also 2-12 Hz"""
    s = env.astype(np.float64); x = (s - s.mean()) * _W
    Pn = np.abs(np.fft.rfft(x, _NFFT)) ** 2 / (_NFFT * np.sum(_W ** 2)) * 2.0
    return float(np.sqrt(Pn[_BAND].sum())), float(np.sqrt(Pn[_BAND12].sum()))


def mod_windows(env, starts):
    """M30 / M12 for windows starting at env index 'starts'"""
    out = [modM(env[s:s + _WIN]) for s in starts]
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])


def win_metrics_real(x, xin_mono, segs):
    """real-layer metrics on windows (list of t0) from whole-song mono layer x (48 kHz) and the input mono; band envelopes of the whole signal"""
    el = env_db_box(sosfiltfilt(BP260_48, x), 240); ei = env_db_box(sosfiltfilt(BP260_48, xin_mono), 240)
    out = []
    for t0 in segs:
        i0 = int(round(t0 * FS)); seg = x[i0:i0 + int(WIN * FS)]
        d = hann_bands(seg, FS)
        e0 = int(round(t0 * 200))
        Ml, Ml12 = modM(el[e0:e0 + _WIN]); Mi, Mi12 = modM(ei[e0:e0 + _WIN])
        d.update(Ml=Ml, Mi=Mi, Ml12=Ml12, Mi12=Mi12, ims=float(np.mean(xin_mono[i0:i0 + int(WIN * FS)] ** 2)))
        out.append(d)
    return out


# ------------------------------------------------------------------ trace -> reconstruction
def trace_of(tr):
    return BM.H_trace(tr)


def sustain_flags(d, nmin=6):
    """sustain (H,S) bool: state ON, >= nmin hops after the last start event (birth / REL>ON / note_chg); ON>REL, release end it"""
    ev, _ = A.events(d)
    st = d['state']; H, S = st.shape
    start = ev['birth'] | ev['REL>ON'] | ev['note_chg']
    sus = np.zeros((H, S), bool)
    for s in range(S):
        c = 0; stc = st[:, s]; sc = start[:, s]
        col = np.zeros(H, bool)
        for i in range(H):
            if stc[i] != 2:
                c = 0
            elif sc[i]:
                c = 0
            else:
                c += 1
            if stc[i] == 2 and c >= nmin:
                col[i] = True
        sus[:, s] = col
    return sus


def _segments(flag):
    """runs of True in a 1-D bool array -> list of (i0, i1)"""
    f = np.concatenate([[False], flag, [False]]).astype(np.int8)
    dd = np.diff(f)
    return list(zip(np.where(dd == 1)[0], np.where(dd == -1)[0]))


def smooth_series(seg, kind, T_ms, R=3):
    L = len(seg); hop = HOPS / CFS
    if L < 2:
        return seg.copy()
    def pole(x, tau, zi0=None):
        al = 1 - np.exp(-hop / tau); b = [al]; a = [1, -(1 - al)]
        zi = lfilter_zi(b, a)
        return lfilter(b, a, x, zi=zi * x[0])[0]
    tau = T_ms / 1000.0
    if kind == 'zp':
        y = pole(seg, tau); y = pole(y[::-1], tau)[::-1]
    elif kind == 'c1':
        y = pole(seg, tau)
    elif kind == 'c2':
        y = pole(pole(seg, tau / 2), tau / 2)
    else:
        raise ValueError(kind)
    j = np.arange(L)
    w = np.minimum(1.0, np.minimum(j / R, (L - 1 - j) / R)); w = np.clip(w, 0, 1)
    return seg + w * (y - seg)


def smooth_amp(d, sus, key, kind, T_ms):
    a = d[key].astype(np.float64).copy(); out = a.copy()
    H, S = a.shape
    for s in range(S):
        for (i0, i1) in _segments(sus[:, s]):
            out[i0:i1, s] = smooth_series(a[i0:i1, s], kind, T_ms)
    return out


def rebuild(d, a2, a3, hp=True):
    """k=2 + k=3 of all slots (by_attr.rebuild logic, vectorised), summed, at 3 kHz; optional causal HP8 150 Hz. returns y indexed by core sample"""
    ih = d['hop'][:, 0].astype(np.int64); st = d['state']; vid = d['voice']; H, S = st.shape
    j16 = np.arange(16) / 16.0; ar = np.arange(16)
    y = np.zeros(int(ih.max()) + 64)
    th_all = d['theta_hat'].astype(np.float64); ps_all = (d['psi_2'].astype(np.float64), d['psi_3'].astype(np.float64))
    am_all = (a2, a3)
    for s in range(S):
        act = st[:, s] >= 1
        brk = np.ones(H, bool); brk[1:] = (vid[1:, s] != vid[:-1, s]) | ~act[:-1]
        i = 0
        while i < H:
            if not act[i]:
                i += 1; continue
            j = i + 1
            while j < H and act[j] and vid[j, s] == vid[i, s]:
                j += 1
            if j - i >= 2:
                sl = slice(i, j); th = th_all[sl, s]
                t0 = np.remainder(th[:-1] + np.pi, 2 * np.pi) - np.pi; dth = (th[1:] - th[:-1]) / 16.0
                ph = t0[:, None] + dth[:, None] * ar[None, :]
                pos = ih[i + 1:j][:, None] + ar[None, :]
                for kk, ps, am in ((2, ps_all[0], am_all[0]), (3, ps_all[1], am_all[1])):
                    a = am[sl, s]; p = ps[sl, s]
                    aa = a[:-1, None] + (a[1:] - a[:-1])[:, None] * j16[None, :]
                    pp = p[:-1, None] + (p[1:] - p[:-1])[:, None] * j16[None, :]
                    y[pos] += aa * np.cos(kk * ph + pp)
            i = j
    if not hp:
        return y
    return sosfilt(HP3, sosfilt(OUT3, y))     # engine order (pvb_vb52.cpp:1082-1083): output band filter kOutSos, then the layer HP


LAG = [22]   # core samples; calibrated per song by find_lag (test_recon: +22 on Last Carnival)


def core_idx(t):
    return int(round((t - T0) * CFS)) + OFF + LAG[0]


def find_lag(x, y, t0, span=60):
    """lag (core samples) maximising the correlation of the 150-600 Hz band of the real layer x (48k) and the reconstruction y (3k) over a 2 s window"""
    bp = butter(4, [150, 600], 'bandpass', fs=FS, output='sos'); bp3 = butter(4, [150, 600], 'bandpass', fs=CFS, output='sos')
    i0 = int(t0 * FS); n = int(2 * FS)
    xr3 = resample_poly(sosfiltfilt(bp, x)[i0 - 4800:i0 + n + 4800], 1, 16)
    yb = sosfiltfilt(bp3, y); best = None
    for lag in range(-span, span + 1):
        n0 = int(round((t0 - T0) * CFS)) + OFF + lag
        yy = yb[n0 - 300:n0 + 6000 + 300]; m = min(len(yy), len(xr3))
        c = np.corrcoef(yy[:m], xr3[:m])[0, 1]
        if best is None or c > best[0]:
            best = (float(c), lag)
    return best


def win_metrics_recon(y, segs):
    """recon-signal metrics on windows: Hann FFT bands, M30/M12 of the 150-260 envelope (15-sample boxes from the window start)"""
    bb = sosfiltfilt(BP260_3, y)
    out = []
    for t0 in segs:
        n0 = core_idx(t0); n1 = n0 + int(WIN * CFS)
        d = hann_bands(y[n0:n1], CFS)
        d['Ml'], d['Ml12'] = modM(env_db_box(bb[n0:n1], 15))
        out.append(d)
    return out


def jump_stats(d, a2, t0s, only=None):
    """count of >6 dB/hop steps of a_2 in the dev windows (see CHOICES m3); returns counts per window and checked pairs"""
    ih = d['hop'][:, 0].astype(np.int64); st = d['state']; vid = d['voice']
    tc = (ih - OFF + 8) / CFS + T0
    a = a2
    ok = (vid[1:] == vid[:-1]) & (st[1:] >= 2) & (st[:-1] >= 2) & (a[1:] > 1e-7) & (a[:-1] > 1e-7)
    dd = np.abs(20 * np.log10(np.where(ok, a[1:], 1.0) / np.where(ok, a[:-1], 1.0)))
    big = ok & (dd > 6.0)
    if only is not None:      # only hop pairs with both hops in the given (H,S) mask (sustain)
        big = big & only[1:] & only[:-1]
    res = []
    for t0 in t0s:
        m = (tc[1:] >= t0) & (tc[1:] < t0 + WIN)
        res.append((int(big[m].sum()), int(ok[m].sum())))
    return res
