"""R4-L v2 blind (local only, phone speaker with Rootnote off): does the slow per-track return remove the late swell
(bare bass), the crackle (synthetic bass with kick, and without the kick but with the noise bed), and does the gain
survive on a song (Track00060 39-47 s)? v2 = R4c + R4-L 6 dB + StageReentrySlow (tau 250 ms). App chain at the
default level, each file = A (8 s) + 1 s silence + B (8 s). Pairs, each in a random order, files shuffled: bare
p1/v2, bare v2/v2 (null), synth p1/v2, nokick p1/v2, T60 p1/v2. Question per file: noise (crackle, fizz), timing
mismatch, and which half has the stronger bass. Key JSON SHA-256 printed; listening spots from |v2 - p1| (150-600 Hz)
per source, key-free. Usage: render_r4l2_pairs.py <lib> <synth wav> <nokick wav> <T60 mix> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, resample_poly
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, synth, nokick, t60, outdir, keyfile, seed = sys.argv[1:8]; seed = int(seed); outdir = Path(outdir)
FS = 48000; lib = RP.api(libp)
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]; lib.pvb_set_r4_reentry.argtypes = [C.c_void_p, C.c_double]
V2 = 16777216 | 67108864 | 134217728
def load(p):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    if fs != FS: x = resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0)
    return np.clip(x, -1, 1).astype(np.float32)
def render(x, v2=False):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
    if v2:
        assert lib.pvb_set_r4_level(e.h, 6.) == 1 and lib.pvb_set_r4_reentry(e.h, 250.) == 1
        cap = StageCapture(lib, e.h, V2, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[lat:].astype(np.float32)
t = np.arange(9 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
src = {'bare': (np.ascontiguousarray(np.stack([bass, bass], 1), np.float32), 0),
       'synth': (load(synth)[:8 * FS + FS // 2], 0), 'nokick': (load(nokick)[:8 * FS + FS // 2], 0),
       'T60': (load(t60)[36 * FS:48 * FS], 3)}
S = {}
for nm, (x, c0) in src.items():
    cut = lambda y: y[c0 * FS:c0 * FS + 8 * FS]
    S[nm] = {'p1': cut(render(x)), 'v2': cut(render(x, True))}
    d = sosfiltfilt(butter(4, [150, 600], btype='band', fs=FS, output='sos'), (S[nm]['v2'] - S[nm]['p1']).mean(axis=1))
    B = FS // 4; en = np.array([np.sum(d[i:i + B] ** 2) for i in range(0, len(d) - B + 1, B)]); en[:2] = en[-2:] = 0
    print(f'spots {nm}:', ', '.join(f'{i * .25:.2f}-{i * .25 + .25:.2f} s' for i in sorted(np.argsort(en)[::-1][:3])))
pairs = [('bare', 'p1', 'v2'), ('bare', 'v2', 'v2'), ('synth', 'p1', 'v2'), ('nokick', 'p1', 'v2'), ('T60', 'p1', 'v2')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    s, a, b = pairs[j]
    if rng.random() < .5: a, b = b, a
    key[f'r4l2_{n}'] = dict(src=s, A=a, B=b)
    sf.write(str(outdir / f'r4l2_{n}_{s}.wav'), np.r_[S[s][a] * fade, np.zeros((FS, 2), np.float32), S[s][b] * fade], FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest())
print('files', sorted(p.name for p in outdir.glob('r4l2_*.wav')))
