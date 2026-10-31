"""LOGOFF: does the layer outlast the input bass after low-band hits, and does C1 (stage flag 8192) shorten only that
excess? Per hit (input 30-150 Hz onset, layer on its own time axis = input + engine latency):
- lag: layer 150-400 Hz envelope reaching -6 dB of its 0-150 ms peak, minus the input 30-150 Hz envelope doing the same.
- fall: time from the peak to -10 dB for the layer and for the input bass; excess_ms = layer fall - input fall.
- late ratio: layer/input energy 100-300 ms after the hit minus the song-wide median layer/input ratio (dB): the part
  of the tail that is not explained by the bass that really sustains.
- level: layer 150-400 Hz energy over the whole song and at 0-300 ms after hits (the effect that would be traded away).
Input clipped to +-1. Usage: song_tail.py <song> <lib> <out.json>"""
import json, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import research_p1plus as P

song, libpath, out = sys.argv[1:4]
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
k10 = int(.01 * FS)
env = lambda y: 10 * np.log10(np.convolve(y ** 2, np.ones(k10) / k10, 'same') + 1e-30)
Ein = env(lo)
band = butter(4, [150, 400], btype='band', fs=FS, output='sos')

def per_hit(Ely, lat):
    rows = []
    for o in on:
        s, t = o, o + lat
        if t + int(.4 * FS) > len(Ely) or s < k10: continue
        a, b = Ein[s:s + int(.4 * FS)], Ely[t:t + int(.4 * FS)]
        pa, pb = int(np.argmax(a[:int(.15 * FS)])), int(np.argmax(b[:int(.15 * FS)]))
        if b[pb] < Ely.max() - 60: continue                     # no layer at this hit
        rise = lambda v, p: int(np.argmax(v[:p + 1] >= v[p] - 6))
        fall = lambda v, p: (int(np.argmax(v[p:] <= v[p] - 10)) if (v[p:] <= v[p] - 10).any() else len(v) - p)
        late = slice(int(.1 * FS), int(.3 * FS))
        rows.append(dict(lag_ms=1000 * (rise(b, pb) - rise(a, pa)) / FS, layer_fall_ms=1000 * fall(b, pb) / FS,
                         in_fall_ms=1000 * fall(a, pa) / FS,
                         late_db=10 * np.log10(np.mean(10 ** (b[late] / 10)) / np.mean(10 ** (a[late] / 10)))))
    return rows

lib = P.api(libpath); res = dict(hits=len(on))
for name, st in (('p1', 0), ('p1_c1', 8192)):
    r = P.render(lib, x48, FS, 0, capture=True, stage_flags=st)
    lay = r['stem'].astype(float).mean(axis=1); lat = r['latency']
    ly = sosfiltfilt(band, lay); Ely = env(ly)
    n = min(len(Ely) - lat, len(Ein))
    song_ratio = float(np.median(Ely[lat:lat + n][::480] - Ein[:n][::480]))
    rows = per_hit(Ely, lat); m = lambda k, q=50: round(float(np.percentile([v[k] for v in rows], q)), 1)
    hw = np.zeros(len(ly), bool)
    for o in on: hw[o + lat:o + lat + int(.3 * FS)] = True
    res[name] = dict(n=len(rows), latency=lat, lag_ms=m('lag_ms'), lag_p90=m('lag_ms', 90),
                     layer_fall_ms=m('layer_fall_ms'), in_fall_ms=m('in_fall_ms'),
                     excess_fall_ms=round(float(np.median([v['layer_fall_ms'] - v['in_fall_ms'] for v in rows])), 1),
                     late_excess_db=round(float(np.median([v['late_db'] for v in rows]) - song_ratio), 2),
                     layer_db_song=round(float(10 * np.log10(np.mean(ly ** 2))), 2),
                     layer_db_hits=round(float(10 * np.log10(np.mean(ly[hw[:len(ly)]] ** 2))), 2))
    res[name + '_stem'] = lay; print(name, json.dumps(res[name]), flush=True)
a, b = res.pop('p1_stem'), res.pop('p1_c1_stem')
res['c1_vs_p1_diff_db'] = round(float(10 * np.log10(np.sum((a - b) ** 2) / np.sum(a ** 2))), 1)
print('diff', res['c1_vs_p1_diff_db'])
json.dump(res, open(out, 'w'), indent=1)
