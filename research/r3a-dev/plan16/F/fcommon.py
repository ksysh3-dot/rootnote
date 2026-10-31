"""Brief F helpers: render with an explicit parameter vector (16 or 17 values), cap statistics, paths. Slakh TRAIN only."""
import sys, os, ctypes as C
from pathlib import Path
HOME = Path.home()
for p in (HOME / 'r3-work/tools/pvb-harness', HOME / 'r3-work/tools/pvb-harness/study', HOME / 'r3a-dev/diag16', HOME / 'r3a-dev/verify_core'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import numpy as np
import research_core_api as CA
import test_engine as T

F_DIR = HOME / 'r3a-dev/plan16/F'
LIB15 = F_DIR / 'build_v15/libpvbcapi.so'                       # unmodified HEAD (v1.5)  == build_core
LIB151 = HOME / 'r3-work/tools/pvb-harness/build_core151/libpvbcapi.so'
BASE16 = [CA.DEFAULTS[n] for n in CA.PARAMS]                    # defaults, 16 values (voicing 0, ampSource 0)


def load(path):
    lib = CA.load(path)
    try:
        lib.pvb_resultant_cap_stats.argtypes = [C.POINTER(C.c_double)]
        lib.pvb_resultant_cap_stats.restype = None
    except AttributeError:
        pass
    return lib


def cap_stats(lib):
    a = np.zeros(2)
    try:
        lib.pvb_resultant_cap_stats(a.ctypes.data_as(C.POINTER(C.c_double)))
    except AttributeError:
        return None
    return a


def make_params(rho=None, n17=None):
    """rho None -> 16 values (v1.5 call); rho = number -> 17 values with capRho = rho"""
    v = list(BASE16)
    if rho is not None:
        v.append(float(rho))
    return np.array(v, np.float64)


def set_vec(lib, eng, v):
    lib.pvb_set_resultant.argtypes = [C.c_void_p, CA.DP, C.c_int]
    lib.pvb_set_resultant.restype = C.c_int
    h = getattr(eng, 'h', eng)
    if lib.pvb_set_resultant(h, v.ctypes.data_as(CA.DP), len(v)) != 1:
        raise ValueError('pvb_set_resultant refused')


def render(lib, x, pvec, algo=15, block=256, trace=True, sr=48000, **kw):
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    kw.setdefault('ramp_ms', 0)
    e = T.Engine(lib, sr, vb_on=1, vb_algo=algo, **kw)
    try:
        if algo == 15:
            set_vec(lib, e, pvec)
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
