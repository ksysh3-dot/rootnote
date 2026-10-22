"""common5.py - vb51 copy of vb5/common5.py (round 5.1, 2026-10-17).
vb51 changes: the measured phone response files are read from vb51/data/ (copied from the measurement recordings, so the
package is self-contained); tp_limit() = Python port of the product's -1 dBTP look-ahead limiter (pvb_dsp.h TruePeakLimiter).

Original header (vb5):

Everything runs at FS = 48000 Hz (the app's rate). Album files (44.1 kHz) are resampled once on load.
- EQ v1.1 chain exactly as eq/PVB_EQ_S26U_v1.1.eel: 100 Hz LR4 high-pass, 220 Hz +3 dB Q1, 4.5 kHz -3 dB Q0.6, -5 dB output
  (same RBJ math as r4b/common.py, causal direct form)
- phone linear response (UMIK-calibrated pink-noise third-octave RTA, vol60b_cal; below 125 Hz joined with the room sweep)
- ISO 226:2003 equal-loudness contours, BS.1770 loudness (pyloudnorm), 4x oversampled true peak
"""
import json, os
import numpy as np
from scipy.signal import sosfilt, sosfreqz, firwin2, fftconvolve, resample_poly
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.dirname(HERE)
MEAS = os.path.join(HERE, 'data')                 # vb51: vol60b_cal_summary.json, vol60b_cal_curves.npz
ALBUM = os.environ.get('PVB_ALBUM', '')  # optional local folder of .flac files for research runs (not used by CI)
FS = 48000
OUT_DB = -5.0            # EQ v1.1 output gain


# ---------------------------------------------------------------- audio I/O
def load_track(path, fs=FS):
    x, sr = sf.read(path, always_2d=True, dtype='float64')
    if sr != fs:
        from math import gcd
        g = gcd(fs, sr)
        x = resample_poly(x, fs // g, sr // g, axis=0)
    return x


def album_files():
    return sorted(os.path.join(ALBUM, n) for n in os.listdir(ALBUM) if n.endswith('.flac'))


# ---------------------------------------------------------------- EQ v1.1 (same math as the EEL script)
def rbj_peak(fs, f, g_db, q):
    A = 10 ** (g_db / 40); w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al / A
    return np.array([(1 + al * A) / a0, -2 * np.cos(w) / a0, (1 - al * A) / a0, 1.0, -2 * np.cos(w) / a0, (1 - al / A) / a0])


def rbj_hp(fs, f, q=0.7071068):
    w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al; c = np.cos(w)
    return np.array([(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0, 1.0, -2 * c / a0, (1 - al) / a0])


def rbj_lp(fs, f, q=0.7071068):
    w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al; c = np.cos(w)
    return np.array([(1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0, 1.0, -2 * c / a0, (1 - al) / a0])


def eq_sos(fs=FS, kind='eq'):
    """'eq' = EQ v1.1 filters; 'cut' = the same without the 220 Hz boost (high-pass + treble trim only)"""
    s = [rbj_hp(fs, 100), rbj_hp(fs, 100)]
    if kind == 'eq':
        s.append(rbj_peak(fs, 220, 3.0, 1.0))
    s.append(rbj_peak(fs, 4500, -3.0, 0.6))
    return np.vstack(s)


def eq(x, fs=FS, kind='eq', out_db=OUT_DB):
    """EQ v1.1 filters + output gain (the layer of a virtual-bass candidate is added between them: chain position 5)"""
    return sosfilt(eq_sos(fs, kind), x, axis=0) * 10 ** (out_db / 20)


def eq_gain_db(f, fs=FS, kind='eq'):
    _, h = sosfreqz(eq_sos(fs, kind), worN=np.atleast_1d(np.asarray(f, float)), fs=fs)
    return 20 * np.log10(np.abs(h))


# ---------------------------------------------------------------- phone linear response (measured)
def phone_response():
    """(f, dB re the 1-2 kHz average) of the phone + room at the listening position, volume 60."""
    s = json.load(open(os.path.join(MEAS, 'vol60b_cal_summary.json')))
    assert s['cal_applied']
    pk = s['pink_third_octave_db']
    pf = np.array([float(k) for k in pk]); pv = np.array(list(pk.values()), float)
    ref = np.mean(pv[(pf >= 1000) & (pf <= 2000)]); pv = pv - ref
    keep = pf >= 125                                      # below 125 Hz the RTA sits on the room-noise floor
    c = np.load(os.path.join(MEAS, 'vol60b_cal_curves.npz')); sf_, room = c['f'], c['room']
    room = room - np.mean(room[(sf_ >= 1000) & (sf_ <= 2000)])
    r125 = np.interp(np.log10(125), np.log10(sf_), room)
    lo_f = np.array([63, 80, 100]); lo_v = np.interp(np.log10(lo_f), np.log10(sf_), room) - r125 + pv[pf == 125][0]
    f = np.r_[lo_f, pf[keep]]; v = np.r_[lo_v, pv[keep]]
    return f, v


_PR = None


def phone_db(fq):
    global _PR
    if _PR is None:
        _PR = phone_response()
    f, v = _PR
    fq = np.atleast_1d(np.asarray(fq, float))
    out = np.interp(np.log10(np.maximum(fq, 1)), np.log10(f), v)
    lo = fq < f[0]
    out[lo] = v[0] - 24 * np.log2(f[0] / np.maximum(fq[lo], 1))
    return out


_FIR = {}


def phone_fir(fs=FS, n=4097):
    if fs not in _FIR:
        grid = np.r_[0, np.geomspace(10, fs / 2 - 1, 800), fs / 2]
        g = phone_db(grid)
        g[grid > 16000] -= 30
        H = 10 ** (g / 20); H[0] = 0
        _FIR[fs] = firwin2(n, grid / (fs / 2), H)
    return _FIR[fs]


def phone_linear(y, fs=FS):
    """linear part of the phone (speaker + room), zero-phase convolution; mono or (n, ch)"""
    h = phone_fir(fs)
    if y.ndim == 1:
        return fftconvolve(y, h, 'same')
    return np.stack([fftconvolve(y[:, c], h, 'same') for c in range(y.shape[1])], 1)


# ---------------------------------------------------------------- loudness / peak
_METER = {}


def lufs(y, fs=FS):
    import pyloudnorm as pyln
    if fs not in _METER:
        _METER[fs] = pyln.Meter(fs)
    if y.ndim == 1:
        y = y[:, None]
    return float(_METER[fs].integrated_loudness(y))


def true_peak_db(y):
    up = resample_poly(y, 4, 1, axis=0)
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-12))


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-15))


