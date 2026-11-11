"""Coarse model of what the Galaxy S26 Ultra does to our output before it reaches the ear (volume 60).

Measured facts it is built on (UMIK-1, 30 cm, volume 60; measurement recordings and design doc, not included):
  * A dynamics processor BEFORE the volume control, independent of the music app. Stepped 1 kHz sines
    (0.4 s) give gain reduction 0 at -34 dBFS, 0.4 at -31, 0.9 at -28, 1.2 at -25, 2.1 at -22, 3.4 at -19,
    6.0 at -16, 10.2 at -13 and 19.9 dB at -1 dBFS (output nearly flat above about -17).
    400 and 630 Hz steps compress about the same.
  * It reacts most to ~2 kHz and little to 50 Hz, and loud content in one region pushes others down:
    2 kHz masker at -1 dBFS -> 315 Hz probe -7.9 dB; 200 Hz -> 1 kHz -4.7; 50 Hz -> 1 kHz -3.8 dB.
    Recovery after a loud burst: time constant roughly 0.25 s (0.2-0.6 s).
  * Speaker + room response (sweep, volume 60), third-octave, dB re 1 kHz (SPEAKER_DB below).
NOT modelled (unknown): exact band layout and coupling of the processor, the low-frequency protection seen
with long loud sweeps (250-800 Hz 4-7 dB lower than small signals), attack time, and anything volume dependent.
Use the model for direction and rough size, not as a prediction. Two variants bracket the coupling:
  'wide'  : one gain for all frequencies from a 2 kHz-weighted detector (strongest cross-band ducking)
  'split' : low band (<900 Hz) and high band (>900 Hz) each with their own detector and gain, plus coupling
            low <- 0.4 x high reduction, high <- 0.24 x low reduction (from the masker tests)

API
  drc(x, fs, variant='wide') -> (y, info)     x: (n, 2) float, digital level as sent by our app
  speaker_db(f)                               speaker + room response, dB re 1 kHz (interpolated)
  acoustic_bands(y, fs, edges)                band energies (dB) after the speaker response
  loudness_db(y, fs)                          K-weighted loudness proxy after the speaker response (dB)
"""
import numpy as np
from scipy.signal import sosfilt, butter

# Static gain reduction of the processor vs sine-equivalent detector level (1 kHz steps, design doc).
STATIC = np.array([(-34.0, 0.0), (-31.0, 0.42), (-28.0, 0.90), (-25.0, 1.19), (-22.0, 2.06), (-19.0, 3.39),
                   (-16.0, 6.02), (-13.0, 10.19), (-1.0, 19.9)])

# Speaker + room, sweep at volume 60 (vol60_curves.npz 'room'), third-octave dB re 1 kHz.
SPEAKER_HZ = np.array([125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000,
                       5000, 6300, 8000, 10000, 12500, 16000], float)
SPEAKER_DB = np.array([-20.2, -14.0, -8.9, -4.9, -6.0, -5.6, -4.7, -2.8, 1.0, 0.3, 3.0, 2.3, 5.3, 10.7, 11.1,
                       10.9, 15.7, 13.3, 7.9, -1.6, -12.0, -20.0])

BLOCK_S = 0.005          # control rate of the model
LEVEL_RELEASE_S = 0.05   # detector (RMS-like) fall time
ATTACK_S = 0.005         # gain reduction rise time
RELEASE_S = 0.25         # gain reduction recovery time (masker test: 0.2-0.6 s)


def static_gr(level_db):
    l = np.asarray(level_db, float)
    gr = np.interp(l, STATIC[:, 0], STATIC[:, 1])
    gr = np.where(l > STATIC[-1, 0], STATIC[-1, 1] + 0.8 * (l - STATIC[-1, 0]), gr)
    return np.where(l <= STATIC[0, 0], 0.0, gr)


