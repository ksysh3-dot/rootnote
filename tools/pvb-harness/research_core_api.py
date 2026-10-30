"""Python access to the Resultant core (algorithm 15, docs/RESULTANT_CORE.md): library loading, the 16 parameters, the voice
trace and a render helper. Host research only.

    import research_core_api as R
    lib = R.load('build_core/libpvbcapi.so')
    y, trace, latency = R.render(lib, x, sr=48000, algo=15, params=dict(voicing=1, levelDb=6), trace=True)
    tr = R.trace_dict(trace)          # field name -> array of shape (hops, 8): row = hop, column = voice slot

Run from tools/pvb-harness with PYTHONPATH=.:study (it uses test_engine.Engine for the engine parameters).
"""
import ctypes as C
import numpy as np
import test_engine as T

# the 16 parameters of pvb_set_resultant, in the order of spec 5.8, with their defaults
PARAMS = ('voicing', 'levelDb', 'ampSource', 'snrOnDb', 'snrFastDb', 'snrOffDb', 'tauOnMs', 'tauOffMs', 'betaMin',
          'betaMax', 'kappa', 'nMin', 'nFuture', 'psiSlew', 'crest', 'maxDfdtBirth')
DEFAULTS = dict(voicing=0, levelDb=0, ampSource=0, snrOnDb=15, snrFastDb=22, snrOffDb=6, tauOnMs=8, tauOffMs=30,
                betaMin=.2, betaMax=.9, kappa=1.0, nMin=30, nFuture=24, psiSlew=.12, crest=0, maxDfdtBirth=200)
# one record per voice slot (8 per hop), in the order of the spec
TRACE_FIELDS = ('hop', 'voice', 'track', 'state', 'coasting', 'f_track', 'f_osc', 'dfdt_s', 'A', 'c', 'sigma', 'Np',
                'snr_db', 'prominent', 'raw_db', 'res_db', 'subordinate', 'theta_hat', 'psi_2', 'psi_3', 'a_2', 'a_3')
SLOTS = 8
STATE_EMPTY, STATE_CAND, STATE_ON, STATE_REL = 0, 1, 2, 3
CORE_FS, HOP = 3000, 16          # core rate and hop length; hop h is core sample i_h = 383 + 16 h (analysis centre i_h - 382)
VB_RESULTANT = 15
DP = C.POINTER(C.c_double)


def bind(lib):
    """Sets the argtypes / restype of the Resultant core API (and of the diagnostic captures) on a library loaded elsewhere
    (test_engine.load_lib, research_p1plus.api): a 64-bit engine handle must not be passed as a C int. Idempotent."""
    lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]
    lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]
    lib.pvb_copy_harmonic.restype = C.c_int
    lib.pvb_set_resultant.argtypes = [C.c_void_p, DP, C.c_int]
    lib.pvb_set_resultant.restype = C.c_int
    lib.pvb_resultant_trace_enable.argtypes = [C.c_void_p, C.c_int]
    lib.pvb_resultant_trace_enable.restype = C.c_int
    lib.pvb_resultant_trace_copy.argtypes = [C.c_void_p, DP, C.c_int]
    lib.pvb_resultant_trace_copy.restype = C.c_int
    return lib


def load(path):
    """Loads libpvbcapi.so with the argtypes of the engine API and of the Resultant core API."""
    return bind(T.load_lib(str(path)))


def set_resultant(lib, engine, **kw):
    """Applies DEFAULTS overridden by kw (names of PARAMS) to the engine (an object with .h or a raw handle). Kept for any
    algorithm. Raises ValueError for an unknown name or a value the library refuses."""
    bad = set(kw) - set(PARAMS)
    if bad:
        raise ValueError(f'unknown Resultant parameter(s): {sorted(bad)}')
    bind(lib)
    v = np.array([float(kw.get(n, DEFAULTS[n])) for n in PARAMS], np.float64)
    handle = getattr(engine, 'h', engine)
    if lib.pvb_set_resultant(handle, v.ctypes.data_as(DP), len(v)) != 1:
        raise ValueError(f'pvb_set_resultant refused {dict(zip(PARAMS, v))}')


def trace_enable(lib, engine, hops):
    bind(lib)
    handle = getattr(engine, 'h', engine)
    if lib.pvb_resultant_trace_enable(handle, int(hops)) != 1:
        raise ValueError(f'pvb_resultant_trace_enable refused {hops} hops')


def trace_copy(lib, engine, max_rows):
    """The recorded rows as an array (hops * 8, 22); raises when the library reports an error."""
    bind(lib)
    handle = getattr(engine, 'h', engine)
    buf = np.empty(int(max_rows) * len(TRACE_FIELDS), np.float64)
    n = lib.pvb_resultant_trace_copy(handle, buf.ctypes.data_as(DP), buf.size)
    if n == -1:
        raise RuntimeError('Resultant trace not enabled')
    if n == -2:
        raise RuntimeError('Resultant trace buffer too small')
    if n == -3:
        raise RuntimeError('Resultant trace capacity exceeded: enable it with more hops')
    return buf[:n * len(TRACE_FIELDS)].reshape(n, len(TRACE_FIELDS)).copy()


def trace_dict(trace):
    """name -> array (hops, 8) from the (hops * 8, 22) rows of render()."""
    if trace is None:
        return None
    t = np.asarray(trace).reshape(-1, SLOTS, len(TRACE_FIELDS))
    return {n: t[:, :, i] for i, n in enumerate(TRACE_FIELDS)}


def hop_time(trace_hop, sr=48000):
    """Core index of a hop (field 0) -> (input time of the analysis centre, output time of the hop's first sample), in seconds
    of the engine input: c_h = i_h - 382 core samples, output sample n is input time n - 398 (spec 3), plus the module latency
    is not included."""
    return (np.asarray(trace_hop) - 382) / CORE_FS, (np.asarray(trace_hop) - 398) / CORE_FS


def render(lib, x, sr=48000, algo=VB_RESULTANT, params=None, trace=False, block=256, **engine_kw):
    """Renders x (float, (n,) mono or (n, 2) stereo) through the engine with the virtual bass algorithm `algo`.

    params  dict of Resultant parameters (names of PARAMS), applied before the first block (any algo; kept)
    trace   True: record the voice trace (algorithm 15 only; hops * 8 rows of 22 values, see TRACE_FIELDS)
    block   process() block length in frames
    engine_kw  engine parameters of test_engine.Engine (e.g. out_db=-18, vb_level_db=0); ramp_ms defaults to 0 here
               (parameter changes at the first block snap, as in the research scripts)
    Returns (y float32 (n, 2), trace ndarray (rows, 22) or None, latency in frames)."""
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    if x.ndim != 2 or x.shape[1] != 2:
        raise ValueError('x must be mono (n,) or stereo (n, 2)')
    engine_kw.setdefault('ramp_ms', 0)
    e = T.Engine(lib, sr, vb_on=1, vb_algo=algo, **engine_kw)
    try:
        if params is not None or algo == VB_RESULTANT:
            set_resultant(lib, e, **(params or {}))
        hops = 0
        if trace:
            hops = int(len(x) * CORE_FS / sr / HOP) + 64
            trace_enable(lib, e, hops)
        y = np.ascontiguousarray(x).copy()
        for i in range(0, len(y), block):
            b = y[i:i + block]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        lat = int(lib.pvb_latency(e.h))
        tr = trace_copy(lib, e, hops * SLOTS) if trace else None
    finally:
        e.close()
    return y, tr, lat
