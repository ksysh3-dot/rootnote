"""HAUX library (readings: CHOICES.md section 2): comb LS fit on the 48 kHz input, floor between partials, comb-refined f0.  numpy only."""
import numpy as np

FS = 48000
WINLEN = {40: 1920, 85: 4080}
KMAX_HZ = 2000.0
KTOP = 12
NK = KTOP - 1                  # k = 2..12 -> index k-2
_HANN = {}


def hann(L):
    if L not in _HANN:
        n = np.arange(L)
        _HANN[L] = 0.5 * (1 - np.cos(2 * np.pi * (n + 0.5) / L))
    return _HANN[L]


def segment(x, c, L):
    """x[c - L//2 : c - L//2 + L], zero padded outside"""
    a = c - L // 2
    out = np.zeros(L)
    lo, hi = max(a, 0), min(a + L, len(x))
    if hi > lo:
        out[lo - a: hi - a] = x[lo:hi]
    return out


def kmax_of(f, fs=FS, khz=KMAX_HZ):
    return int(min(KTOP, np.floor(min(khz, 0.4 * fs) / f)))


def _ls(seg, w, B, ridge=1e-6):
    Bw = B * w[:, None]
    G = B.T @ Bw
    lam = ridge * np.trace(G) / G.shape[0]
    beta = np.linalg.solve(G + lam * np.eye(G.shape[0]), Bw.T @ seg)
    return beta


def comb_fit(seg, w, f, fs=FS, khz=KMAX_HZ, ktop=KTOP):
    """returns (E[k=2..ktop] nan beyond kmax, Ei[j=1..ktop-1] nan beyond kmax-1, a[k=1..ktop])  (E = a^2/2, a peak amplitude)"""
    L = len(seg)
    kmax = int(min(ktop, np.floor(min(khz, 0.4 * fs) / f)))
    E = np.full(ktop - 1, np.nan); Ei = np.full(ktop - 1, np.nan); a_all = np.full(ktop, np.nan)
    if kmax < 2:
        return E, Ei, a_all
    n = np.arange(L) - L // 2
    ks = np.arange(1, kmax + 1)
    ph = (2 * np.pi * f / fs) * np.outer(n, ks)                    # (L, kmax)
    B = np.empty((L, 1 + 2 * kmax)); B[:, 0] = 1.0
    B[:, 1:1 + kmax] = np.cos(ph); B[:, 1 + kmax:] = np.sin(ph)
    beta = _ls(seg, w, B)
    a = np.hypot(beta[1:1 + kmax], beta[1 + kmax:])
    a_all[:kmax] = a
    E[:kmax - 1] = 0.5 * a[1:] ** 2
    res = seg - B @ beta
    ks2 = np.arange(1, kmax) + 0.5
    ph2 = (2 * np.pi * f / fs) * np.outer(n, ks2)
    B2 = np.concatenate([np.cos(ph2), np.sin(ph2)], 1)
    b2 = _ls(res, w, B2)
    m = len(ks2)
    Ei[:m] = 0.5 * (b2[:m] ** 2 + b2[m:] ** 2)
    return E, Ei, a_all


NFFT = 65536
CENTS = np.arange(-100, 101, 2)


def spec_amp(seg, w):
    X = np.abs(np.fft.rfft(seg * w, NFFT))
    return X


def comb_f0(X, f, fs=FS, khz=KMAX_HZ, kr=6):
    """comb-refined f0 around f (+-100 cent, 2 cent step, parabolic refinement): maximises sum_{k=2..kr, k f' <= khz} |X|(k f')"""
    binhz = fs / NFFT
    cand = f * 2 ** (CENTS / 1200.0)
    sc = np.zeros(len(cand))
    for k in range(2, kr + 1):
        fk = k * cand
        ok = fk <= khz
        sc += np.where(ok, np.interp(fk / binhz, np.arange(len(X)), X), 0.0)
    i = int(np.argmax(sc))
    if 0 < i < len(sc) - 1:
        a, b, c = sc[i - 1], sc[i], sc[i + 1]
        den = a - 2 * b + c
        d = 0.5 * (a - c) / den if abs(den) > 1e-30 else 0.0
        d = float(np.clip(d, -1, 1))
    else:
        d = 0.0
    cen = CENTS[i] + 2.0 * d
    return float(f * 2 ** (cen / 1200.0)), float(sc[i])


def hsal(E, Ei, K):
    """H_sal(K) (dB): mean_{k=2..K} E_k over mean_{j=1..K-1} Ei_j ; K clipped to what exists"""
    e = E[:K - 1]; ei = Ei[:K - 1]
    e = e[np.isfinite(e)]; ei = ei[np.isfinite(ei)]
    if len(e) == 0 or len(ei) == 0:
        return np.nan
    return 10 * np.log10((e.mean() + 1e-30) / (ei.mean() + 1e-30))


def nhit(E, Ei, kmax8=8):
    e = E[:kmax8 - 1]; ei = Ei[:kmax8 - 1]
    ok = np.isfinite(e)
    if not ok.any():
        return np.nan
    fl = np.nanmean(Ei[np.isfinite(Ei)]) if np.isfinite(Ei).any() else 0.0
    return float((e[ok] >= 4 * fl).sum())
