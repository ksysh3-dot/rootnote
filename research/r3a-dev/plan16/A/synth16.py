"""Section 16 common: the ENGINE harmonic set for the offline layers.
k = 2..8 while k f <= 700 Hz (engine `if (fk > 700.0) break;`), a_k = g(f) w_k(f) r_k A, voicing 0, gl = 1,
r_k = 1 for k f <= 220 else g12 + upperBlend (g12^2 - g12), g12 = 10^(-12 log2(fk/220)/20), upperBlend = 1 for vbAlpha2_ (VbHpv{true,true,1}).
Source: app/src/main/cpp/libpvb/pvb_resultant.inc:780 amplitudes(), pvb_vb.cpp:390 lookup().  Tables are identical in r3-work and r3-ref-core (diffed).
The sustained path of rows.render_layer (k = 2, 3) is replaced by render_layer16 (k up to 8); the output filter kOutSos is the same."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from scipy.signal import sosfilt
import tables as T

FSC = 3000.0
KMAX = 8
FMAX = 700.0


def engine_gains(f, kmax=KMAX):
    """per-unit-amplitude gains, array (7, n) for k = 2..8; 0 where k f > 700 Hz.  f: scalar or array (Hz)"""
    f = np.atleast_1d(np.asarray(f, float))
    w, g = T.lookup(f)
    out = np.zeros((7, len(f)))
    for k in range(2, kmax + 1):
        fk = k * f
        g12 = 10 ** (-12 * np.log2(np.maximum(fk, 1e-9) / 220.0) / 20)
        r = np.where(fk > 220, g12 + 1.0 * (g12 * g12 - g12), 1.0)
        out[k - 2] = np.where((fk <= FMAX) & (f > 0), g * w[k - 2] * r, 0.0)
    return out


def render_layer16(voices, dur_s, lag=0.0, kmax=KMAX, split=None):
    """3 kHz layer (causal kOutSos filtered), k = 2..kmax.  voices: dicts with t, f, amp (as rows.py).
    split: optional callable(voice, tt, f, a) -> bool mask array (True = counted in part 'a'); then returns (layer_a, layer_b) with
    a-part amplitude * mask and b-part amplitude * ~mask (same phases, so a + b == the unsplit layer)."""
    n = int(np.ceil(dur_s * FSC)) + 8
    ya = np.zeros(n); yb = np.zeros(n) if split is not None else None
    for v in voices:
        t = v['t'] + lag
        i0 = max(0, int(np.floor(t[0] * FSC))); i1 = min(n, int(np.ceil(t[-1] * FSC)) + 1)
        if i1 <= i0 + 1:
            continue
        tt = np.arange(i0, i1) / FSC
        f = np.interp(tt, t, v['f']); a = np.interp(tt, t, v['amp'], left=0.0, right=0.0)
        ph = 2 * np.pi * np.cumsum(f) / FSC
        G = engine_gains(f, kmax)
        s = np.zeros(len(tt))
        for k in range(2, kmax + 1):
            s += G[k - 2] * np.cos(k * ph)
        if split is None:
            ya[i0:i1] += a * s
        else:
            m = split(v, tt, f, a)
            ya[i0:i1] += a * s * m; yb[i0:i1] += a * s * (~m)
    ya = sosfilt(T.OUT_SOS, ya)
    if split is None:
        return ya
    return ya, sosfilt(T.OUT_SOS, yb)
