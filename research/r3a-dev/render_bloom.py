"""LOGOFF blind set for the post-hit bloom (offline, non-causal, listening only - not an engine candidate).
Full app chain at defaults with the layer off (dry) and P1 (vb_algo 6); layer = P1 output - dry on one time axis.
Variants on the 40-55 s excerpt: P1 as rendered (twice: the null pair), 'advance' = in each hit window the layer is
taken 35 ms later in its own time (harmonics land with the kick), 'duck' = layer -6 dB from 30 to 150 ms after each
hit (the bloom pressed down). 20 ms raised-cosine edges. Hits = input 30-150 Hz onsets (as song_share.py).
Files get shuffled names; the key goes to a JSON whose SHA-256 is printed before anyone listens.
Usage: render_bloom.py <song> <lib> <outdir> <keyfile> <seed>"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import test_engine as T

song, libpath, outdir, keyfile, seed = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4], int(sys.argv[5])
FS = 48000; T0, T1 = 40.0, 55.0
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
lib = T.load_lib(libpath)
def run(**kw):
    eng = T.Engine(lib, FS, **kw); y = eng.process(x48, block=256); lat = eng.latency(); eng.close(); return y.astype(float), lat
dry0, l0 = run(vb_on=0); y, lat = run(vb_on=1, vb_algo=6)
dry = np.r_[np.zeros((lat - l0, 2)), dry0][:len(y)]; lay = y - dry
ms = lambda v: int(v * FS / 1000)
def window(a, b, edge=20):
    """raised-cosine window over output samples [a, b] ms after every hit"""
    w = np.zeros(len(y))
    r = .5 - .5 * np.cos(np.linspace(0, np.pi, ms(edge)))
    for o in on:
        s, t = o + lat + ms(a), o + lat + ms(b)
        if s < 0 or t + ms(edge) > len(w): continue
        w[s:s + ms(edge)] = np.maximum(w[s:s + ms(edge)], r); w[s + ms(edge):t] = 1
        w[t:t + ms(edge)] = np.maximum(w[t:t + ms(edge)], r[::-1])
    return w[:, None]
D = ms(35); later = np.r_[lay[D:], np.zeros((D, 2))]
wa = window(-20, 150); advance = dry + (1 - wa) * lay + wa * later
duck = dry + lay * (1 - (1 - 10 ** (-6 / 20)) * window(30, 150))
variants = dict(p1=y, p1_null=y.copy(), advance=advance, duck=duck)
cut = slice(int(T0 * FS) + lat, int(T1 * FS) + lat)
names = list(variants); rng = np.random.default_rng(seed); order = rng.permutation(len(names))
outdir.mkdir(parents=True, exist_ok=True); key = {}; info = {}
band = butter(4, [150, 400], btype='band', fs=FS, output='sos')
for n, j in enumerate(order, 1):
    nm = names[j]; seg = variants[nm][cut]; key[str(n)] = nm
    sf.write(str(outdir / f'logoff_bloom_{n}.wav'), seg.astype(np.float32), FS, subtype='PCM_16')
    l = (variants[nm] - dry)[cut].mean(axis=1)
    info[nm] = dict(peak=round(float(np.abs(seg).max()), 3),
                    layer_db_excerpt=round(float(10 * np.log10(np.mean(sosfiltfilt(band, l) ** 2))), 2))
blob = json.dumps(dict(key=key, seed=seed, info=info, song_commit=T.source_commit(libpath)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob)
print('key sha256', hashlib.sha256(blob).hexdigest())
print(json.dumps({nm: v for nm, v in info.items()}))
