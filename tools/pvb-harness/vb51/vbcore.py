"""vbcore.py - vb51 copy of vb5/vbcore.py. Generators unchanged (bit-identical); vb51 changes: render() takes an explicit
dry delay, accepts stereo layers (Bankstown) and ends with the product's -1 dBTP true-peak limiter (common5.tp_limit,
delay-compensated). New candidates are registered by cands51.py.
Original header (vb5):
vbcore.py - round-5 virtual-bass candidates. All causal, fixed latency, written for a C++ port.

Signal plan (48 kHz stereo in):
  m = (L+R)/2 --(causal FIR, decimate x16)--> 3 kHz --> band 34-165 Hz (LR4 edges) --> IIR Hilbert (allpass pair) -> z (analytic)
  --> LR4 crossovers at 60 / 100 Hz applied to z -> z_b (3 analytic sub-bands; their sum is allpass-consistent, so a tone at a
      crossover has the same phase in both bands and its harmonics add without cancellation)
  --> per band: A = |z_b|, u = z_b / (|z_b| + eps)   (eps = -80 dBFS soft floor; no gate)
                f_i = instantaneous frequency of u (one-pole 5 ms), clamped to the band
                layer_b = A * 10^(Lf(f_i)/20) * sum_k w_k(f_i) * Re(u^k e^{j psi_k}),  k = 2..8
                   w_k: harmonic k lands in 150-500 Hz (smoothstep edges), -3 dB/oct tilt, first 3 in-band harmonics full,
                        normalised sum w_k^2 = 1;  Lf: ISO-226 'faithful' level (70 phon) incl. the phone response
  --> sum bands --> output band limit (4th-order HP 150 Hz + 2nd-order LP 600 Hz, IIR) --> interpolate x16 --> layer (mono)
  dry path: delayed by LAT samples (the module's nominal latency), layer added to both channels after the EQ filters.
Candidates differ in the sub-band count, the coherence weighting (graceful fade of a band that holds two strong components),
and the HPSS hybrid (percussive part -> 1-band fast path, harmonic part -> 3-band path).
"""
import numpy as np
from scipy.signal import butter, sosfilt, firwin, fftconvolve, lfilter
import common5 as C

FS = C.FS
DEC = 16
FSD = FS // DEC                    # 3000 Hz
EPS_DB = -80.0
K_MAX = 8
F_LO_EDGE, F_HI_EDGE = 32.0, 190.0
FADE0, FADE1 = 115.0, 165.0       # the layer fades out for fundamentals the speaker plays itself
XO = [60.0, 100.0]                 # 3-band crossovers
OUT_LO0, OUT_LO1 = 140.0, 170.0    # lower edge smoothstep of the harmonic placement
OUT_HI0, OUT_HI1 = 450.0, 600.0
N_FULL = 3                         # in-band harmonics at full weight
PHON = 70.0

# ---------------------------------------------------------------- rate conversion (causal FIR, 161 taps, Kaiser)
_AA = firwin(161, 900.0, window=('kaiser', 8.0), fs=FS)       # passband < 700 Hz, > 80 dB above 2.3 kHz
AA_DELAY = (len(_AA) - 1) // 2                                # 80 samples @ 48 kHz


def decimate(m):
    y = fftconvolve(m, _AA)[:len(m)]
    return y[::DEC]


def interpolate(h, n_out):
    up = np.zeros(len(h) * DEC); up[::DEC] = h * DEC
    y = fftconvolve(up, _AA)[:n_out]
    if len(y) < n_out:
        y = np.r_[y, np.zeros(n_out - len(y))]
    return y


# ---------------------------------------------------------------- IIR Hilbert (Olli Niemitalo's 2x4 allpass pair)
_HA = [0.6923878, 0.9360654322959, 0.9882295226860, 0.9987488452737]
_HB = [0.4021921162426, 0.8561710882420, 0.9722909545651, 0.9952884791278]


