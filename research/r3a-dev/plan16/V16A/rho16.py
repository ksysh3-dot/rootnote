"""16.15 output-based silence-layer ratio rho = E_sil/E_act (plan16/P: same masks, band 150-700 Hz, t >= 4 s main) for the 18.3 rows.
Core rows rendered here with the v1.6-a library (diagnostic layer capture, 10 V6 songs 0-30 s, Slakh train); the P1 layers are plan16/P/cache (layer_<key>_6.npy, build_core P1 == ref).
usage: rho16.py"""
import sys, json, ctypes as C, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
import multiprocessing as mp
import vcommon as VC
import test_engine as T
import research_core_xcheck as X
import p_main as PM
from scipy.signal import sosfiltfilt

lib = VC.load(str(VC.LIB16A))
lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
lib.pvb_copy_diagnostic.restype = C.c_int
FIELDS = 32 + lib.pvb_param_count()
FS = 48000; BLOCK = 256
ROWS = {'v1.5': (0, 0), 'A1 8': (0, 8), 'A1 16': (0, 16), 'A1 32': (0, 32), 'A2 1.5': (1.5, 0), 'A1+A2 16/1.5': (1.5, 16)}
for a in sys.argv[1:]:
    r, c = a.split(':'); ROWS[f'A1+A2 {c}/{r}'] = (float(r), float(c))
CACHE = VC.V_DIR / 'cache'; CACHE.mkdir(exist_ok=True)


def capture(x, par):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=15, ramp_ms=0)
    try:
        VC.set_vec(lib, e, VC.make_params(par[0], par[1]))
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(np.stack([x, x], 1) if x.ndim == 1 else x, np.float32).copy()
        lay = np.zeros_like(y)
        tr = np.empty(FIELDS, np.float32); lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        for i in range(0, len(y), BLOCK):
            b = y[i:i + BLOCK]; m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            assert lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, tr.ctypes.data_as(T.FP), FIELDS) == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2)
        lat = int(lib.pvb_latency(e.h))
    finally:
        e.close()
    return lay[lat:lat + int(30.0 * FS), 0].astype(np.float32)


def job(args):
    key, name = args
    p = CACHE / f'layer_{key}_{name.replace(" ", "_").replace("/", "_")}.npy'
    if not p.exists():
        x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
        np.save(p, capture(x, ROWS[name]))
    return key, name


def energies(key, lay):
    mk = PM.song_masks(key)
    e = sosfiltfilt(PM.SOS48, lay.astype(np.float64)[:PM.N]) ** 2
    ok = PM.T_ >= 4.0
    act = mk['main']
    return dict(E_sil=float(e[ok & ~act].sum()), E_act=float(e[ok & act].sum()), E_sil_drum=float(e[ok & ~act & mk['near']].sum()))


if __name__ == '__main__':
    t0 = time.time()
    jobs = [(k, n) for n in ROWS for k in PM.SONGS]
    with mp.get_context('fork').Pool(14) as pool:
        pool.map(job, jobs, chunksize=1)
    print('rendered', round(time.time() - t0), flush=True)
    out = {}
    en = {}
    en['P1'] = {k: energies(k, np.load(PM.CACHE / f'layer_{k}_6.npy')) for k in PM.SONGS}
    for n in ROWS:
        en[n] = {k: energies(k, np.load(CACHE / f'layer_{k}_{n.replace(" ", "_").replace("/", "_")}.npy')) for k in PM.SONGS}
    for n, d in en.items():
        S = sum(d[k]['E_sil'] for k in PM.SONGS); A = sum(d[k]['E_act'] for k in PM.SONGS)
        Sd = sum(d[k]['E_sil_drum'] for k in PM.SONGS)
        S4 = sum(d[k]['E_sil'] for k in PM.SONGS if k != 'Track00040'); A4 = sum(d[k]['E_act'] for k in PM.SONGS if k != 'Track00040')
        out[n] = dict(rho=S / A, E_sil=S, E_act=A, drum_near_share=Sd / S, rho_noT40=S4 / A4,
                      per_song={k: dict(E_sil=d[k]['E_sil'], E_act=d[k]['E_act']) for k in PM.SONGS})
    r15 = out['v1.5']['rho']; p1 = out['P1']['rho']
    for n, o in out.items():
        o['rho_vs_v15'] = o['rho'] / r15; o['r_P1_over_row'] = p1 / o['rho']
        print(f'{n:14s} rho {o["rho"]:.4f}  vs v1.5 {o["rho"] / r15:.3f}  r(P1/row) {p1 / o["rho"]:.3f}  E_act {o["E_act"]:.4g}  E_sil {o["E_sil"]:.4g} drum-near {o["drum_near_share"]:.3f}  noT40 {o["rho_noT40"]:.4f}')
    json.dump(out, open(VC.V_DIR / 'rho16.json', 'w'), indent=1)
