"""Component model of the v1.5 layer from the voice trace: a_vk = g w_k r_k A c sigma (core rule, pvb_resultant.inc amplitudes()),
tables parsed read-only from pvb_vb_tables.h. Band power of a component through the core output filter (kOutSos @3 kHz) and a
zero-phase Butterworth measurement band-pass (sosfiltfilt -> |H|^4 in power)."""
import re, sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12common import *

TAB = Path('/home/ksysh/r3-work/app/src/main/cpp/libpvb/pvb_vb_tables.h').read_text()


def arr(name):
    m = re.search(r'static const double ' + name + r'\[\d+\] = \{(.*?)\};', TAB, re.S)
    return np.array([float(s) for s in re.findall(r'[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?', m.group(1))])


GRID = arr('kGridHz'); WTAB = arr('kWeights').reshape(7, 400); GTAB = arr('kGain')
assert len(GRID) == 400 and WTAB.shape == (7, 400) and len(GTAB) == 400


def lookup(f):
    f = np.asarray(f, float)
    idx = np.interp(f, GRID, np.arange(400.0))
    i0 = np.clip(np.floor(idx).astype(int), 0, 399); i1 = np.minimum(i0 + 1, 399); fr = idx - i0
    w = WTAB[:, i0] * (1 - fr) + WTAB[:, i1] * fr
    g = GTAB[i0] * (1 - fr) + GTAB[i1] * fr
    return w, g          # w (7, ...), g (...)


def rolloff(fk, corner, blend):
    g12 = 10 ** (-12 * np.log2(np.maximum(fk, 1e-9) / corner) / 20)
    return g12 + blend * (g12 * g12 - g12)


def amplitudes(f, base, gentle=True, blend=0.0, voicing0=True):
    """f, base = A*c*sigma (arrays, any shape). Returns a[7, ...] for k = 2..8 (0 when k f > 700 or base<=0 or f<=0)."""
    f = np.asarray(f, float); base = np.asarray(base, float)
    w, g = lookup(np.where(f > 0, f, 25.0))
    a = np.zeros((7,) + f.shape)
    ok = (base > 0) & (f > 0)
    for kk in range(2, 9):
        fk = kk * f
        r = np.ones_like(f)
        if gentle:
            r = np.where(fk > 220, rolloff(fk, 220.0, blend), 1.0)
        a[kk - 2] = np.where(ok & (fk <= 700.0), g * w[kk - 2] * r * base, 0.0)
    return a


def mag_out(f):
    w, H = sosfreqz(OUT_SOS, worN=np.atleast_1d(f), fs=3000)
    return np.abs(H)


def mag_meas(f, sos):
    w, H = sosfreqz(sos, worN=np.atleast_1d(f), fs=FS)
    return np.abs(H)


def band_pow(a, fk, sos):
    """power of a sinusoid (amplitude a, freq fk) after the out filter and zero-phase band measurement"""
    return 0.5 * (a * mag_out(fk)) ** 2 * mag_meas(fk, sos) ** 4