def _ap_cascade(x, coefs):
    y = x
    for a in coefs:
        c = a * a
        # y[n] = c*(x[n] + y[n-2]) - x[n-2]
        y = lfilter([c, 0.0, -1.0], [1.0, 0.0, -c], y)
    return y


def hilbert_iir(x):
    """analytic signal z = I + jQ: I = allpass cascade B, Q = allpass cascade A delayed by one sample (Q lags I by
    90 deg +- 0.7 deg over 3..1490 Hz at 3 kHz; verified numerically)."""
    i_ = _ap_cascade(x, _HB)
    q_ = _ap_cascade(x, _HA)
    q_ = np.r_[0.0, q_[:-1]]
    return i_ + 1j * q_


# ---------------------------------------------------------------- filters at 3 kHz
def lr4(fc, kind):
    s = butter(2, fc, kind, fs=FSD, output='sos')
    return np.vstack([s, s])


def sos_apply(sos, z):
    if np.iscomplexobj(z):
        return sosfilt(sos, z.real) + 1j * sosfilt(sos, z.imag)
    return sosfilt(sos, z)


_BAND_SOS = np.vstack([lr4(F_LO_EDGE, 'high'), lr4(F_HI_EDGE, 'low')])
_OUT_SOS = np.vstack([butter(4, 150.0, 'high', fs=FSD, output='sos'), butter(2, 600.0, 'low', fs=FSD, output='sos')])


def split_bands(z, xo=XO):
    """LR4 crossovers on the analytic signal; lower bands pass the allpass of later stages (sum exactly allpass)"""
    bands = []; rest = z
    for fc in xo:
        lp = lr4(fc, 'low'); hp = lr4(fc, 'high')
        bands = [sos_apply(lp, b) + sos_apply(hp, b) for b in bands]
        bands.append(sos_apply(lp, rest)); rest = sos_apply(hp, rest)
    bands.append(rest)
    return bands


# ---------------------------------------------------------------- harmonic weights and 'faithful' level tables
def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# harmonic placement presets: (lower edge smoothstep lo0->lo1, upper edge hi0->hi1, tilt exponent per octave re lo1)
PLACEMENTS = {
    'lo': (140.0, 170.0, 450.0, 600.0, -0.5),     # harmonics from 150 Hz, -3 dB/oct: the missing-fundamental textbook choice
    'hi': (230.0, 270.0, 550.0, 750.0, 0.0),      # harmonics from 250 Hz, flat: where the phone speaker is efficient
}
PLACEMENT = 'lo'


def harmonic_weights(f, placement=None):
    """w[k-2, :] for k = 2..K_MAX at fundamental f (array). normalised so sum_k w^2 = 1 (where any harmonic is in band)"""
    lo0, lo1, hi0, hi1, tilt_e = PLACEMENTS[placement or PLACEMENT]
    ks = np.arange(2, K_MAX + 1)[:, None]
    fk = ks * f[None, :]
    lo = smoothstep((fk - lo0) / (lo1 - lo0))
    hi = 1 - smoothstep((fk - hi0) / (hi1 - hi0))
    k0 = lo1 / f[None, :]                                       # fractional index of the first fully usable harmonic
    rank = np.clip(N_FULL + 0.5 - (ks - k0), 0, 1)
    tilt = (np.maximum(fk / lo1, 1.0)) ** tilt_e
    w = lo * hi * rank * tilt
    n = np.sqrt(np.sum(w ** 2, 0))
    return w / np.maximum(n, 1e-9), n


_PH = {}


def faithful_db(f, w):
    """layer amplitude re the fundamental amplitude so that the harmonic complex (centre fc) is as loud as the fundamental
    would be on a full-range speaker (ISO 226, PHON), played through the phone (its response at fc compensated)."""
    ks = np.arange(2, K_MAX + 1)[:, None]
    p = w ** 2
    fc = np.sum(p * ks * f[None, :], 0) / np.maximum(np.sum(p, 0), 1e-20)
    fc = np.where(np.sum(p, 0) > 0, fc, 250.0)
    return C.iso226_spl(fc, PHON) - C.iso226_spl(f, PHON) - C.phone_db(fc)


