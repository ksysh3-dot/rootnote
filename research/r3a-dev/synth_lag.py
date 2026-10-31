"""Control for the LOGOFF onset lag: known onsets. A 48 Hz sine note (5 ms attack, 400 ms, 600 ms gap), alone and with
a 60->45 Hz kick at the same instant, at -12 dBFS. Same lag/fall measure as song_tail.py (layer 150-400 Hz vs input
30-150 Hz, -6 dB rise point, 10 ms envelope). Usage: synth_lag.py <lib>"""
import json, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as P

FS = 48000; lib = P.api(sys.argv[1])
t = np.arange(int(1.0 * FS)) / FS
def note(f=48.0):
    a = np.minimum(t / .005, 1) * (t < .4) * np.minimum(1, np.maximum(0, (.42 - t) / .02)); return a * np.sin(2 * np.pi * f * t)
def kick():
    ph = 2 * np.pi * np.cumsum(45 + 15 * np.exp(-t / .03)) / FS; return np.exp(-t / .12) * np.sin(ph)
k10 = int(.01 * FS)
env = lambda y: 10 * np.log10(np.convolve(y ** 2, np.ones(k10) / k10, 'same') + 1e-30)
lo = butter(4, [30, 150], btype='band', fs=FS, output='sos'); hi = butter(4, [150, 400], btype='band', fs=FS, output='sos')
res = {}
for name, one in (('sine', note()), ('sine_kick', .7 * note() + .7 * kick()), ('kick', kick())):
    x = np.tile(one, 8); x = (10 ** (-12 / 20) * x / np.abs(x).max()).astype(np.float32)
    x = np.stack([x, x], 1)
    r = P.render(lib, x, FS, 0, capture=True, stage_flags=0)
    lay = r['stem'].astype(float).mean(axis=1); lat = r['latency']
    Ei, El = env(sosfiltfilt(lo, x[:, 0].astype(float))), env(sosfiltfilt(hi, lay))
    lags, falls = [], []
    for n in range(2, 8):                              # skip the first notes (engine settling)
        s = n * FS; a, b = Ei[s:s + int(.15 * FS)], El[s + lat:s + lat + int(.15 * FS)]
        pa, pb = int(np.argmax(a)), int(np.argmax(b))
        lags.append(1000 * (int(np.argmax(b[:pb + 1] >= b[pb] - 6)) - int(np.argmax(a[:pa + 1] >= a[pa] - 6))) / FS)
        # layer level at fixed times after the onset, relative to its 0-500 ms peak
        bb = El[s + lat:s + lat + int(.5 * FS)]; pk = bb.max()
        falls.append([round(float(bb[int(ms * FS / 1000)] - pk), 1) for ms in (10, 20, 40, 80, 200, 420, 460)])
    res[name] = dict(latency=lat, lag_ms=round(float(np.median(lags)), 1), lag_all=lags,
                     layer_db_at_10_20_40_80_200_420_460ms=np.median(np.array(falls), axis=0).tolist())
    print(name, json.dumps(res[name]), flush=True)
