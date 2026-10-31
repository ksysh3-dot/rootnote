"""Second control for the LOGOFF onset lag: the bass note CHANGES at the kick. 1 s cycle: note A for 0-0.5 s, then at
0.5 s a kick and note B (no gap, phase-continuous), or a 40 ms glide A->B. Lag = layer 150-400 Hz -6 dB rise point
minus input 30-150 Hz rise point at the change, and the layer level 10/20/40/80 ms after the change relative to its
0-150 ms peak. -12 dBFS. Usage: synth_lag2.py <lib>"""
import json, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as P

FS = 48000; lib = P.api(sys.argv[1])
t = np.arange(FS) / FS
def bass(fa, fb, glide=0.0):
    f = np.where(t < .5, fa, fb).astype(float)
    if glide: g = (t >= .5) & (t < .5 + glide); f[g] = fa + (fb - fa) * (t[g] - .5) / glide
    a = np.minimum(t / .005, 1) * np.minimum(1, np.maximum(0, (.98 - t) / .02))
    return a * np.sin(2 * np.pi * np.cumsum(f) / FS)
tk = np.maximum(t - .5, 0)
kick = (t >= .5) * np.exp(-tk / .12) * np.sin(2 * np.pi * np.cumsum(45 + 15 * np.exp(-tk / .03)) / FS)
k10 = int(.01 * FS)
env = lambda y: 10 * np.log10(np.convolve(y ** 2, np.ones(k10) / k10, 'same') + 1e-30)
lo = butter(4, [30, 150], btype='band', fs=FS, output='sos'); hi = butter(4, [150, 400], btype='band', fs=FS, output='sos')
for name, one in (('change_55_45', bass(55, 45)), ('change_55_45_kick', .7 * bass(55, 45) + .7 * kick),
                  ('glide40_55_45_kick', .7 * bass(55, 45, .04) + .7 * kick), ('same_48_kick', .7 * bass(48, 48) + .7 * kick)):
    x = np.tile(one, 8); x = (10 ** (-12 / 20) * x / np.abs(x).max()).astype(np.float32); x = np.stack([x, x], 1)
    r = P.render(lib, x, FS, 0, capture=True, stage_flags=0)
    lay = r['stem'].astype(float).mean(axis=1); lat = r['latency']
    Ei, El = env(sosfiltfilt(lo, x[:, 0].astype(float))), env(sosfiltfilt(hi, lay))
    lags, lv = [], []
    for n in range(2, 8):
        s = n * FS + FS // 2
        b = El[s + lat:s + lat + int(.15 * FS)]; pb = int(np.argmax(b))
        lags.append(1000 * int(np.argmax(b[:pb + 1] >= b[pb] - 6)) / FS)     # input change point is at 0
        lv.append([b[int(ms * FS / 1000)] - b[pb] for ms in (10, 20, 40, 80)] + [El[s + lat - int(.05 * FS)] - b[pb]])
    print(name, json.dumps(dict(lag_ms=round(float(np.median(lags)), 1), lags=[round(v, 1) for v in lags],
                                rel_db_10_20_40_80_and_before=[round(float(v), 1) for v in np.median(np.array(lv), axis=0)])), flush=True)