_TAB = {}


def tables(placement=None):
    """lookup over 25..200 Hz: (f_grid, w (K-1, n), gain_lin (n))"""
    key = placement or PLACEMENT
    if key not in _TAB:
        fg = np.geomspace(25.0, 200.0, 400)
        w, n = harmonic_weights(fg, key)
        g = 10 ** (faithful_db(fg, w) / 20) * (n > 1e-6) * (1 - 0.75 * smoothstep((fg - FADE0) / (FADE1 - FADE0)))   # fade to -12 dB, never 0
        _TAB[key] = (fg, w, g)
    return _TAB[key]


def lookup(f):
    fg, w, g = tables()
    idx = np.clip(np.interp(f, fg, np.arange(len(fg))), 0, len(fg) - 1)
    i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(fg) - 1); fr = idx - i0
    wk = w[:, i0] * (1 - fr) + w[:, i1] * fr
    gk = g[i0] * (1 - fr) + g[i1] * fr
    return wk, gk


PSI = np.pi * np.arange(2, K_MAX + 1) ** 2 / 6.0           # fixed Schroeder-like partial phases (low crest)


# ---------------------------------------------------------------- instantaneous frequency / coherence
IF_FLOOR_DB = -52.0                # below this band amplitude the IF estimate is not trusted (weights fall back to 60 Hz)


def inst_freq(u, A=None, tau=0.005, f_default=60.0):
    """instantaneous frequency of the unit phasor u, one-pole smoothed (tau). Where the band amplitude A is below
    IF_FLOOR_DB the raw estimate is replaced by f_default (numerical garbage must not reach the weight tables)."""
    d = u[1:] * np.conj(u[:-1])
    f = np.r_[f_default, np.angle(d)] * FSD / (2 * np.pi)
    if A is not None:
        f = np.where(A >= 10 ** (IF_FLOOR_DB / 20), f, f_default)
    a = np.exp(-1 / (tau * FSD))
    return lfilter([1 - a], [1, -a], f, zi=[f_default * a])[0]


COH_WIN_S, COH_SIGMA_DB, COH_ONSET_DB = 0.040, 3.0, 10.0


def coherence(A, win_s=COH_WIN_S, sigma_db=COH_SIGMA_DB, A_onset=None, smooth_s=0.025):
    """A: envelope to judge (full-band |z|); A_onset: envelope used for onset resets (default A). The judged envelope is
    first smoothed by a `smooth_s` boxcar so the natural ripple of a note's own harmonics (>= 32 Hz) is ignored while
    beats below ~25 Hz (two notes a third or closer, kick against bass) remain visible."""
    if A_onset is None:
        A_onset = A
    nb = max(1, int(smooth_s * FSD))
    A = lfilter(np.ones(nb) / nb, [1.0], A)
    """graceful weight (0..1) per sample: 1 for one component in the band (its log envelope is locally a straight line,
    including exponential decays and sweeps), lower when the envelope beats (two strong components) or is noise-like.
    Measure: RMS residual (dB) of a linear fit of the log envelope over the past `win_s`, restarted at onsets (a rise of
    COH_ONSET_DB within 2 ms), so an attack is never penalised. c = 1 / (1 + (res / sigma)^2), then 3 ms one-pole."""
    n = len(A)
    L = 20 * np.log10(A + 1e-7)
    Lo = 20 * np.log10(A_onset + 1e-7)
    k = int(0.002 * FSD)
    rise = np.r_[np.zeros(k), Lo[k:] - Lo[:-k]]
    onset = rise > COH_ONSET_DB
    # debounce: an onset starts a new segment only if the previous started > 20 ms ago
    idx = np.where(onset)[0]
    starts = []
    last = -10 ** 9
    for i in idx:
        if i - last > int(0.020 * FSD):
            starts.append(i); last = i
    seg_start = np.zeros(n, int)
    for s0 in starts:
        seg_start[s0:] = s0
    W = int(win_s * FSD)
    t = np.arange(n) / FSD
    c0 = np.r_[0.0, np.cumsum(np.ones(n))]; c1 = np.r_[0.0, np.cumsum(t)]; c2 = np.r_[0.0, np.cumsum(t * t)]
    d0 = np.r_[0.0, np.cumsum(L)]; d1 = np.r_[0.0, np.cumsum(t * L)]; q = np.r_[0.0, np.cumsum(L * L)]
    a = np.maximum(np.arange(n) - W + 1, seg_start); b = np.arange(n) + 1
    S0 = c0[b] - c0[a]; S1 = c1[b] - c1[a]; S2 = c2[b] - c2[a]
    T0 = d0[b] - d0[a]; T1 = d1[b] - d1[a]; Q = q[b] - q[a]
    det = S0 * S2 - S1 * S1
    ok = (S0 >= 10) & (det > 1e-12)
    rss = Q - np.where(ok, (T0 * T0 * S2 - 2 * T0 * T1 * S1 + T1 * T1 * S0) / np.where(ok, det, 1.0), T0 * T0 / np.maximum(S0, 1))
    res = np.sqrt(np.maximum(rss, 0) / np.maximum(S0, 1))
    res = np.where(ok, res, 0.0)
    c = 1.0 / (1.0 + (res / sigma_db) ** 2)
    al = np.exp(-1 / (0.003 * FSD))
    return lfilter([1 - al], [1, -al], c, zi=[c[0] * al])[0]


