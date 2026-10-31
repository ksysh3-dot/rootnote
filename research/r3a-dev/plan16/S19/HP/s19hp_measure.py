"""S19-HP measurement per (row, song): main metric (S19-L/H code), onset times, excursion proxy, analysis-trace hashes. numbers only.
usage: s19hp_measure.py ROW[,ROW..] [songs]; run via V16A/runpy.sh. Definitions: HP/CHOICES.md."""
import sys, json, time, hashlib, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/HP'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/L')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
from pathlib import Path
from scipy.signal import sosfilt, sosfiltfilt, butter
from scipy.ndimage import median_filter
import hpcommon as H
import p_primary as P
import s19l_measure as L
from b1_mod import mod_series
CA = H.CA; T = H.T
FS = 48000; BOX = 240; BLOCK = 256
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/HP/res'); OUT.mkdir(exist_ok=True)
HARN = H.HOME / 'r3-work/tools/pvb-harness'
ROWS = {
    'p1': ('build_core', 6, None, 0),
    'v15': ('build_core16b', 15, H.V15, 19),
    'b3p2': ('build_core16b', 15, H.B3P2, 19),
    'hp8_150c1': ('build_core19', 15, dict(H.B3P2, layerHpHz=150, layerHpOrder=8, layerHpComp=1), 22),
    'hp8_135c1': ('build_core19', 15, dict(H.B3P2, layerHpHz=135, layerHpOrder=8, layerHpComp=1), 22),
    'hp8_150c0': ('build_core19', 15, dict(H.B3P2, layerHpHz=150, layerHpOrder=8, layerHpComp=0), 22),
    'b3p2_19': ('build_core19', 15, H.B3P2, 22),     # v1.6-b on the new library (bit identity cross-check)
}
LR4 = np.vstack([butter(2, 100, 'highpass', fs=FS, output='sos')] * 2)
SOS400 = butter(4, [20, 400], 'bandpass', fs=FS, output='sos')
KEEP = [i for i in range(22) if i not in (18, 19)]
_libs = {}


def render_song(x, label):
    d, algo, prm, n = ROWS[label]
    if d not in _libs:
        _libs[d] = CA.load(HARN / d / 'libpvbcapi.so')
    lib = _libs[d]
    lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
    lib.pvb_copy_diagnostic.restype = C.c_int
    fields = 32 + lib.pvb_param_count()
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    tr = None
    try:
        if algo == 15:
            H.set_vec(lib, e, H.vec(prm, n))
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(x, np.float32).copy(); N = len(y)
        hops = 0
        if algo == 15:
            hops = int(N * CA.CORE_FS / FS / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        lay = np.zeros(N, np.float32)
        trb = np.empty(fields, np.float32); lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        for i in range(0, N, BLOCK):
            b = y[i:i + BLOCK]; m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            assert lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, trb.ctypes.data_as(T.FP), fields) == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2).mean(1)
        lat = int(lib.pvb_latency(e.h))
        if hops:
            tr = np.asarray(CA.trace_copy(lib, e, hops * CA.SLOTS))
    finally:
        e.close()
    return lay[lat:].astype(np.float64), tr


def births(tr):
    """onset times (s, block centre) of voice births: a slot is ON now and was not ON with the same voice id in the previous hop (CAND/new -> ON, REL -> ON)"""
    d = CA.trace_dict(tr)
    st, vid = d['state'], d['voice']
    on = st[1:] == 2
    cont = (st[:-1] == 2) & (vid[:-1] == vid[1:])
    b = on & ~cont
    hh = np.where(b.any(1))[0] + 1
    ts = CA.hop_time(d['hop'][hh, 0])[1] + 8.0 / CA.CORE_FS
    return np.sort(ts)


def env_db(sig):
    return L.env_db(sig)


def job(a):
    label, i = a
    f = OUT / f'{label}_s{i:02d}.json'
    if f.exists():
        return a
    t = time.time()
    xin = P.read_song(i)
    x, tr = render_song(xin, label)
    xm = xin.astype(np.float64).mean(1)[:len(x)]; del xin
    n = len(x)
    res = dict(label=label, song=i, n=n, segs=[])
    if tr is not None:
        res['tr_sha_all'] = hashlib.sha1(np.ascontiguousarray(tr).tobytes()).hexdigest()
        res['tr_sha_keep'] = hashlib.sha1(np.ascontiguousarray(tr[:, KEEP]).tobytes()).hexdigest()
        res['tr_shape'] = list(tr.shape)
        ons = births(tr)
    else:
        ons = np.zeros(0)
    # 20-140 Hz linear-phase band, 5 ms boxes
    S = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / FS)
    b14 = np.fft.irfft(S * L.ramp_mask(fr, 20, 140), n); del S
    nb = n // BOX
    eb = np.mean(b14[:nb * BOX].reshape(nb, BOX) ** 2, axis=1); del b14
    # excursion proxy: dry through the app input HP (LR4 100 Hz) + layer, band 20-400 Hz
    dry = sosfilt(LR4, xm)
    bs = sosfiltfilt(SOS400, dry + x); bd = sosfiltfilt(SOS400, dry)
    es, ed = env_db(bs), env_db(bd)
    for (t0, t1) in L.segs_for(i, n):
        i0, i1 = int(t0 * FS), int(t1 * FS); b0, b1 = i0 // BOX, i1 // BOX
        seg = dict(t0=t0, t1=t1, b0=b0, fft=L.fft_bands(x[i0:i1]), eb=eb[b0:b1].tolist(), e140=float(eb[b0:b1].mean()),
                   onsets=ons[(ons >= t0 - 0.1) & (ons < t1)].tolist())
        e0, e1 = int(round(t0 * 200)), int(round(t1 * 200))
        for nm, sig, ev in (('sum', bs, es), ('dry', bd, ed)):
            s = sig[i0:i1]; w = s[:len(s) // 9600 * 9600].reshape(-1, 9600)
            pk = 20 * np.log10(np.abs(w).max(1) + 1e-12)
            M = mod_series(ev[e0:e1])[1]
            seg[nm] = dict(peak=float(20 * np.log10(np.abs(s).max() + 1e-12)), pk200_med=float(np.median(pk)), M=float(M.mean()) if len(M) else None,
                           rms=float(10 * np.log10(np.mean(s ** 2) + 1e-30)))
        res['segs'].append(seg)
    res['sec'] = round(time.time() - t)
    json.dump(res, open(f, 'w')); print(label, i, res['sec'], flush=True)
    return a


if __name__ == '__main__':
    from multiprocessing import Pool
    rows = sys.argv[1].split(',')
    idx = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(14))
    with Pool(int(__import__('os').environ.get('NP', 6))) as p:
        for _ in p.imap_unordered(job, [(l, i) for i in idx for l in rows]):
            pass