# ---------------------------------------------------------------- ISO 226:2003
_ISO = np.array([
    [20, 0.532, -31.6, 78.5], [25, 0.506, -27.2, 68.7], [31.5, 0.480, -23.0, 59.5], [40, 0.455, -19.1, 51.1],
    [50, 0.432, -15.9, 44.0], [63, 0.409, -13.0, 37.5], [80, 0.387, -10.3, 31.5], [100, 0.367, -8.1, 26.5],
    [125, 0.349, -6.2, 22.1], [160, 0.330, -4.5, 17.9], [200, 0.315, -3.1, 14.4], [250, 0.301, -2.0, 11.4],
    [315, 0.288, -1.1, 8.6], [400, 0.276, -0.4, 6.2], [500, 0.267, 0.0, 4.4], [630, 0.259, 0.3, 3.0],
    [800, 0.253, 0.5, 2.2], [1000, 0.250, 0.0, 2.4], [1250, 0.246, -2.7, 3.5], [1600, 0.244, -4.1, 1.7],
    [2000, 0.243, -1.0, -1.3], [2500, 0.243, 1.7, -4.2], [3150, 0.243, 2.5, -6.0], [4000, 0.242, 1.2, -5.4],
    [5000, 0.242, -2.1, -1.5], [6300, 0.245, -7.1, 6.0], [8000, 0.254, -11.2, 12.6], [10000, 0.271, -10.7, 13.9],
    [12500, 0.301, -3.1, 12.3]])


def iso226_spl(f, phon=70.0):
    """SPL (dB) of a pure tone at frequency f that is as loud as `phon` (ISO 226:2003)."""
    f0, af, lu, tf = _ISO.T
    Af = 4.47e-3 * (10 ** (0.025 * phon) - 1.15) + (0.4 * 10 ** ((tf + lu) / 10 - 9)) ** af
    lp = 10 / af * np.log10(Af) - lu + 94
    return np.interp(np.log10(np.atleast_1d(np.asarray(f, float))), np.log10(f0), lp)


# ---------------------------------------------------------------- band levels (analysis only, zero-phase)
def band_level_db(y, fs, lo, hi):
    """mean power (dB) of y in [lo, hi] Hz via FFT (whole signal); y mono"""
    n = len(y)
    Y = np.fft.rfft(y)
    f = np.fft.rfftfreq(n, 1 / fs)
    m = (f >= lo) & (f < hi)
    p = np.sum(np.abs(Y[m]) ** 2) * 2 / (n * n)
    return float(10 * np.log10(p + 1e-30))