# ---------------------------------------------------------------- the generator for one analytic band
def band_layer(zb, f_lo, f_hi, eps, coh=None, fast=False):
    A = np.abs(zb)
    u = zb / (A + eps)
    f_i = inst_freq(u, A)
    f_c = np.clip(f_i, F_LO_EDGE, F_HI_EDGE)                # global clamp: a tone leaking from the neighbour band keeps its weights
    wk, _ = lookup(f_c)
    ag = np.exp(-1 / (0.020 * FSD))                          # the level table is read with a slower (20 ms) frequency estimate
    f_g = lfilter([1 - ag], [1, -ag], f_c, zi=[f_c[0] * ag])[0]
    _, gk = lookup(f_g)
    amp = A * gk
    if coh is not None:
        amp = amp * coh
    out = np.zeros(len(zb))
    uk = u.copy()
    for k in range(2, K_MAX + 1):
        uk = uk * u                                       # u^k
        out += wk[k - 2] * (uk * np.exp(1j * PSI[k - 2])).real
    return out * amp, dict(A=A, f=f_i)


# ---------------------------------------------------------------- candidates
def _prep(m48):
    md = decimate(m48)
    b = sosfilt(_BAND_SOS, md)
    return hilbert_iir(b)


def layer_sb(m48, n_bands=3, coh=False, placement='lo'):
    """sub-band analytic harmonic generation. returns the mono layer at 48 kHz (same length as m48) and info."""
    global PLACEMENT
    PLACEMENT = placement
    z = _prep(m48)
    eps = 10 ** (EPS_DB / 20)
    if n_bands == 1:
        parts = [(z, F_LO_EDGE, F_HI_EDGE)]
    elif n_bands == 2:
        bs = split_bands(z, [80.0]); parts = [(bs[0], F_LO_EDGE, 80.0), (bs[1], 80.0, F_HI_EDGE)]
    else:
        bs = split_bands(z, XO); edges = [F_LO_EDGE] + XO + [F_HI_EDGE]
        parts = [(bs[i], edges[i], edges[i + 1]) for i in range(3)]
    h = np.zeros(len(z)); infos = []
    cw = coherence(np.abs(z)) if coh else None
    for zb, lo, hi in parts:
        hb, inf = band_layer(zb, lo, hi, eps, coh=cw); h += hb; infos.append(inf)
    h = sosfilt(_OUT_SOS, h)
    return interpolate(h, len(m48)), dict(bands=infos, z=z)


