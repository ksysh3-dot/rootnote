"""B1-2 helpers. Run from ~/r3-work/tools/pvb-harness with PYTHONPATH=.:study (read-only use of the harness).
Uses b12/api5c1.py (copy of research_core_api.py at 5c1c62c, 19 params) for build_core16b and the 16 first params for build_core."""
import sys, glob, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly, butter, sosfiltfilt, sosfreqz
import api5c1 as CA
import test_engine as T

FS = 48000
BLOCK = 256
B1 = Path('/home/ksysh/r3a-dev/plan16/B1')
B12 = B1 / 'b12'
TMP = B12 / 'tmp'            # derived layers live only here, deleted at the end
HARN = Path('/home/ksysh/r3-work/tools/pvb-harness')
MUSIC = sorted(glob.glob('/mnt/c/Users/ksysh/Music/vanila/*.flac'))
SONG_IDX = {'app': 9, 'rem': 6}
ENGINES = {
    'P1': ('build_core', 6, None),
    'v15': ('build_core', 15, 'default16'),
    'v16b': ('build_core16b', 15, dict(capRho=1.5, windowCreep=16, creepMode=2)),
}
# candidate-2 windows: (song key, t0, t1)
EXT = [('app', 178.0, 222.0), ('rem', 0.0, 400.0)]
WINDOWS = [('app', 52.0, 54.0), ('app', 88.5, 90.5), ('app', 123.5, 125.5), ('rem', 52.0, 54.0)]
OUT_SOS = np.array([[0.6620158372026176, -1.3240316744052352, 0.6620158372026176, 1.0, -1.4796742169311934, 0.5558215432824889],
                    [1.0, -2.0, 1.0, 1.0, -1.7009643319435257, 0.7884997398152979],
                    [0.20657208382614792, 0.41314416765229584, 0.20657208382614792, 1.0, -0.3695273773512414, 0.19581571265583306]])
# NOTE: kOutSos is defined at the 3 kHz core rate? -> checked in analysis (b12_filter_check.py); see mag_out()
SOS_LO = butter(4, [20, 150], 'bandpass', fs=FS, output='sos')
SOS_MID = butter(4, [150, 600], 'bandpass', fs=FS, output='sos')


def read_song(i):
    p = MUSIC[i]
    assert 'slakh2100' not in p
    x, fs = sf.read(p, always_2d=True, dtype='float64')
    x = x[:, :2]
    g = np.gcd(fs, FS)
    x = resample_poly(x, FS // g, fs // g, axis=0)
    return np.clip(x, -1, 1).astype(np.float32)


def render(x, eng, windows=None):
    """Whole-song render. Returns layer (mono, latency removed), v15-type trace dict or None, P1 harmonic rows (kept only for the
    windows (t0-1.5, t1+1.5) in core-index time) or None."""
    d, algo, prm = ENGINES[eng]
    lib = CA.load(HARN / d / 'libpvbcapi.so')
    lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
    lib.pvb_copy_diagnostic.restype = C.c_int
    fields = 32 + lib.pvb_param_count()
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    tr = None; hrows = []
    HF = 28 + 56 * 12
    try:
        if algo == 15:
            if prm == 'default16':
                v = np.array([float(CA.DEFAULTS[n]) for n in CA.PARAMS[:16]], np.float64)
                assert lib.pvb_set_resultant(e.h, v.ctypes.data_as(CA.DP), 16) == 1
            else:
                CA.set_resultant(lib, e, **prm)
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(x, np.float32).copy()
        n = len(y)
        hops = 0
        if algo == 15:
            hops = int(n * CA.CORE_FS / FS / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        lay = np.zeros(n, np.float32)
        trb = np.empty(fields, np.float32)
        lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        hb = np.empty(72 * HF, np.float32)
        keep = [(t0 - 1.5, t1 + 1.5) for (_, t0, t1) in (windows or [])]
        for i in range(0, n, BLOCK):
            b = y[i:i + BLOCK]; m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            ok = lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, trb.ctypes.data_as(T.FP), fields)
            assert ok == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2).mean(1)
            if True:
                ts = i / FS
                if any(a <= ts <= b_ for a, b_ in keep):
                    nr = lib.pvb_copy_harmonic(e.h, hb.ctypes.data_as(T.FP), hb.size)
                    assert nr >= 0
                    if nr:
                        r = hb[:nr * HF].reshape(nr, HF).copy(); r[:, 0] += i
                        hrows.append(r)
        lat = int(lib.pvb_latency(e.h))
        if hops:
            tr = CA.trace_dict(CA.trace_copy(lib, e, hops * CA.SLOTS))
    finally:
        e.close()
    h = np.vstack(hrows) if hrows else None
    return lay[lat:].astype(np.float64), tr, h, lat
