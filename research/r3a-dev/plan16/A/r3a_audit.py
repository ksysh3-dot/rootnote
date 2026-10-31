"""16.2 R3-a audit, empirical part: is the host stage flag 8388608 (StageSubOctaveNoHold) live in algo 15 and in the P1 path (algo 6)?
Track00060 36-48 s excerpt, engine run with a stage probe attached with flags 0 and 8388608 (pvb_stage_attach(handle, flags, capacity)):
  algo 15 (candidate lib, config A): output bit-identical?     algo 6 (P1) on the reference lib and on the candidate lib: output changed?
usage (from diag16): ./run.sh ../plan16/A/r3a_audit.py"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import ctypes as C
import numpy as np
import research_core_xcheck as X
import test_engine as T

FS = 48000
DP = C.POINTER(C.c_double)
x = X.read_excerpt(X.SLAKH / 'Track00060' / 'mix.flac', 36.0, 12.0)
x = np.ascontiguousarray(np.concatenate([x, np.zeros((int(.3 * FS), 2), np.float32)]))


def run(lib_path, algo, flags):
    lib = X.open_lib(lib_path)
    lib.pvb_stage_attach.argtypes = [C.c_void_p, C.c_uint, C.c_int]; lib.pvb_stage_attach.restype = C.c_void_p
    lib.pvb_stage_detach.argtypes = [C.c_void_p]
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, vb_level_db=0.0, out_db=-5.0, ramp_ms=0)
    h = None
    try:
        if algo == 15:
            v = np.array([X.CFG['A'].get(n, d) for n, d in zip(X.PNAMES, X.PDEF)], np.float64)
            assert lib.pvb_set_resultant(e.h, v.ctypes.data_as(DP), len(v)) == 1
        h = lib.pvb_stage_attach(e.h, flags, 40000)
        assert h, 'attach refused'
        y = x.copy()
        for i in range(0, len(y), 256):
            b = y[i:i + 256]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
    finally:
        if h:
            lib.pvb_stage_detach(h)
        e.close()
    return y


out = {}
for name, path, algo in (('algo15_candidate', X.CAND, 15), ('algo6_P1_reference_lib', X.REF, 6), ('algo6_P1_candidate_lib', X.CAND, 6)):
    y0 = run(path, algo, 0); y1 = run(path, algo, 8388608)
    d = np.abs(y0 - y1)
    out[name] = dict(bit_identical=bool(np.array_equal(y0, y1)), max_abs_diff=float(d.max()), n_diff_samples=int((d > 0).sum()), out_rms=float(np.sqrt(np.mean(y0 ** 2))))
    print(name, out[name], flush=True)
json.dump(out, open('/home/ksysh/r3a-dev/plan16/A/r3a_audit.json', 'w'), indent=1)