# ---------------------------------------------------------------- causal HPSS at 3 kHz (hybrid)
HP_N, HP_HOP = 192, 16            # 64 ms window, 5.3 ms hop
HP_MED_T, HP_MED_F = 11, 7        # horizontal median over the past 11 frames (59 ms), vertical +-3 bins (+-47 Hz)


def hpss_split(x, HP_N=HP_N, HP_HOP=HP_HOP, HP_MED_T=HP_MED_T, HP_MED_F=HP_MED_F):
    """causal median-filter HPSS of a real signal at FSD. Frames end at the current sample (causal framing); the harmonic
    estimate is the median of the current and past HP_MED_T-1 frames. Soft masks (Wiener, power 2). Overlap-add synthesis
    with a Hann window -> both outputs are delayed by HP_N - HP_HOP... we report the exact delay: the analysis frame is
    centred HP_N/2 samples in the past, so outputs lag the input by HP_N/2 (=32 ms)."""
    n = len(x)
    win = np.hanning(HP_N + 1)[:-1]
    nf = (n + HP_N) // HP_HOP + 1
    xp = np.r_[np.zeros(HP_N), x, np.zeros(HP_N)]
    idx = np.arange(nf)[:, None] * HP_HOP + np.arange(HP_N)[None, :]
    idx = np.minimum(idx, len(xp) - 1)
    F = np.fft.rfft(xp[idx] * win, axis=1)                 # (nf, nb)
    S = np.abs(F)
    from scipy.ndimage import median_filter
    H = median_filter(S, size=(HP_MED_T, 1), mode='nearest', origin=(HP_MED_T // 2, 0))   # past-only (causal) median
    P = median_filter(S, size=(1, HP_MED_F), mode='nearest')
    Mh = H ** 2 / (H ** 2 + P ** 2 + 1e-20)
    yh = np.zeros(len(xp) + HP_N); yp = np.zeros(len(xp) + HP_N); wsum = np.zeros(len(xp) + HP_N)
    fh = np.fft.irfft(F * Mh, n=HP_N, axis=1) * win
    fp = np.fft.irfft(F * (1 - Mh), n=HP_N, axis=1) * win
    for j in range(nf):
        s = j * HP_HOP
        yh[s:s + HP_N] += fh[j]; yp[s:s + HP_N] += fp[j]; wsum[s:s + HP_N] += win * win
    wsum = np.maximum(wsum, 1e-3)
    yh = yh / wsum; yp = yp / wsum
    # frame j covers xp[j*HOP : j*HOP+N]; xp index = x index + HP_N, so output sample t of x sits at yh[t + HP_N].
    # The returned signals are time-aligned with x (no delay). In real time the OLA sum at position t is final only when
    # the last frame overlapping t (start <= t) is complete, i.e. HP_N - 1 samples later: the caller delays them by
    # HPSS_DELAY_D to emulate the real-time output.
    return yh[HP_N:HP_N + n], yp[HP_N:HP_N + n]


HPSS_DELAY_D = HP_N - 1             # samples at FSD (63.7 ms)


def layer_hyb(m48, coh=True, placement='lo'):
    """HPSS hybrid: percussive bass -> single-band generator (fast, follows sweeps), harmonic bass -> 3-band generator
    (optionally coherence-weighted). The percussive path is delayed to match the HPSS output delay of the harmonic path."""
    global PLACEMENT
    PLACEMENT = placement
    md = decimate(m48)
    b = sosfilt(_BAND_SOS, md)
    bh, bp = hpss_split(b)
    bh = np.r_[np.zeros(HPSS_DELAY_D), bh[:-HPSS_DELAY_D]]; bp = np.r_[np.zeros(HPSS_DELAY_D), bp[:-HPSS_DELAY_D]]
    eps = 10 ** (EPS_DB / 20)
    zh = hilbert_iir(bh); zp = hilbert_iir(bp)
    bs = split_bands(zh, XO); edges = [F_LO_EDGE] + XO + [F_HI_EDGE]
    h = np.zeros(len(zh))
    cw = coherence(np.abs(zh), A_onset=np.abs(zh + zp)) if coh else None
    for i in range(3):
        hb, _ = band_layer(bs[i], edges[i], edges[i + 1], eps, coh=cw); h += hb
    hp, _ = band_layer(zp, F_LO_EDGE, F_HI_EDGE, eps, coh=None)
    h = h + hp
    h = sosfilt(_OUT_SOS, h)
    return interpolate(h, len(m48)), dict(delay_d=HPSS_DELAY_D)


# ---------------------------------------------------------------- phase-vocoder harmonic path (hybrid 2)
PV_N, PV_H, PV_NFFT = 384, 16, 2048      # 128 ms Hann, 5.3 ms hop, 1.46 Hz FFT grid
PV_MAX_PEAKS, PV_REL_DB, PV_ABS_DB = 4, -30.0, -75.0
PV_ENV_CAP = 1.0                         # cut-only imposition: the envelope ratio may shorten (decays, stops) but never boost
PV_ENV_SMOOTH_S = 0.020                  # one-pole on both envelopes before the ratio: beats > ~10 Hz are not imposed


def pv_layer(bh, A_fast, N=PV_N, H=PV_H, nfft=PV_NFFT):
    """sinusoidal/phase-vocoder harmonic generation on the harmonic stream bh (real, FSD) with time-domain envelope
    imposition. Frames end at j*H (causal); the analysis describes the frame centre, so the synthesised grain for frame j
    is placed at j*H, i.e. the output lags bh by N/2 samples. A_fast (|analytic(bh)|) is delayed by the same N/2 and
    imposed: out *= clip(A_fast / A_pv, 0, PV_ENV_CAP) where A_pv is the overlap-added sum of the peak amplitudes.
    Peaks: parabolic interpolation on the log magnitude (25..200 Hz), <= PV_MAX_PEAKS within PV_REL_DB of the strongest.
    Tracks: nearest previous peak within 10 %; phase locked to the measured phase every frame (the propagated phase only
    resolves the 2 pi ambiguity), so harmonic k has phase k*phi exactly like the analytic generator."""
    n = len(bh)
    win = np.hanning(N + 1)[:-1]
    wsum = win.sum()
    nf = (n - N) // H + 1
    half = N // 2
    f_grid = np.fft.rfftfreq(nfft, 1 / FSD)
    lo_bin = int(np.searchsorted(f_grid, 25.0)); hi_bin = int(np.searchsorted(f_grid, 200.0))
    out = np.zeros(n + 2 * N); apv = np.zeros(n + 2 * N)
    gw = np.bartlett(2 * H + 1)[:-1]                 # triangular grain window, hop H -> constant overlap-add
    gn = np.arange(-H, H)
    tracks = []
    eps_abs = 10 ** (PV_ABS_DB / 20)
    ks = np.arange(2, K_MAX + 1)
    for j in range(nf):
        s0 = j * H; frame = bh[s0:s0 + N] * win
        # zero-phase arrangement: rotate so the window centre sits at index 0 -> phases refer to the frame centre
        fr = np.r_[frame[half:], np.zeros(nfft - N), frame[:half]]
        X = np.fft.rfft(fr)
        mag = np.abs(X[lo_bin:hi_bin]); 
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
        c = s0 + N                                     # grain centre: frame end (s0 + N - 1) -> output index s0 + N
        out[c - H:c + H] += grain * gw; apv[c - H:c + H] += agrain * gw
    out = out[:n]; apv = apv[:n]
    A_del = np.r_[np.zeros(half), A_fast[:-half]] if half < n else np.zeros(n)
    al = np.exp(-1 / (PV_ENV_SMOOTH_S * FSD))
    A_s = lfilter([1 - al], [1, -al], A_del); P_s = lfilter([1 - al], [1, -al], apv)
    g = np.clip(A_s / (P_s + 1e-9), 0.0, PV_ENV_CAP) * (apv > 0)
    return out * g, dict(delay_d=half, apv=apv, g=g)


def layer_hpv(m48, pv_n=PV_N, hp_n=HP_N, placement='lo'):
    """HPSS hybrid with the phase-vocoder harmonic path: percussive -> 1-band analytic generator, harmonic -> pv_layer.
    The percussive path is delayed by the PV's N/2 so both paths stay aligned."""
    global PLACEMENT
    PLACEMENT = placement
    md = decimate(m48)
    b = sosfilt(_BAND_SOS, md)
    hop = hp_n // 12
    bh, bp = hpss_split(b, hp_n, hop, HP_MED_T, HP_MED_F)
    d = hp_n - 1
    bh = np.r_[np.zeros(d), bh[:-d]]; bp = np.r_[np.zeros(d), bp[:-d]]
    eps = 10 ** (EPS_DB / 20)
    zh = hilbert_iir(bh); zp = hilbert_iir(bp)
    hh, inf = pv_layer(bh, np.abs(zh), N=pv_n)
    half = inf['delay_d']
    hp, _ = band_layer(zp, F_LO_EDGE, F_HI_EDGE, eps)
    hp = np.r_[np.zeros(half), hp[:-half]]
    h = sosfilt(_OUT_SOS, hh + hp)
    return interpolate(h, len(m48)), dict(delay_d=d + half)


# ---------------------------------------------------------------- full renders
CANDS = {
    'sb1':  dict(fn=lambda m: layer_sb(m, 1, False), lat_ms=None, desc='1-band analytic NLD (34-165 Hz), no coherence weight'),
    'sb3':  dict(fn=lambda m: layer_sb(m, 3, False), lat_ms=None, desc='3-band analytic NLD (34-60-100-165 Hz)'),
    'sb3c': dict(fn=lambda m: layer_sb(m, 3, True), lat_ms=None, desc='3-band analytic NLD + coherence weight'),
    'hyb':  dict(fn=lambda m: layer_hyb(m, False), lat_ms=None, desc='causal HPSS: percussive->1-band NLD, harmonic->3-band NLD'),
    'hpv':  dict(fn=lambda m: layer_hpv(m, 384), lat_ms=None, desc='causal HPSS: percussive->1-band NLD, harmonic->phase vocoder 128 ms + envelope imposition'),
    'hpv2': dict(fn=lambda m: layer_hpv(m, 768), lat_ms=None, desc='as hpv with a 256 ms vocoder window'),
    'sb3h': dict(fn=lambda m: layer_sb(m, 3, False, 'hi'), lat_ms=None, desc='3-band analytic NLD, harmonics placed 250-600 Hz (flat)'),
    'sb1h': dict(fn=lambda m: layer_sb(m, 1, False, 'hi'), lat_ms=None, desc='1-band analytic NLD, harmonics placed 250-600 Hz (flat)'),
}
# nominal latencies (samples @48 kHz) are measured by synth_tests.latency() and stored here by run_all
LAT = {}


def delay(x, n):
    if n <= 0:
        return x.copy()
    return np.r_[np.zeros((n,) + x.shape[1:]), x[:-n]]


def render(x, cand, level_db=0.0, eq_kind='eq', layer=None, lat=None, limiter=True):
    """full chain output (stereo, 48 kHz): EQ v1.1 filters -> + layer (mono to both channels, or stereo) -> output gain
    -> true-peak limiter (-1 dBTP, 1.5 ms look-ahead, 60 ms release; its 88-sample delay is compensated).
    The dry path is delayed by the candidate's nominal latency (lat, default LAT[cand]) so the layer is time-aligned."""
    if layer is None:
        layer, _ = CANDS[cand]['fn'](x if CANDS[cand].get('stereo') else x.mean(1))
    lat = LAT.get(cand, 0) if lat is None else lat
    y = sosfilt(C.eq_sos(FS, eq_kind), delay(x, lat), axis=0)
    L = layer if layer.ndim == 2 else layer[:, None]
    y = (y + L * 10 ** (level_db / 20)) * 10 ** (C.OUT_DB / 20)
    if limiter:
        y = C.tp_limit(y)
    return y, layer
