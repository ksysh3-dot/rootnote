"""R4-L noise follow-up (local only, phone speaker with Rootnote off): does a lower register level, or the onset
protection, keep LOGOFF and the synthetic 100 Hz bass clean (both crackled at 9 dB)? App chain at the default level,
each file = A (8 s) + 1 s silence + B (8 s), the same excerpts as r4l_*. Pairs, each in a random order, files shuffled:
LOGOFF p1/l6, LOGOFF p1/l6p, synth p1/l6, synth p1/l6p, synth l6/l6 (null); l6p = R4-L 6 dB with the onset protection
(8 hops, floor 0, 30 ms). Question: noise (crackle, fizz) in either half, and which has the stronger bass.
Key JSON SHA-256 printed. Usage: render_r4l6_pairs.py <lib> <logoff> <synth bass100> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, logoff, synth, outdir, keyfile, seed = sys.argv[1:7]; seed = int(seed); outdir = Path(outdir)
FS = 48000; lib = RP.api(libp)
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]; lib.pvb_set_r4_research.argtypes = [C.c_void_p, C.c_int, C.c_double, C.c_double]
def load(p):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    return np.clip(resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x, -1, 1).astype(np.float32)
def render(x, level=None, protect=False):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6); flags = 0
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; flags = 16777216 | 67108864
    if protect:
        assert lib.pvb_set_r4_research(e.h, 8, 0., 30.) == 1; flags |= 33554432
    cap = StageCapture(lib, e.h, flags, int(len(x) / FS * 3000) + 16) if flags else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[lat:].astype(np.float32)
xl = load(logoff)[37 * FS:49 * FS]; xs = load(synth)[:8 * FS + FS // 2]
cl = lambda y: y[3 * FS:11 * FS]; cs = lambda y: y[:8 * FS]
S = {'LOGOFF': {'p1': cl(render(xl)), 'l6': cl(render(xl, 6.)), 'l6p': cl(render(xl, 6., True))},
     'synth': {'p1': cs(render(xs)), 'l6': cs(render(xs, 6.)), 'l6p': cs(render(xs, 6., True))}}
pairs = [('LOGOFF', 'p1', 'l6'), ('LOGOFF', 'p1', 'l6p'), ('synth', 'p1', 'l6'), ('synth', 'p1', 'l6p'), ('synth', 'l6', 'l6')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    src, a, b = pairs[j]
    if rng.random() < .5: a, b = b, a
    key[f'r4l6_{n}'] = dict(src=src, A=a, B=b)
    sf.write(str(outdir / f'r4l6_{n}_{src}.wav'), np.r_[S[src][a] * fade, np.zeros((FS, 2), np.float32), S[src][b] * fade], FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest())
print('files', sorted(p.name for p in outdir.glob('r4l6_*.wav')))
