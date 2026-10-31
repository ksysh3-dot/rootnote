"""B1 helpers. Run from ~/r3-work/tools/pvb-harness with PYTHONPATH=.:study (read-only use of the harness)."""
import sys, glob, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly, butter, sosfiltfilt
import api084 as CA          # copy of research_core_api.py at 084ea45 (18 params)
import test_engine as T

FS = 48000
BLOCK = 256
B1 = Path('/home/ksysh/r3a-dev/plan16/B1')
HARN = Path('/home/ksysh/r3-work/tools/pvb-harness')
MUSIC = sorted(glob.glob('/mnt/c/Users/ksysh/Music/vanila/*.flac'))
ENGINES = {  # name: (lib dir, algo, params)
    'P1': ('build_core', 6, None),
    'v15': ('build_core', 15, 'default16'),
    'v16a': ('build_core16a', 15, dict(capRho=1.5)),
}
BOX = 240  # 5 ms at 48 kHz
SOS_L = butter(4, [150, 600], 'bandpass', fs=FS, output='sos')   # layer band
SOS_I = butter(4, [40, 600], 'bandpass', fs=FS, output='sos')    # input low band
FLOOR_DB = -90.0


def read_song(i):
    p = MUSIC[i]
    assert 'slakh2100' not in p
    x, fs = sf.read(p, always_2d=True, dtype='float64')
    x = x[:, :2]
    g = np.gcd(fs, FS)
    x = resample_poly(x, FS // g, fs // g, axis=0)
    return np.clip(x, -1, 1).astype(np.float32)


def env_db(sig):
    """5 ms non-overlapping box RMS in dB re full scale, floor FLOOR_DB."""
    n = len(sig) // BOX
    r = np.sqrt(np.mean(sig[:n * BOX].reshape(n, BOX) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), FLOOR_DB)


def band_env(sig, sos):
    return env_db(sosfiltfilt(sos, sig))


def render(x, eng, trace=False):
    d, algo, prm = ENGINES[eng]
    lib = CA.load(HARN / d / 'libpvbcapi.so')
    lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
    lib.pvb_copy_diagnostic.restype = C.c_int
    fields = 32 + lib.pvb_param_count()
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    tr = None
    try:
        if algo == 15:
            if prm == 'default16':   # build_core predates capRho/windowCreep: 16 parameters
                v = np.array([float(CA.DEFAULTS[n]) for n in CA.PARAMS[:16]], np.float64)
                assert lib.pvb_set_resultant(e.h, v.ctypes.data_as(CA.DP), 16) == 1
            else:
                CA.set_resultant(lib, e, **prm)
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(np.stack([x, x], 1) if x.ndim == 1 else x, np.float32).copy()
        n = len(y)
        hops = 0
        if trace and algo == 15:
            hops = int(n * CA.CORE_FS / FS / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        lay = np.zeros(n, np.float32)
        trb = np.empty(fields, np.float32)
        lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        for i in range(0, n, BLOCK):
            b = y[i:i + BLOCK]; m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            ok = lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, trb.ctypes.data_as(T.FP), fields)
            assert ok == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2).mean(1)
        lat = int(lib.pvb_latency(e.h))
        if hops:
            tr = CA.trace_dict(CA.trace_copy(lib, e, hops * CA.SLOTS))
    finally:
        e.close()
    return lay[lat:].astype(np.float64), tr, lat
