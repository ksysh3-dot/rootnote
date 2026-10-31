"""S19-LIM helpers: engine runs (limited app chain L and limiter-free twin U), segment series. Numbers only. Definitions: CHOICES.md"""
import os, sys, ctypes as C
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')
sys.dont_write_bytecode = True
from pathlib import Path
HOME = Path.home()
HARN = HOME / 'r3-work/tools/pvb-harness'
for p in (HARN, HARN / 'study'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import research_core_api as CA
import test_engine as T

FS = 48000; BLOCK = 256; FSB = FS / BLOCK
LIB = HARN / 'build_core19/libpvbcapi.so'
MUSIC = sorted(Path('/mnt/c/Users/ksysh/Music/vanila').glob('*.flac'))
SONG_IDX = {'app': 9, 'rem': 6}
WINDOWS = [('app', 52.0, 54.0), ('app', 88.5, 90.5), ('app', 123.5, 125.5), ('app', 201.0, 203.0), ('app', 203.0, 205.0), ('rem', 96.0, 98.0), ('rem', 113.0, 115.0)]
WNAME = ['A0:52', 'A1:28.5', 'A2:03.5', 'A3:21', 'A3:23', 'R1:36', 'R1:53']
B3P2 = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2, betaMin=.05, betaMax=.1, psiSlew=.03)
ROWS = {
    'p1': (6, None),
    'v15': (15, dict(voicing=0, ampSource=0)),
    'v16b': (15, B3P2),
    'v16c': (15, dict(B3P2, layerHpHz=150, layerHpOrder=8, layerHpComp=1)),
}
ROWNAME = {'p1': 'P1', 'v15': 'v1.5', 'v16b': 'v1.6-b', 'v16c': 'v1.6-c'}
APP = dict(hp_hz=100, low_hz=220, low_db=3, low_q=1, hi_hz=4500, hi_db=-3, hi_q=0.6, rel_ms=60, ramp_ms=0, dyn_on=0, hs_db=0, flat=0)
OUT_DB, CEIL_DB = -5.0, -1.0
TWIN_DROP = 25.0
SOS_LO = butter(4, [20, 150], 'bandpass', fs=FS, output='sos')
SOS_400 = butter(4, [20, 400], 'bandpass', fs=FS, output='sos')
SOS_GR = butter(2, [2, 12], 'bandpass', fs=FSB, output='sos')
SOS_GR1K = butter(2, [2, 12], 'bandpass', fs=1000.0, output='sos')
_lib = None


def lib():
    global _lib
    if _lib is None:
        _lib = CA.load(LIB)
        _lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
        _lib.pvb_copy_diagnostic.restype = C.c_int
    return _lib


def read_song(i):
    p = str(MUSIC[i]); assert 'slakh2100' not in p
    x, fs = sf.read(p, always_2d=True, dtype='float64'); x = x[:, :2]
    g = np.gcd(fs, FS)
    return np.clip(resample_poly(x, FS // g, fs // g, axis=0), -1, 1).astype(np.float32)


def vec(prm):
    d = dict(CA.DEFAULTS); d.update(prm)
    return np.array([float(d[k]) for k in CA.PARAMS], np.float64)


def run(x, row, level_db, twin, capture=False):
    """-> y (N,2) output, gr (blocks, dB>=0 meter), layer (N,2) or None, latency. twin: out gain -25 dB, ceiling 0 (limiter idle), output scaled +25 dB."""
    L = lib()
    algo, prm = ROWS[row]
    kw = dict(APP, out_db=OUT_DB - (TWIN_DROP if twin else 0), ceil_db=0.0 if twin else CEIL_DB, vb_on=1, vb_algo=algo, vb_level_db=level_db)
    e = T.Engine(L, FS, **kw)
    try:
        if algo == 15:
            v = vec(prm)
            L.pvb_set_resultant.argtypes = [C.c_void_p, CA.DP, C.c_int]; L.pvb_set_resultant.restype = C.c_int
            assert L.pvb_set_resultant(e.h, v.ctypes.data_as(CA.DP), len(v)) == 1
        fields = 32 + L.pvb_param_count()
        if capture:
            L.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(x, np.float32).copy(); n = len(y)
        lay = np.zeros((n, 2), np.float32) if capture else None
        gr = np.zeros((n + BLOCK - 1) // BLOCK, np.float32)
        trb = np.empty(fields, np.float32); lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        gi = T.M['LIM_GR_DB']
        for k, i in enumerate(range(0, n, BLOCK)):
            b = y[i:i + BLOCK]; m = len(b)
            L.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            gr[k] = e.meters()[gi]
            if capture:
                assert L.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, trb.ctypes.data_as(T.FP), fields) == 1
                lay[i:i + m] = lb[:2 * m].reshape(m, 2)
        lat = int(L.pvb_latency(e.h))
    finally:
        e.close()
    if twin:
        s = np.float32(10 ** (TWIN_DROP / 20))
        y = y * s
        if lay is not None:
            lay = lay * s
    return y, gr, lay, lat


def env_db(sig, box=240):
    n = len(sig) // box
    r = np.sqrt(np.mean(sig[:n * box].reshape(n, box) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), -90.0)


WIN = 400; HOPM = 100; NFFT = 2048; ER = 200.0
_w = np.hanning(WIN); _f = np.fft.rfftfreq(NFFT, 1 / ER); _band = (_f >= 2) & (_f <= 12)


def mod_M(env):
    """B1 mod_series M (dB rms, 2-12 Hz) per 2 s window; returns array"""
    n = (len(env) - WIN) // HOPM + 1
    M = np.zeros(max(n, 0))
    for k in range(n):
        s = env[k * HOPM:k * HOPM + WIN].astype(np.float64)
        x = (s - s.mean()) * _w
        P = np.abs(np.fft.rfft(x, NFFT)) ** 2
        Pn = P / (NFFT * np.sum(_w ** 2)) * 2.0
        M[k] = np.sqrt(np.sum(Pn[_band]))
    return M


def block_series(y, pre, lay, gr, lat):
    """per-block series on the output timeline: layer-lo level (dB), layer-lo peak, pre-limiter peak (lin)."""
    n = len(y); nb = len(gr)
    lo = sosfiltfilt(SOS_LO, lay.mean(1).astype(np.float64))
    pad = nb * BLOCK - n
    lo_p = np.pad(lo, (0, pad)); pk_p = np.pad(np.abs(pre).max(1).astype(np.float64), (0, pad))
    r = lo_p.reshape(nb, BLOCK)
    lev = np.maximum(20 * np.log10(np.sqrt(np.mean(r ** 2, 1)) + 1e-12), -90.0)
    return lev, np.abs(r).max(1), pk_p.reshape(nb, BLOCK).max(1)


def bursts(lev, n=38, rise=6.0, floor=-60.0):
    """burst block: level >= median of the previous n blocks + rise dB and level > floor dBFS (history from the whole series)"""
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.concatenate([np.full(n, -90.0), lev])
    med = np.median(sliding_window_view(pad, n)[:len(lev)], axis=1)
    return (lev >= med + rise) & (lev > floor)


def fine_gr(y, pre):
    n1 = len(y) // 48
    a = y[:n1 * 48].astype(np.float64).reshape(n1, 48, 2); b = pre[:n1 * 48].astype(np.float64).reshape(n1, 48, 2)
    num = (a * b).sum((1, 2)); den = (b * b).sum((1, 2))
    g = np.where(den > 1e-10, num / np.maximum(den, 1e-30), 1.0)
    return -20 * np.log10(np.clip(g, 1e-3, 1.0))
