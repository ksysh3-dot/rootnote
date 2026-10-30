"""R4 blind pair set (local only, listening on the phone speaker with Rootnote off). App chain at defaults; R4 via host
stage flags (StageCapture attached) and pvb_set_r4_research. Each file = A (8 s) + 1 s silence + B (8 s).
Group 'bass' (Slakh train Track00040 mix, 40-48 s, bass median 110 Hz): p1/r4c, r4c/p1, r4c/r4c (null), p1/r4p8, in a
shuffled order; question: which half has the stronger bass, and is there noise in either.
Group 'noise' (LOGOFF 40-48 s, layer +6 dB): p1/r4c, r4c/p1, p1/p1 (null), shuffled; question: which half has more
fizz / noise on hits. Key JSON SHA-256 printed before listening.
Usage: render_r4_pairs.py <lib> <slakh mix.flac> <logoff.mp3> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, slakh, logoff, outdir, keyfile, seed = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]), sys.argv[5], int(sys.argv[6])
FS = 48000; lib = RP.api(libp)
lib.pvb_set_r4_research.argtypes = [C.c_void_p, C.c_int, C.c_double, C.c_double]
def load(p, t0):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    x = resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x
    return np.clip(x[int((t0 - 3) * FS):int((t0 + 9) * FS)], -1, 1).astype(np.float32)
def render(x, stage=0, r4=None, level=0.):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, vb_level_db=level)
    if r4: assert lib.pvb_set_r4_research(e.h, *r4) == 1
    cap = StageCapture(lib, e.h, stage, int(len(x) / FS * 3000) + 16) if stage else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[3 * FS + lat:3 * FS + lat + 8 * FS].astype(np.float32)
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
xb, xl = load(slakh, 40.), load(logoff, 40.)
B = dict(p1=render(xb), r4c=render(xb, 16777216), r4p8=render(xb, 50331648, (8, 0., 30.)))
d0 = np.zeros(lib.pvb_param_count(), np.float32); lib.pvb_default_params(d0.ctypes.data_as(T.FP)); lv = float(d0[T.P['VB_LEVEL_DB']]) + 6
L = dict(p1=render(xl, level=lv), r4c=render(xl, 16777216, level=lv))
groups = [('bass', B, [('p1', 'r4c'), ('r4c', 'p1'), ('r4c', 'r4c'), ('p1', 'r4p8')]),
          ('noise', L, [('p1', 'r4c'), ('r4c', 'p1'), ('p1', 'p1')])]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
for g, V, pairs in groups:
    for n, j in enumerate(rng.permutation(len(pairs)), 1):
        a, b = pairs[j]; key[f'{g}_{n}'] = dict(A=a, B=b)
        z = np.r_[V[a] * fade, np.zeros((FS, 2), np.float32), V[b] * fade]
        sf.write(str(outdir / f'r4_{g}_{n}.wav'), z, FS, subtype='PCM_16')
info = {f'{g}_{k}': float(np.abs(v).max()) for g, V, _ in groups for k, v in V.items()}
blob = json.dumps(dict(key=key, seed=seed, peaks=info, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest()); print('peaks', info)