def _rbj_peak(fs, f, g, q):
    A = 10 ** (g / 40); w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); a0 = 1 + al / A
    return np.array([(1 + al * A) / a0, -2 * np.cos(w) / a0, (1 - al * A) / a0, 1, -2 * np.cos(w) / a0, (1 - al / A) / a0])


def _detector_sos(fs, weighted):
    hp = butter(2, 100, 'hp', fs=fs, output='sos')
    if not weighted:
        return hp
    # reacts most around 2 kHz: +4 dB there relative to the mid band (assumption sized from the masker tests).
    # Normalised to 0 dB at 1 kHz, where the static curve was measured.
    pk = _rbj_peak(fs, 2000, 4.0, 0.8)
    w = np.exp(-1j * 2 * np.pi * 1000 / fs)
    g1k = abs((pk[0] + pk[1] * w + pk[2] * w * w) / (1 + pk[4] * w + pk[5] * w * w))
    pk = pk.copy(); pk[:3] /= g1k
    return np.vstack([hp, pk[None, :]])


def _envelope_db(x, fs, sos):
    """Sine-equivalent level per control block (dB): fast rise, LEVEL_RELEASE_S fall."""
    w = sosfilt(sos, x, axis=0)
    p = np.mean(w ** 2, axis=1)
    n = int(BLOCK_S * fs)
    m = len(p) // n
    blk = 10 * np.log10(np.maximum(p[:m * n].reshape(m, n).mean(axis=1), 1e-14)) + 3.0103
    r = 1 - np.exp(-BLOCK_S / LEVEL_RELEASE_S)
    env = np.empty(m); s = -100.0
    for i, v in enumerate(blk):
        s = v if v > s else s + (v - s) * r
        env[i] = s
    return env, n


def _ballistics(gr):
    """Gain reduction with ATTACK_S rise and RELEASE_S recovery."""
    a = 1 - np.exp(-BLOCK_S / ATTACK_S); r = 1 - np.exp(-BLOCK_S / RELEASE_S)
    out = np.empty_like(gr); s = 0.0
    for i, v in enumerate(gr):
        s += (v - s) * (a if v > s else r)
        out[i] = s
    return out


def _gain_samples(gr_db_blocks, n, length):
    g = 10 ** (-np.repeat(gr_db_blocks, n) / 20)
    if len(g) < length:
        g = np.concatenate([g, np.full(length - len(g), g[-1] if len(g) else 1.0)])
    return g[:length]


def drc(x, fs, variant='oct'):
    x = np.asarray(x, float)
    if variant == 'oct':
        return drc_oct(x, fs)
    if variant == 'octx':
        return drc_oct(x, fs, cross_measured=True)
    if variant == 'wide':
        env, n = _envelope_db(x, fs, _detector_sos(fs, True))
        gr = _ballistics(static_gr(env))
        y = x * _gain_samples(gr, n, len(x))[:, None]
        return y, dict(gr_low=gr, gr_high=gr, block=n)
    # split: Linkwitz-Riley 4th order at 900 Hz
    lo_sos = butter(2, 900, 'lp', fs=fs, output='sos'); hi_sos = butter(2, 900, 'hp', fs=fs, output='sos')
    lo = sosfilt(lo_sos, sosfilt(lo_sos, x, axis=0), axis=0)
    hi = sosfilt(hi_sos, sosfilt(hi_sos, x, axis=0), axis=0)  # LR4: low + high is an allpass
    el, n = _envelope_db(lo, fs, butter(2, 100, 'hp', fs=fs, output='sos'))
    eh, _ = _envelope_db(hi, fs, _detector_sos(fs, True))
    gl, gh = static_gr(el), static_gr(eh)
    gl_t = _ballistics(np.maximum(gl, 0.4 * gh))
    gh_t = _ballistics(np.maximum(gh, 0.24 * gl))
    y = lo * _gain_samples(gl_t, n, len(x))[:, None] + hi * _gain_samples(gh_t, n, len(x))[:, None]
    return y, dict(gr_low=gl_t, gr_high=gh_t, block=n)