# ---------------------------------------------------------------- vb51: the product's true-peak limiter (pvb_dsp.h)
# Port of pvb::TruePeakLimiter as configured by pvb_engine.cpp: look-ahead 1.5 ms (72 samples @ 48 kHz), ceiling
# -1 dBTP (internally -1.1 dB: 0.1 dB margin), release 60 ms, stereo linked. Detection on an 8x oversampled estimate
# (x[j] itself + 7 Kaiser-windowed-sinc fractional delays, 32 taps, beta 9, R 16, each phase normalised to unit DC gain).
# Gain path: r = min(1, ceil/peak) -> min over L+1 -> moving average over L+1 -> instant attack / exponential release.
# Audio delay D + L = 16 + 72 samples. tp_limit(..., compensate=True) removes that pure delay (offline alignment).
LIM_D, LIM_TAPS, LIM_PH = 16, 32, 7


def _lim_coefs():
    from numpy import i0
    c = np.zeros((LIM_PH, LIM_TAPS))
    for p in range(LIM_PH):
        mu = (p + 1) / 8.0
        x = (np.arange(LIM_TAPS) - 15) - mu
        s = np.sinc(x)
        u = x / 16.0
        w = np.where(np.abs(u) < 1, i0(9.0 * np.sqrt(np.maximum(0, 1 - u * u))) / i0(9.0), 0.0)
        c[p] = s * w / np.sum(s * w)
    return c


_LIMC = None


