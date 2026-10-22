"""common5.py - shared pieces for round 5 (virtual bass research), written 2026-10-16.

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
MEAS = os.path.join(SCRATCH, 'meas', 'rec')
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
