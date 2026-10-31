"""LOGOFF 'ringing' as the phone speaker would play it: the app chain's OUTPUT 150-400 Hz envelope after each low-band
hit (input onsets, output time axis = input + latency). Per hit: level at 40/80/150/250 ms relative to the 0-60 ms
peak, and the time to fall 10 dB. Variants: layer off, P1 default, P1 +6 dB (the three blind files, whose order the
user heard as off < default < +6), model 14 (P1 + C1). Input clipped to +-1. Usage: song_ring.py <song> <lib> [algos]"""
import json, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import test_engine as T

song, libpath = sys.argv[1:3]
FS = 48000
x, fs = sf.read(song, always_2d=True)
x48 = np.clip(resample_poly(x, 160, 147, axis=0) if fs == 44100 else x, -1, 1).astype(np.float32)
mono = x48.astype(float).mean(axis=1)
lo = sosfiltfilt(butter(4, [30, 150], btype='band', fs=FS, output='sos'), mono)
e = lo ** 2; k5, k150 = int(.005 * FS), int(.15 * FS)
fast = np.convolve(e, np.ones(k5) / k5, 'same'); slow = np.convolve(e, np.ones(k150) / k150, 'same')
ratio = 10 * np.log10((fast + 1e-20) / (np.r_[slow[:k150], slow[:-k150]] + 1e-20))
on = []; i = 0
while i < len(ratio):
    if ratio[i] > 8 and fast[i] > 1e-4 * fast.max(): on.append(i); i += k150
    else: i += 1
k10 = int(.01 * FS); band = butter(4, [150, 400], btype='band', fs=FS, output='sos')
env = lambda y: 10 * np.log10(np.convolve(y ** 2, np.ones(k10) / k10, 'same') + 1e-30)
lib = T.load_lib(libpath)
d0 = np.zeros(lib.pvb_param_count(), np.float32); lib.pvb_default_params(d0.ctypes.data_as(T.FP))
lv = float(d0[T.P['VB_LEVEL_DB']])
variants = [('off', dict(vb_on=0)), ('p1', dict(vb_on=1, vb_algo=6)), ('p1_plus6', dict(vb_on=1, vb_algo=6, vb_level_db=lv + 6)),
            ('m14_c1', dict(vb_on=1, vb_algo=14))]
res = dict(hits=len(on))
for name, kw in variants:
    eng = T.Engine(lib, FS, **kw); y = eng.process(x48, block=256); lat = eng.latency(); eng.close()
    E = env(sosfiltfilt(band, y.astype(float).mean(axis=1)))
    rows = []
    for o in on:
        s = o + lat
        if s + int(.4 * FS) > len(E): continue
        v = E[s:s + int(.4 * FS)]; p = int(np.argmax(v[:int(.06 * FS)])); pk = v[p]
        f10 = np.where(v[p:] <= pk - 10)[0]
        rows.append([v[int(ms * FS / 1000)] - pk for ms in (40, 80, 150, 250)] + [1000 * (f10[0] if len(f10) else len(v) - p) / FS, pk])
    R = np.array(rows); med = np.median(R, axis=0)
    res[name] = dict(n=len(R), rel_db_40_80_150_250=[round(float(v), 1) for v in med[:4]], fall10_ms=round(float(med[4]), 1),
                     fall10_p75=round(float(np.percentile(R[:, 4], 75)), 1), peak_db=round(float(med[5]), 1))
    print(name, json.dumps(res[name]), flush=True)
