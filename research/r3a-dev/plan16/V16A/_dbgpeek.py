import sys, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S
lib = VC.load('/home/ksysh/r3a-dev/plan16/V16A/dbgsrc/libpvbcapi_dbg.so')
lib.a1p_dbg_n.restype = C.c_int
lib.a1p_dbg_copy.argtypes = [C.POINTER(C.c_double)]
x = S.stereo(S.low_notes())
y, tr, _ = VC.render(lib, x, VC.make_params(1.5, 8, 0))
n = lib.a1p_dbg_n(); print('n', n)
buf = (C.c_double * (6 * max(n, 1)))(); lib.a1p_dbg_copy(buf)
d = np.array(buf[:6 * n]).reshape(-1, 6)
print(d[:5]); print(d[-3:])
t = VC.CA.trace_dict(tr)
print(t['hop'][:3, 0], t['hop'][-3:, 0], t['hop'].shape)