# ----------------------------------------------------------------------------------------------- 'oct' variant
# Octave-band processor, applied with an STFT. Each band reduces itself by the measured static curve; loud
# content elsewhere pulls a band down by  s(f_masker) * exp(-distance_octaves / LAMBDA) * its own reduction,
# with s = 1 at >= 1 kHz falling to 0.5 at <= 300 Hz ("most sensitive to 2 kHz, little to 50 Hz").
# Fitted to the masker tests: 2 kHz -> 315 Hz 0.40 (model 0.41), 200 Hz -> 1 kHz 0.24 (model 0.23).
OCT_CENTERS = np.array([31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
LAMBDA = 3.0
STFT_N, STFT_HOP = 1024, 256


def _masker_weight(fc):
    return np.interp(np.log2(fc), [np.log2(300), np.log2(1000)], [0.5, 1.0])


# 'octx': same bands and self-reduction as 'oct', but the cross-band term follows the measured masker-level
# dependence instead of the band's own reduction. Measured cross-band ducking falls much faster with masker
# level than the self-reduction does (2 kHz -> 315 Hz: -7.9/-3.1/-2.3/-1.3 dB at -1/-4/-8/-12 dBFS, while the
# self-reduction only goes 19.9 -> 11 dB), so 'oct' over-ducks moderately loud maskers by 2-4 dB. CROSS is
# the masker-level curve that, times the same coupling, fits all three masker tests within about 0.5 dB
# (it equals the static curve at -1 dBFS). Below -12 dBFS it is an extrapolation.
CROSS = np.array([(-24.0, 0.0), (-20.0, 0.3), (-16.0, 1.0), (-12.0, 2.4), (-8.0, 4.5), (-4.0, 8.0), (-1.0, 19.9)])


def cross_gr(level_db):
    l = np.asarray(level_db, float)
    gr = np.interp(l, CROSS[:, 0], CROSS[:, 1])
    gr = np.where(l > CROSS[-1, 0], CROSS[-1, 1] + 0.8 * (l - CROSS[-1, 0]), gr)
    return np.where(l <= CROSS[0, 0], 0.0, gr)


def _coupling():
    d = np.abs(np.log2(OCT_CENTERS[:, None] / OCT_CENTERS[None, :]))      # [band, masker]
    c = _masker_weight(OCT_CENTERS)[None, :] * np.exp(-d / LAMBDA)
    np.fill_diagonal(c, 1.0)
    return c


def drc_oct(x, fs, cross_measured=False):
    from scipy.signal import stft, istft
    x = np.asarray(x, float)
    f, t, Z = stft(x.T, fs=fs, window='hann', nperseg=STFT_N, noverlap=STFT_N - STFT_HOP, boundary='even', padded=True)
    P = np.mean(np.abs(Z) ** 2, axis=0)                                 # (freq, frames)
    edges = np.sqrt(OCT_CENTERS[:-1] * OCT_CENTERS[1:])
    idx = np.searchsorted(edges, f)                                     # band of each bin
    nb = len(OCT_CENTERS)
    bandP = np.zeros((nb, P.shape[1]))
    for b in range(nb):
        bandP[b] = P[idx == b].sum(axis=0)
    # a full-scale sine in one band reads 0 dB (Hann, scipy stft scaling): calibrated below
    lvl = 10 * np.log10(np.maximum(bandP, 1e-20)) + _OCT_CAL_DB
    hop_s = STFT_HOP / fs
    r = 1 - np.exp(-hop_s / LEVEL_RELEASE_S)
    env = np.empty_like(lvl); s_ = np.full(nb, -100.0)
    for k in range(lvl.shape[1]):
        v = lvl[:, k]
        s_ = np.where(v > s_, v, s_ + (v - s_) * r)
        env[:, k] = s_
    own = static_gr(env)                                                # (band, frames)
    C = _coupling()
    if cross_measured:
        Cx = C.copy(); np.fill_diagonal(Cx, 0.0)
        gr = np.maximum(own, np.max(Cx[:, :, None] * cross_gr(env)[None, :, :], axis=1))
    else:
        gr = np.max(C[:, :, None] * own[None, :, :], axis=1)            # (band, frames)
    a = 1 - np.exp(-hop_s / ATTACK_S); rr = 1 - np.exp(-hop_s / RELEASE_S)
    g = np.empty_like(gr); s_ = np.zeros(nb)
    for k in range(gr.shape[1]):
        v = gr[:, k]
        s_ = s_ + (v - s_) * np.where(v > s_, a, rr)
        g[:, k] = s_
    # per-bin gain: linear interpolation in dB over log-frequency between band centres
    lf = np.log2(np.maximum(f, 1.0))
    G = np.empty((len(f), g.shape[1]))
    for k in range(g.shape[1]):
        G[:, k] = np.interp(lf, np.log2(OCT_CENTERS), g[:, k])
    Zo = Z * (10 ** (-G / 20))[None, :, :]
    _, y = istft(Zo, fs=fs, window='hann', nperseg=STFT_N, noverlap=STFT_N - STFT_HOP, boundary=True)
    y = y.T[:len(x)]
    return y, dict(gr_bands=g, gr_low=g[3], gr_high=g[6], block=STFT_HOP)


def _calibrate_oct():
    from scipy.signal import stft
    fs = 48000; t = np.arange(fs) / fs
    x = np.sin(2 * np.pi * 1000 * t)
    f, _, Z = stft(np.vstack([x, x]), fs=fs, window='hann', nperseg=STFT_N, noverlap=STFT_N - STFT_HOP)
    P = np.mean(np.abs(Z) ** 2, axis=0)
    band = (f > 707) & (f < 1414)
    return -10 * np.log10(np.median(P[band].sum(axis=0))) - 3.0103   # sine of amplitude 1 -> -3.01 dB RMS -> 0 dB sine-eq


_OCT_CAL_DB = 0.0
_OCT_CAL_DB = _calibrate_oct() + 3.0103


def speaker_db(f):
    f = np.maximum(np.asarray(f, float), 1.0)
    v = np.interp(np.log(f), np.log(SPEAKER_HZ), SPEAKER_DB, left=-40.0, right=-30.0)
    return np.where(f < 100, -20.2 - 40 * np.log10(125 / np.minimum(f, 125)), v)  # steep below 125 Hz


def _spectrum(y, fs, frame=8192):
    mono = y.mean(axis=1) if y.ndim == 2 else y
    m = len(mono) // frame
    if m == 0:
        return None, None
    seg = mono[:m * frame].reshape(m, frame) * np.hanning(frame)
    P = np.mean(np.abs(np.fft.rfft(seg, axis=1)) ** 2, axis=0)
    f = np.fft.rfftfreq(frame, 1 / fs)
    return f, P * 10 ** (speaker_db(f) / 10)


def acoustic_bands(y, fs, edges=((150, 400), (400, 1000), (1000, 2500), (2500, 8000))):
    f, P = _spectrum(y, fs)
    return [float(10 * np.log10(np.sum(P[(f >= a) & (f < b)]) + 1e-20)) for a, b in edges]


def _k_weight(f):
    # ITU-R BS.1770 K-weighting magnitude (shelf + RLB high-pass), as a frequency weighting
    f = np.maximum(f, 1.0)
    hp = 1 / np.sqrt(1 + (38.0 / f) ** 4)
    shelf = 10 ** ((4.0 * (1 / (1 + (1500.0 / f) ** 2))) / 20)
    return (hp * shelf) ** 2


def loudness_db(y, fs):
    f, P = _spectrum(y, fs)
    return float(10 * np.log10(np.sum(P * _k_weight(f)) + 1e-20))
