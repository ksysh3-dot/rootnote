"""S19-HP helpers: libraries (HEAD reference / 19.7 build), parameter vectors of n values, render with trace. Numbers only."""
import sys, ctypes as C
from pathlib import Path
HOME = Path.home()
for p in (HOME / 'r3-work/tools/pvb-harness', HOME / 'r3-work/tools/pvb-harness/study', HOME / 'r3a-dev/diag16', HOME / 'r3a-dev/verify_core'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import numpy as np
import research_core_api as CA
import test_engine as T

HP_DIR = HOME / 'r3a-dev/plan16/S19/HP'
LIB_HEAD = HP_DIR / 'lib_head/libpvbcapi.so'                               # committed HEAD (19 params)
LIB19 = HOME / 'r3-work/tools/pvb-harness/build_core19/libpvbcapi.so'      # 19.7 build (22 params)
LIB_M = HP_DIR / 'lib_m/libpvbcapi.so'                                     # 19.7 build with the compensation sign flipped (sign check only)
# v1.6-b = A5P row b3p2
B3P2 = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2, betaMin=.05, betaMax=.1, psiSlew=.03)
V15 = dict(voicing=0, ampSource=0)


def vec(prm, n=None):
    d = dict(CA.DEFAULTS); d.update(prm)
    v = np.array([float(d[k]) for k in CA.PARAMS], np.float64)
    return v if n is None else v[:n]


def set_vec(lib, eng, v):
    lib.pvb_set_resultant.argtypes = [C.c_void_p, CA.DP, C.c_int]
    lib.pvb_set_resultant.restype = C.c_int
    if lib.pvb_set_resultant(getattr(eng, 'h', eng), v.ctypes.data_as(CA.DP), len(v)) != 1:
        raise ValueError('pvb_set_resultant refused')


def try_vec(lib, eng, v):
    lib.pvb_set_resultant.argtypes = [C.c_void_p, CA.DP, C.c_int]
    lib.pvb_set_resultant.restype = C.c_int
    return int(lib.pvb_set_resultant(getattr(eng, 'h', eng), v.ctypes.data_as(CA.DP), len(v)))


def render(lib, x, v, algo=15, block=256, trace=True, sr=48000, **kw):
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    kw.setdefault('ramp_ms', 0)
    e = T.Engine(lib, sr, vb_on=1, vb_algo=algo, **kw)
    try:
        if algo == 15:
            set_vec(lib, e, v)
        hops = 0
        if trace and algo == 15:
            hops = int(len(x) * CA.CORE_FS / sr / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        y = np.ascontiguousarray(x).copy()
        for i in range(0, len(y), block):
            b = y[i:i + block]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        lat = int(lib.pvb_latency(e.h))
        tr = CA.trace_copy(lib, e, hops * CA.SLOTS) if (trace and algo == 15) else None
    finally:
        e.close()
    return y, tr, lat
