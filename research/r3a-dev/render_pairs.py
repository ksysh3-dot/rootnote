"""LOGOFF pair test, duck vs P1 (offline, non-causal, listening only). Same chain and 'duck' as render_bloom.py
(layer -6 dB from 30 to 150 ms after each input low-band hit). Each file = A (8 s) + 1 s silence + B (8 s), excerpt
40-48 s. Six pairs: duck/p1 twice, p1/duck twice, p1/p1 and duck/duck (the null pairs), in shuffled order. The
listener says per file which half has the shorter tail after the hits, or 'same'. Key SHA-256 printed before listening.
Usage: render_pairs.py <song> <lib> <outdir> <keyfile> <seed>"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import test_engine as T

song, libpath, outdir, keyfile, seed = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4], int(sys.argv[5])
FS = 48000; T0, T1 = 40.0, 48.0
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
    w = np.zeros(len(y)); r = .5 - .5 * np.cos(np.linspace(0, np.pi, ms(edge)))
    for o in on:
        s, t = o + lat + ms(a), o + lat + ms(b)
        if s < 0 or t + ms(edge) > len(w): continue
        w[s:s + ms(edge)] = np.maximum(w[s:s + ms(edge)], r); w[s + ms(edge):t] = 1
        w[t:t + ms(edge)] = np.maximum(w[t:t + ms(edge)], r[::-1])
    return w[:, None]
V = dict(p1=y, duck=dry + lay * (1 - (1 - 10 ** (-6 / 20)) * window(30, 150)))
cut = slice(int(T0 * FS) + lat, int(T1 * FS) + lat)
fade = np.minimum(1, np.minimum(np.arange(cut.stop - cut.start), np.arange(cut.stop - cut.start)[::-1]) / ms(10))[:, None]
pairs = [('duck', 'p1'), ('duck', 'p1'), ('p1', 'duck'), ('p1', 'duck'), ('p1', 'p1'), ('duck', 'duck')]
order = np.random.default_rng(seed).permutation(len(pairs))
outdir.mkdir(parents=True, exist_ok=True); key = {}
for n, j in enumerate(order, 1):
    a, b = pairs[j]; key[str(n)] = dict(A=a, B=b)
    z = np.r_[V[a][cut] * fade, np.zeros((FS, 2)), V[b][cut] * fade]
    sf.write(str(outdir / f'logoff_pair_{n}.wav'), z.astype(np.float32), FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, excerpt=[T0, T1], lib_commit=T.source_commit(libpath)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob)
print('key sha256', hashlib.sha256(blob).hexdigest())
