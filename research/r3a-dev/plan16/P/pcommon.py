"""Plan16 P (16.15): render core / P1 through libpvbcapi.so with the diagnostic layer capture.
Run from tools/pvb-harness with PYTHONPATH=.:study"""
import sys, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
from pathlib import Path
import test_engine as T
import research_core_api as CA
import research_core_xcheck as X

FS = 48000
BLOCK = 256
LIB = Path('build_core/libpvbcapi.so').resolve()
lib = CA.load(LIB)
lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
lib.pvb_copy_diagnostic.restype = C.c_int
FIELDS = 32 + lib.pvb_param_count()


def render_capture(x, algo, dur=30.0, ceil_db=None):
    """x: mono float excerpt (>= dur+1 s). Returns dict(y, layer, full, lat, mingain): stereo output / the engine's diagnostic generated
    layer (after output filter + gain, aligned with the output, times mix*fade*gate*limiter gain) / full mix, all with the engine latency removed."""
    kw = dict(vb_on=1, vb_algo=algo, ramp_ms=0)
    if ceil_db is not None:
        kw['ceil_db'] = ceil_db
    e = T.Engine(lib, FS, **kw)
    try:
        if algo == 15:
            CA.set_resultant(lib, e)
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(np.stack([x, x], 1) if x.ndim == 1 else x, np.float32).copy()
        n = len(y)
        lay = np.zeros_like(y); full = np.zeros_like(y)
        tr = np.empty(FIELDS, np.float32)
        lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        for i in range(0, n, BLOCK):
            b = y[i:i + BLOCK]
            m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            ok = lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, tr.ctypes.data_as(T.FP), FIELDS)
            assert ok == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2); full[i:i + m] = fb[:2 * m].reshape(m, 2)
        lat = int(lib.pvb_latency(e.h))
    finally:
        e.close()
    N = int(dur * FS)
    sl = slice(lat, lat + N)
    return dict(y=y[sl].astype(np.float64), layer=lay[sl].astype(np.float64), full=full[sl].astype(np.float64), lat=lat)
