"""hpv_ref.py - frozen Python reference of the 'hpv' virtual-bass candidate for the C++ port (libpvb/pvb_vb.*).

The 3 kHz core is a verbatim copy of tools/pvb-harness/vb5/vbcore.py (commit c2b1324: hpss_split, hilbert_iir,
pv_layer, band_layer, layer_hpv with placement 'lo'), so the app's tests do not depend on the research folder, which
keeps changing. Constants come from the exported files next to this one (copies of vb5/port/*.json).
test_engine.py checks that this copy still equals vbcore.layer_hpv when vb5 is present.

Two additions for the port:
  * rate conversion for 44.1 kHz. The core always runs at exactly 3000 Hz. 48 kHz: decimate/interpolate by 16 with
    the 161-tap Kaiser FIR (as vbcore). 44.1 kHz: rational 10/147 polyphase conversion whose FIR is the same
    continuous-time filter sampled at 441 kHz (firwin(1471, 900 Hz, Kaiser 8): same 900 Hz cutoff, same 3.33 ms span,
    same 1/600 s group delay). Decimated sample m is the input at time m/3000 s for both rates.
  * real-time alignment. vbcore.pv_layer places the grain of frame j at [s0+N-H, s0+N+H), up to H-1 = 15 decimated
    samples before the frame's last sample, i.e. the reference looks 5 ms ahead. A causal implementation emits the core
    output 15 decimated samples later: layer_rt() = interpolate(delay(core, 15)). The app's dry delay is therefore the
    measured hpv latency (6812 samples at 48 kHz) + 240 samples = 7052 samples (146.9 ms).
"""
import json, os
import numpy as np
from scipy.signal import firwin, sosfilt, lfilter, upfirdn
from scipy.ndimage import median_filter

HERE = os.path.dirname(os.path.abspath(__file__))
FSD = 3000
RT_SHIFT = 15                       # decimated samples (H - 1), see above
LAT48_PY = 6812                     # vbcore nominal latency of hpv at 48 kHz (synth_tests.t_latency)
LAT_S = (LAT48_PY + RT_SHIFT * 16) / 48000.0

_aa = json.load(open(os.path.join(HERE, 'aa_fir.json')))
AA48 = np.array(_aa['taps'])
AA441 = firwin(1471, 900.0, window=('kaiser', 8.0), fs=441000)
RATES = {48000: (1, 16, AA48), 44100: (10, 147, AA441)}   # L (up), M (down), FIR at fs * L

_flt = json.load(open(os.path.join(HERE, 'filters_3k.json')))
BAND_SOS = np.array(_flt['band_32_190'])
OUT_SOS = np.array(_flt['out_hp150_lp600'])
_hil = json.load(open(os.path.join(HERE, 'hilbert.json')))
HA, HB = _hil['Q_branch'], _hil['I_branch']
_tab = json.load(open(os.path.join(HERE, 'tables_lo.json')))
FG, W, G = np.array(_tab['f_hz']), np.array(_tab['w']), np.array(_tab['g'])
PSI = np.array(_tab['psi'])
K_MAX = 8
EPS = 10 ** (-80.0 / 20)
F_LO_EDGE, F_HI_EDGE = 32.0, 190.0
IF_FLOOR_DB = -52.0
HP_N, HP_HOP, HP_MED_T, HP_MED_F = 192, 16, 11, 7
PV_N, PV_H, PV_NFFT = 384, 16, 2048
PV_MAX_PEAKS, PV_REL_DB, PV_ABS_DB = 4, -30.0, -75.0
PV_ENV_CAP, PV_ENV_SMOOTH_S = 1.0, 0.020


def latency_frames(fs):
    return int(round(LAT_S * fs))


# ---------------------------------------------------------------- rate conversion
def decimate(x, fs):
    L, M, h = RATES[fs]
    n_out = (len(x) * L + M - 1) // M
    return upfirdn(h * L, x, up=L, down=M)[:n_out]


def interpolate(hc, fs, n_out):
    L, M, h = RATES[fs]
    y = upfirdn(h * M, hc, up=M, down=L)[:n_out]
    return np.r_[y, np.zeros(n_out - len(y))] if len(y) < n_out else y


# ---------------------------------------------------------------- 3 kHz core (copied from vbcore)
def _ap_cascade(x, coefs):
    y = x
    for a in coefs:
        c = a * a
        y = lfilter([c, 0.0, -1.0], [1.0, 0.0, -c], y)
    return y


def hilbert_iir(x):
    i_ = _ap_cascade(x, HB)
    q_ = _ap_cascade(x, HA)
    q_ = np.r_[0.0, q_[:-1]]
    return i_ + 1j * q_


def lookup(f):
    idx = np.clip(np.interp(f, FG, np.arange(len(FG))), 0, len(FG) - 1)
    i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(FG) - 1); fr = idx - i0
    return W[:, i0] * (1 - fr) + W[:, i1] * fr, G[i0] * (1 - fr) + G[i1] * fr


