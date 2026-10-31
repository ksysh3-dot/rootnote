"""LOGOFF: the layer's share of the app output in 150-400 Hz around hits, as a time profile: 10 log10(E_layer/E_dry)
in windows 0-40, 40-80, 80-150, 150-250, 250-400 ms after each low-band hit, for the whole song and for the blind
excerpt (40-55 s). Layer = output(P1) - output(layer off) (same chain, same latency). Also P1 +6 dB.
Usage: song_share.py <song> <lib>"""
import json, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import test_engine as T

song, libpath = sys.argv[1:3]
FS = 48000
x, fs = sf.read(song, always_2d=True)
x48 = np.clip(resample_poly(x, 160, 147, axis=0) if fs == 44100 else x, -1, 1).astype(np.float32)
lo = sosfiltfilt(butter(4, [30, 150], btype='band', fs=FS, output='sos'), x48.astype(float).mean(axis=1))
e = lo ** 2; k5, k150 = int(.005 * FS), int(.15 * FS)
fast = np.convolve(e, np.ones(k5) / k5, 'same'); slow = np.convolve(e, np.ones(k150) / k150, 'same')
ratio = 10 * np.log10((fast + 1e-20) / (np.r_[slow[:k150], slow[:-k150]] + 1e-20))
on = []; i = 0
while i < len(ratio):
    if ratio[i] > 8 and fast[i] > 1e-4 * fast.max(): on.append(i); i += k150
    else: i += 1
band = butter(4, [150, 400], btype='band', fs=FS, output='sos')
lib = T.load_lib(libpath)
d0 = np.zeros(lib.pvb_param_count(), np.float32); lib.pvb_default_params(d0.ctypes.data_as(T.FP))
lv = float(d0[T.P['VB_LEVEL_DB']])
def run(**kw):
    eng = T.Engine(lib, FS, **kw); y = eng.process(x48, block=256); lat = eng.latency(); eng.close()
    return sosfiltfilt(band, y.astype(float).mean(axis=1)), lat
dry0, l0 = run(vb_on=0)
W = ((0, 40), (40, 80), (80, 150), (150, 250), (250, 400))
res = dict(hits=len(on))
VARIANTS = [('p1', dict(vb_on=1, vb_algo=6)), ('p1_plus6', dict(vb_on=1, vb_algo=6, vb_level_db=lv + 6))]
if len(sys.argv) > 3: VARIANTS = [(f'algo{a}', dict(vb_on=1, vb_algo=int(a))) for a in sys.argv[3].split(',')]
for name, kw in VARIANTS:
    y, lat = run(**kw)                                  # layer on adds latency: put the dry run on the same time axis
    dry = np.r_[np.zeros(lat - l0), dry0][:len(y)]; lay = y - dry
    res[name + '_residual_check_db'] = round(float(10 * np.log10(np.sum(lay[:lat + FS] ** 2) + 1e-30)), 1)
    for scope, sel in (('song', lambda o: True), ('excerpt_40_55', lambda o: 40 * FS <= o < 55 * FS)):
        rows = []
        for o in on:
            if not sel(o) or o + lat + int(.4 * FS) > len(dry): continue
            s = o + lat
            pw = lambda z, a, b: 10 * np.log10(np.mean(z[s + a * 48:s + b * 48] ** 2) + 1e-30)
            rows.append([pw(lay, a, b) - pw(dry, a, b) for a, b in W] + [pw(lay, a, b) for a, b in W] + [pw(dry, a, b) for a, b in W])
        R = np.median(np.array(rows), axis=0); k = len(W)
        res[f'{name}_{scope}'] = dict(n=len(rows), layer_over_dry_db=[round(float(v), 1) for v in R[:k]],
                                      layer_db=[round(float(v), 1) for v in R[k:2 * k]], dry_db=[round(float(v), 1) for v in R[2 * k:]])
        print(name, scope, json.dumps(res[f'{name}_{scope}']), flush=True)
