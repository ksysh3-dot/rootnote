"""R4 level blind set (local only, phone speaker with Rootnote off): how much layer a 110 Hz bass needs to sound stronger,
and whether noise appears then. Slakh train Track00040 40-48 s (the same excerpt as r4_bass_*), app chain, each file = A
(8 s) + 1 s silence + B (8 s). Pairs vs P1 at the default level: p1 / r4c+6, r4c+12 / p1, p1 / p1+12, r4c+12 / r4c+12
(null), shuffled. Question: which half has the stronger bass, and is there noise in either. Key JSON SHA-256 printed.
Usage: render_level_pairs.py <lib> <slakh mix.flac> <outdir> <keyfile> <seed>"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, slakh, outdir, keyfile, seed = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4], int(sys.argv[5])
FS = 48000; lib = RP.api(libp)
def load(p, t0):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    x = resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x
    return np.clip(x[int((t0 - 3) * FS):int((t0 + 9) * FS)], -1, 1).astype(np.float32)
def render(x, stage=0, level=0.):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, vb_level_db=level)
    cap = StageCapture(lib, e.h, stage, int(len(x) / FS * 3000) + 16) if stage else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[3 * FS + lat:3 * FS + lat + 8 * FS].astype(np.float32)
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
xb = load(slakh, 40.)
V = {'p1': render(xb), 'r4c+6': render(xb, 16777216, 6.), 'r4c+12': render(xb, 16777216, 12.), 'p1+12': render(xb, 0, 12.)}
pairs = [('p1', 'r4c+6'), ('r4c+12', 'p1'), ('p1', 'p1+12'), ('r4c+12', 'r4c+12')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    a, b = pairs[j]; key[f'level_{n}'] = dict(A=a, B=b)
    sf.write(str(outdir / f'r4_level_{n}.wav'), np.r_[V[a] * fade, np.zeros((FS, 2), np.float32), V[b] * fade], FS, subtype='PCM_16')
info = {k: float(np.abs(v).max()) for k, v in V.items()}
blob = json.dumps(dict(key=key, seed=seed, peaks=info, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest()); print('peaks', {k: round(v, 3) for k, v in info.items()})