def inst_freq(u, A=None, tau=0.005, f_default=60.0):
    d = u[1:] * np.conj(u[:-1])
    f = np.r_[f_default, np.angle(d)] * FSD / (2 * np.pi)
    if A is not None:
        f = np.where(A >= 10 ** (IF_FLOOR_DB / 20), f, f_default)
    a = np.exp(-1 / (tau * FSD))
    return lfilter([1 - a], [1, -a], f, zi=[f_default * a])[0]


def band_layer(zb, eps=EPS):
    A = np.abs(zb)
    u = zb / (A + eps)
    f_i = inst_freq(u, A)
    f_c = np.clip(f_i, F_LO_EDGE, F_HI_EDGE)
    wk, _ = lookup(f_c)
    ag = np.exp(-1 / (0.020 * FSD))
    f_g = lfilter([1 - ag], [1, -ag], f_c, zi=[f_c[0] * ag])[0]
    _, gk = lookup(f_g)
    amp = A * gk
    out = np.zeros(len(zb))
    uk = u.copy()
    for k in range(2, K_MAX + 1):
        uk = uk * u
        out += wk[k - 2] * (uk * np.exp(1j * PSI[k - 2])).real
    return out * amp


def hpss_split(x, N=HP_N, HOP=HP_HOP, MT=HP_MED_T, MF=HP_MED_F):
    n = len(x)
    win = np.hanning(N + 1)[:-1]
    nf = (n + N) // HOP + 1
    xp = np.r_[np.zeros(N), x, np.zeros(N)]
    idx = np.arange(nf)[:, None] * HOP + np.arange(N)[None, :]
    idx = np.minimum(idx, len(xp) - 1)
    F = np.fft.rfft(xp[idx] * win, axis=1)
    S = np.abs(F)
    H = median_filter(S, size=(MT, 1), mode='nearest', origin=(MT // 2, 0))
    P = median_filter(S, size=(1, MF), mode='nearest')
    Mh = H ** 2 / (H ** 2 + P ** 2 + 1e-20)
    yh = np.zeros(len(xp) + N); yp = np.zeros(len(xp) + N); wsum = np.zeros(len(xp) + N)
    fh = np.fft.irfft(F * Mh, n=N, axis=1) * win
    fp = np.fft.irfft(F * (1 - Mh), n=N, axis=1) * win
    for j in range(nf):
        s = j * HOP
        yh[s:s + N] += fh[j]; yp[s:s + N] += fp[j]; wsum[s:s + N] += win * win
    wsum = np.maximum(wsum, 1e-3)
    yh = yh / wsum; yp = yp / wsum
    return yh[N:N + n], yp[N:N + n]


def pv_layer(bh, A_fast, N=PV_N, H=PV_H, nfft=PV_NFFT):
    n = len(bh)
    win = np.hanning(N + 1)[:-1]
    wsum = win.sum()
    nf = (n - N) // H + 1
    half = N // 2
    f_grid = np.fft.rfftfreq(nfft, 1 / FSD)
    lo_bin = int(np.searchsorted(f_grid, 25.0)); hi_bin = int(np.searchsorted(f_grid, 200.0))
    out = np.zeros(n + 2 * N); apv = np.zeros(n + 2 * N)
    gw = np.bartlett(2 * H + 1)[:-1]
    gn = np.arange(-H, H)
    tracks = []
    eps_abs = 10 ** (PV_ABS_DB / 20)
    ks = np.arange(2, K_MAX + 1)
    for j in range(nf):
        s0 = j * H; frame = bh[s0:s0 + N] * win
        fr = np.r_[frame[half:], np.zeros(nfft - N), frame[:half]]
        X = np.fft.rfft(fr)
        mag = np.abs(X[lo_bin:hi_bin])
        if mag.size == 0 or mag.max() * 2 / wsum < eps_abs:
            tracks = []
            continue
        lm = np.where((mag[1:-1] >= mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
        if lm.size == 0:
            tracks = []
            continue
        order = lm[np.argsort(mag[lm])[::-1]]
        thr = mag.max() * 10 ** (PV_REL_DB / 20)
        peaks = []
        for i in order:
            if mag[i] < thr or len(peaks) >= PV_MAX_PEAKS:
                break
            a_, b_, c_ = np.log(mag[i - 1] + 1e-30), np.log(mag[i] + 1e-30), np.log(mag[i + 1] + 1e-30)
            den = a_ - 2 * b_ + c_
            off = 0.5 * (a_ - c_) / den if abs(den) > 1e-12 else 0.0
            off = float(np.clip(off, -1, 1))
            fp = f_grid[lo_bin + i] + off * (f_grid[1] - f_grid[0])
            ap = np.exp(b_ - 0.25 * (a_ - c_) * off) * 2 / wsum
            ph = float(np.angle(X[lo_bin + i]))
            if any(abs(fp - q[0]) < 12.0 for q in peaks):
                continue
            peaks.append((fp, ap, ph))
        new_tracks = []
        grain = np.zeros(2 * H); agrain = 0.0
        for fp, ap, ph in peaks:
            best = None
            for tr in tracks:
                if abs(tr['f'] - fp) < 0.10 * fp and (best is None or abs(tr['f'] - fp) < abs(best['f'] - fp)):
                    best = tr
            if best is not None:
                tracks.remove(best)
                pred = best['Phi'] + np.pi * (best['f'] + fp) * H / FSD
                Phi = ph + 2 * np.pi * np.round((pred - ph) / (2 * np.pi))
            else:
                Phi = ph
            new_tracks.append(dict(f=fp, Phi=Phi))
            wk, gk = lookup(np.array([fp]))
            phase = Phi + 2 * np.pi * fp * gn / FSD
            amp = ap * gk[0]
            for ki, k in enumerate(ks):
                if wk[ki, 0] > 1e-4:
                    grain += amp * wk[ki, 0] * np.cos(k * phase + PSI[ki])
            agrain += ap
        tracks = new_tracks
        c = s0 + N
        out[c - H:c + H] += grain * gw; apv[c - H:c + H] += agrain * gw
    out = out[:n]; apv = apv[:n]
    A_del = np.r_[np.zeros(half), A_fast[:-half]] if half < n else np.zeros(n)
    al = np.exp(-1 / (PV_ENV_SMOOTH_S * FSD))
    A_s = lfilter([1 - al], [1, -al], A_del); P_s = lfilter([1 - al], [1, -al], apv)
    g = np.clip(A_s / (P_s + 1e-9), 0.0, PV_ENV_CAP) * (apv > 0)
    return out * g, half


def core(md):
    """vbcore.layer_hpv between decimation and interpolation (3 kHz in, 3 kHz out, vbcore's alignment)."""
    b = sosfilt(BAND_SOS, md)
    bh, bp = hpss_split(b)
    d = HP_N - 1
    bh = np.r_[np.zeros(d), bh[:-d]]; bp = np.r_[np.zeros(d), bp[:-d]]
    zh = hilbert_iir(bh); zp = hilbert_iir(bp)
    hh, half = pv_layer(bh, np.abs(zh))
    hp = band_layer(zp)
    hp = np.r_[np.zeros(half), hp[:-half]]
    return sosfilt(OUT_SOS, hh + hp)


def layer_like_vbcore(m48):
    """Same as vbcore.layer_hpv(m48) (48 kHz only): the non-causal alignment of the research code."""
    return interpolate(core(decimate(m48, 48000)), 48000, len(m48))


def layer_rt(m, fs):
    """What a causal real-time implementation produces at fs (44100 or 48000): the core 15 samples later."""
    h = core(decimate(m, fs))
    h = np.r_[np.zeros(RT_SHIFT), h[:-RT_SHIFT]]
    return interpolate(h, fs, len(m))


# ---------------------------------------------------------------- Bankstown (chadmed/bankstown, MIT), per channel
BANKSTOWN = dict(amt=1.45, s2=1.35, s3=2.25, blend=0.67, floor=20.0, ceil=200.0, final_hp=200.0)   # Asahi MBP 14 tuning


def rbj(fs, f, kind, q=1 / np.sqrt(2)):
    w = 2 * np.pi * f / fs; al = np.sin(w) / (2 * q); c = np.cos(w); a0 = 1 + al
    if kind == 'lp':
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    else:
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    return np.array([b[0] / a0, b[1] / a0, b[2] / a0, 1.0, -2 * c / a0, (1 - al) / a0])


def bankstown_layer(x, fs, level_db=0.0, p=BANKSTOWN):
    """layer for one channel: LP2(3 ceil)(HP2(final_hp)(amt * K * [blend tanh(s3 p) + (1-blend) tanh(s2 p) (p<=0)]))
    with p = LP2(ceil)(HP2(floor)(x)), K = pi / (0.5 + e); RBJ Butterworth biquads (Q = 1/sqrt 2)."""
    pp = sosfilt(np.vstack([rbj(fs, p['floor'], 'hp'), rbj(fs, p['ceil'], 'lp')]), x)
    K = np.pi / (0.5 + np.e)
    sat = K * (p['blend'] * np.tanh(p['s3'] * pp) + (1 - p['blend']) * np.tanh(p['s2'] * pp) * (pp <= 0))
    amt = p['amt'] * 10 ** (level_db / 20)
    return sosfilt(np.vstack([rbj(fs, p['final_hp'], 'hp'), rbj(fs, 3 * p['ceil'], 'lp')]), amt * sat)
