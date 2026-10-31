"""Opus check for 17.1: does algo 15 with the C++ defaults (the app path: pvb_set_resultant never called) equal
algo 15 with research_core_api.set_resultant (every harness measurement)?  Output and 22-field trace, bit for bit.
Run from tools/pvb-harness with PYTHONPATH=.:study"""
from pathlib import Path
import numpy as np
import test_engine as T
import research_core_api as CA
import research_core_signals as S

FS = 48000
lib = CA.load(Path('build_core/libpvbcapi.so').resolve())


def render(x, send):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=15, ramp_ms=0)
    try:
        if send:
            CA.set_resultant(lib, e)
        lib.pvb_resultant_trace_enable(e.h, 20000)
        y = np.ascontiguousarray(np.stack([x, x], 1) if x.ndim == 1 else x, np.float32).copy()
        for i in range(0, len(y), 256):
            b = y[i:i + 256]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        tr = np.zeros(20000 * 22 * 8)
        n = lib.pvb_resultant_trace_copy(e.h, tr.ctypes.data_as(CA.C.POINTER(CA.C.c_double)), len(tr))
    finally:
        e.close()
    return y, tr[:max(n, 0)]


x = np.asarray(S.load_excerpt(S.LOGOFF, 37.0, 12.0), np.float32)
ya, ta = render(x, False)
yb, tb = render(x, True)
print('set_resultant values sent:', getattr(CA, 'DEFAULTS', None))
print('output equal:', np.array_equal(ya, yb), 'max diff', float(np.abs(ya - yb).max()))
print('trace equal:', np.array_equal(ta, tb), 'len', len(ta), len(tb))
