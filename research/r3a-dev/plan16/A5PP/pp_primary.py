"""A5 primary metric (18.9): 20-150 / 150-600 Hz layer ratio and >6 dB per-hop jumps of the rendered k=2 amplitude, in the user-confirmed windows.
Renders the two whole songs (Apparition, Reminiscence; read in place, never copied) with one row, as b12_render.py / b12common.py (diagnostic layer capture,
engine latency removed, layer band = zero-phase 4th-order Butterworth, mono mean of the two layer channels). Nothing but numbers is saved.
usage: a5_primary.py LABEL   (rows: a5pprows.ROWS)"""
import sys, json, time, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5PP'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly, butter, sosfiltfilt
import a5ppcommon as AC
import a5pprows as AR
CA = AC.CA; T = AC.T
from multiprocessing import Pool

FS = 48000; BLOCK = 256
MUSIC = sorted(Path('/mnt/c/Users/ksysh/Music/vanila').glob('*.flac'))
SONG_IDX = {'app': 9, 'rem': 6}
# (song, t0, t1) 2 s windows; Apparition 3:21-3:25 is taken as two 2 s windows
WINDOWS = [('app', 52.0, 54.0), ('app', 88.5, 90.5), ('app', 123.5, 125.5), ('app', 201.0, 203.0), ('app', 203.0, 205.0), ('rem', 96.0, 98.0), ('rem', 113.0, 115.0)]
SOS_LO = butter(4, [20, 150], 'bandpass', fs=FS, output='sos')
SOS_MID = butter(4, [150, 600], 'bandpass', fs=FS, output='sos')
A_IDX = CA.TRACE_FIELDS.index('a_2'); ST_IDX = CA.TRACE_FIELDS.index('state'); V_IDX = CA.TRACE_FIELDS.index('voice')


def read_song(i):
    p = str(MUSIC[i]); assert 'slakh2100' not in p
    x, fs = sf.read(p, always_2d=True, dtype='float64'); x = x[:, :2]
    g = np.gcd(fs, FS)
    return np.clip(resample_poly(x, FS // g, fs // g, axis=0), -1, 1).astype(np.float32)


def render_song(x, label, with_trace=True):
    lib, algo, prm = AR.engine(label)
    lib.pvb_copy_diagnostic.argtypes = [C.c_void_p, T.FP, T.FP, C.c_int, T.FP, C.c_int]
    lib.pvb_copy_diagnostic.restype = C.c_int
    fields = 32 + lib.pvb_param_count()
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    tr = None
    try:
        if algo == 15:
            CA.set_resultant(lib, e, **prm)
        lib.pvb_set_diagnostic_capture(e.h, 1)
        y = np.ascontiguousarray(x, np.float32).copy(); n = len(y)
        hops = 0
        if algo == 15 and with_trace:
            hops = int(n * CA.CORE_FS / FS / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        lay = np.zeros(n, np.float32)
        trb = np.empty(fields, np.float32); lb = np.empty(2 * BLOCK, np.float32); fb = np.empty(2 * BLOCK, np.float32)
        for i in range(0, n, BLOCK):
            b = y[i:i + BLOCK]; m = len(b)
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), m)
            assert lib.pvb_copy_diagnostic(e.h, lb.ctypes.data_as(T.FP), fb.ctypes.data_as(T.FP), 2 * m, trb.ctypes.data_as(T.FP), fields) == 1
            lay[i:i + m] = lb[:2 * m].reshape(m, 2).mean(1)
        lat = int(lib.pvb_latency(e.h))
        if hops:
            tr = CA.trace_dict(CA.trace_copy(lib, e, hops * CA.SLOTS))
    finally:
        e.close()
    return lay[lat:].astype(np.float64), tr


def jumps(tr, t0, t1, thr_db=6.0):
    """per-hop >thr_db changes of the rendered k=2 amplitude a_2 of one voice (same slot, same voice id, ON/REL in both hops, both amplitudes > 1e-7);
    returns (count, number of voice-hop pairs checked)"""
    ts = CA.hop_time(tr['hop'][:, 0])[1]
    sel = np.where((ts >= t0) & (ts < t1))[0]
    sel = sel[sel >= 1]
    a = tr['a_2']; st = tr['state']; vid = tr['voice']
    a1, a0 = a[sel], a[sel - 1]
    ok = (vid[sel] == vid[sel - 1]) & (st[sel] >= 2) & (st[sel - 1] >= 2) & (a1 > 1e-7) & (a0 > 1e-7)
    d = np.abs(20 * np.log10(np.where(ok, a1, 1.0) / np.where(ok, a0, 1.0)))
    return int((ok & (d > thr_db)).sum()), int(ok.sum())


def job(a):
    label, sk = a
    t = time.time()
    lay, tr = render_song(read_song(SONG_IDX[sk]), label)
    lo = sosfiltfilt(SOS_LO, lay); mid = sosfiltfilt(SOS_MID, lay)
    out = []
    for (s, t0, t1) in WINDOWS:
        if s != sk:
            continue
        i0, i1 = int(t0 * FS), int(t1 * FS)
        pl, pm = float(np.mean(lo[i0:i1] ** 2)), float(np.mean(mid[i0:i1] ** 2))
        j, nchk = jumps(tr, t0, t1) if tr is not None else (None, None)
        out.append(dict(song=s, t0=t0, t1=t1, p_lo=pl, p_mid=pm, jumps=j, checked=nchk))
    return label, sk, out, time.time() - t


if __name__ == '__main__':
    labels = sys.argv[1:]
    res = {}
    with Pool(min(12, 2 * len(labels))) as p:
        for label, sk, out, dt in p.imap_unordered(job, [(l, s) for l in labels for s in SONG_IDX]):
            res.setdefault(label, []).extend(out)
            print(label, sk, round(dt), flush=True)
    for label, rows in res.items():
        json.dump(rows, open(AC.A5_DIR / f'primary_{label}.json', 'w'), indent=1)