def tp_limit(y, fs=FS, ceil_db=-1.0, release_ms=60.0, lookahead_ms=1.5, compensate=True, return_gain=False):
    """y: (n,) or (n, ch). Returns the limited signal (and the gain per output sample if return_gain)."""
    global _LIMC
    if _LIMC is None:
        _LIMC = _lim_coefs()
    y = np.asarray(y, float)
    x2 = y if y.ndim == 2 else y[:, None]
    n0 = len(x2)
    L = int(np.clip(round(lookahead_ms * 1e-3 * fs), 1, 300))
    lat = LIM_D + L
    x2 = np.r_[x2, np.zeros((lat, x2.shape[1]))]          # flush: the gain of the last input samples is computed
    n = len(x2)
    ceil = 10 ** ((ceil_db - 0.1) / 20)
    # peak[j] for j = -D .. n-1 (detection at input index i uses j = i - D and the samples x[j-15] .. x[j+16])
    xp = np.r_[np.zeros((LIM_D + 15, x2.shape[1])), x2, np.zeros((LIM_TAPS, x2.shape[1]))]
    # position j (0-based in x) <-> xp index j + D + 15
    nj = n + LIM_D                                       # j from -D to n-1
    base = np.arange(nj)                                 # xp index of x[j-15] for j = -D + base
    pk = np.max(np.abs(xp[base + 15]), 1)                # x[j]
    # the 7 fractional-delay estimates only where the 32-sample support holds a sample above ceil/2 (an inter-sample
    # peak of this interpolator cannot exceed the ceiling elsewhere for audio; exact against the full computation)
    from scipy.ndimage import maximum_filter1d
    near = maximum_filter1d(np.max(np.abs(xp), 1), LIM_TAPS, origin=-(LIM_TAPS // 2))[:nj] > 0.5 * ceil
    cand = np.where(near)[0]
    for s0 in range(0, len(cand), 65536):
        cj = cand[s0:s0 + 65536]
        seg = xp[cj[:, None] + np.arange(LIM_TAPS)[None, :]]          # (nc, 32, ch)
        est = np.einsum('pt,ntc->npc', _LIMC, seg)
        pk[cj] = np.maximum(pk[cj], np.max(np.abs(est), axis=(1, 2)))
    # input index i = 0..n-1 uses j = i - D  -> pk index i
    r = np.where(pk[:n] > ceil, ceil / np.maximum(pk[:n], 1e-30), 1.0)
    if not np.any(r < 1.0):
        g = np.ones(n)
    else:
        from scipy.ndimage import minimum_filter1d
        rp = np.r_[np.ones(L), r]
        m = minimum_filter1d(rp, L + 1, origin=L // 2)[L:]          # min over r[i-L .. i]
        # check origin convention numerically: m[i] must equal min(r[max(0,i-L):i+1]) (ones before 0)
        cs = np.r_[0.0, np.cumsum(np.r_[np.ones(L), m])]
        box = np.minimum(1.0, (cs[L + 1:] - cs[:-L - 1])[:n] / (L + 1))
        rel = 1.0 - np.exp(-1.0 / (release_ms * 1e-3 * fs))
        g = np.ones(n)
        act = np.where(box < 1.0)[0]
        gi = 1.0; i = int(act[0]); k = 0
        while i < n:
            b = box[i]
            gi = b if b < gi else gi + (b - gi) * rel
            g[i] = gi
            if gi > 1 - 1e-9 and b >= 1.0:
                gi = 1.0
                k = np.searchsorted(act, i + 1)
                if k >= len(act):
                    break
                i = int(act[k]); continue
            i += 1
    if compensate:                                     # input sample s meets g[s + lat] (C++: out[i] = x[i - D - L] * g[i])
        g = g[lat:]
        out = x2[:n0] * g[:, None]
    else:
        out = (np.r_[np.zeros((lat, x2.shape[1])), x2[:-lat]] * g[:, None])[:n0]
        g = g[:n0]
    out = out if y.ndim == 2 else out[:, 0]
    return (out, g) if return_gain else out


def tp_limit_lm(y, fs=FS, ceil_db=-1.0, release_ms=60.0, lookahead_ms=1.5):
    """memory-light tp_limit(..., compensate=True, return_gain=True): same output, but the gain path is computed only
    around the (sparse) positions where the limiter acts. Returns (out, g) with g = None when the limiter never acts."""
    global _LIMC
    if _LIMC is None:
        _LIMC = _lim_coefs()
    from scipy.ndimage import maximum_filter1d
    x2 = y if y.ndim == 2 else y[:, None]
    n0 = len(x2)
    L = int(np.clip(round(lookahead_ms * 1e-3 * fs), 1, 300))
    lat = LIM_D + L
    ceil = 10 ** ((ceil_db - 0.1) / 20)
    # sample peak per position j (0..n0-1); positions near the ceiling get the 7 fractional estimates
    sp = np.max(np.abs(x2), 1)
    near = maximum_filter1d(sp, LIM_TAPS, origin=-(LIM_TAPS // 2) + 15) > 0.5 * ceil   # support x[j-15 .. j+16]
    cand = np.where(near)[0]
    del near
    hits = []
    for s0 in range(0, len(cand), 65536):
        cj = cand[s0:s0 + 65536]
        idx = cj[:, None] + np.arange(-15, 17)[None, :]
        ok = (idx >= 0) & (idx < n0)
        seg = np.where(ok[:, :, None], x2[np.clip(idx, 0, n0 - 1)], 0.0)
        est = np.einsum('pt,ntc->npc', _LIMC, seg)
        pk = np.maximum(sp[cj], np.max(np.abs(est), axis=(1, 2)))
        h = pk > ceil
        if h.any():
            hits.append((cj[h], ceil / pk[h]))
    del sp
    if not hits:
        return (y.copy(), None)
    hj = np.concatenate([a for a, _ in hits]); hr = np.concatenate([b for _, b in hits])
    # detection at input index i uses j = i - D: r[i] < 1 at i = j + D. In the compensated output, sample s meets
    # g[s + lat]; work in the 'i' index space on segments [first hit - 1, last hit + 2L + release tail]
    ri = hj + LIM_D
    rel = 1.0 - np.exp(-1.0 / (release_ms * 1e-3 * fs))
    tail = int(np.ceil(np.log(1e-9) / np.log(1 - rel))) + 2 * L + 2
    n_i = n0 + lat
    gs = np.ones(n0)
    # group hits into segments separated by more than tail
    order = np.argsort(ri); ri = ri[order]; hr = hr[order]
    starts = np.r_[0, np.where(np.diff(ri) > tail)[0] + 1]; ends = np.r_[starts[1:], len(ri)]
    for a, b in zip(starts, ends):
        i0 = int(ri[a]); i1 = min(int(ri[b - 1]) + tail, n_i)
        r = np.ones(i1 - i0); r[ri[a:b] - i0] = np.minimum(r[ri[a:b] - i0], hr[a:b])
        rp = np.r_[np.ones(L), r]
        from scipy.ndimage import minimum_filter1d
        m = minimum_filter1d(rp, L + 1, origin=L // 2)[L:]
        cs = np.r_[0.0, np.cumsum(np.r_[np.ones(L), m])]
        box = np.minimum(1.0, (cs[L + 1:] - cs[:-L - 1])[:len(r)] / (L + 1))
        g = np.ones(len(r)); gi = 1.0
        for k in range(len(r)):
            bb = box[k]
            gi = bb if bb < gi else gi + (bb - gi) * rel
            g[k] = gi
        # output sample s = i - lat
        s_a = i0 - lat; s_b = i1 - lat
        lo = max(s_a, 0); hi = min(s_b, n0)
        if hi > lo:
            gs[lo:hi] = np.minimum(gs[lo:hi], g[lo - s_a:hi - s_a])
    out = x2 * gs[:, None]
    return (out if y.ndim == 2 else out[:, 0]), gs
