"""P1 lookup tables (pvb_vb_tables.h) ported to numpy: gain/weights per frequency, output filter (3 kHz biquads).
Identical to VbHpv::lookup (numpy.interp of the frequency grid to the index, then linear interpolation of the tables)."""
import re
from pathlib import Path
import numpy as np

HDR = Path.home() / 'r3-ref-core/app/src/main/cpp/libpvb/pvb_vb_tables.h'


def _arr(txt, name):
    m = re.search(r'static const double ' + name + r'\[\d+\]\s*=\s*\{(.*?)\};', txt, re.S)
    return np.array([float(v) for v in re.findall(r'[-+0-9.eE]+', m.group(1)) if re.search(r'\d', v)])


_t = HDR.read_text()
GRID_HZ = _arr(_t, 'kGridHz')
WEIGHTS = _arr(_t, 'kWeights').reshape(7, 400)      # k = 2..8
GAIN = _arr(_t, 'kGain')
OUT_SOS = _arr(_t, 'kOutSos').reshape(3, 6)          # at the 3 kHz core rate: b0 b1 b2 a0 a1 a2
assert GRID_HZ.shape == (400,) and GAIN.shape == (400,)


def lookup(f):
    """f (Hz, array) -> (w (7, n) weights for k=2..8, gain (n,))"""
    f = np.asarray(f, float)
    idx = np.interp(f, GRID_HZ, np.arange(400.0))          # clipped like the C++
    i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, 399); fr = idx - i0
    w = WEIGHTS[:, i0] * (1 - fr) + WEIGHTS[:, i1] * fr
    g = GAIN[i0] * (1 - fr) + GAIN[i1] * fr
    return w, g


def harm_gains(f, kmax=3):
    """Per-unit-amplitude harmonic gains for k = 2..kmax of a track at frequency f, voicing 0 (P1 timbre):
    gain(f) * w_k(f) * rolloff, rolloff = 24 dB/oct above 220 Hz (upperBlend 1)."""
    f = np.asarray(f, float)
    w, g = lookup(f)
    out = []
    for k in range(2, kmax + 1):
        wk = w[k - 2].copy()
        fk = k * f
        # P1 profile: upperBlend = 1 (fixed 24 dB/oct above 220 Hz): g12 + 1*(g12^2 - g12) = g12^2 (verified against the P1 harmonic trace)
        g12 = 10 ** (-12 * np.log2(np.maximum(fk, 1e-9) / 220.0) / 20)
        ro = np.where(fk > 220, g12 * g12, 1.0)
        out.append(g * wk * ro)
    return out
