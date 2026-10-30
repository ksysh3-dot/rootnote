"""R4-L crackle cause check (local only, phone speaker with Rootnote off): the synthetic 100 Hz bass crackled at 6 dB,
and its kick (90 -> 50 Hz, f0/2) switches the boost off and on inside every note. Same bass without the kick, and with
a kick settling at 60 Hz (same onset energy, no switching: 0 of 25 cycle steps off): is 6 dB clean? No-kick clean
alone would not separate switching from the kick's own energy; kick60 does. App chain at the default level, first
8 s, each file = A (8 s) + 1 s silence + B (8 s). Pairs, each in a random order, files shuffled: nokick p1/l6,
nokick l6/l6 (null), kick p1/l6 (the crackling case again), kick60 p1/l6. Question: noise (crackle, fizz) in either
half, and which has the stronger bass. Key JSON SHA-256 printed; listening spots from |l6 - p1| (150-600 Hz) per
group (with a kick: kick + kick60 together; without), key-free.
Usage: render_r4l6b_pairs.py <lib> <kick wav> <kick60 wav> <nokick wav> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, kick, kick60, nokick, outdir, keyfile, seed = sys.argv[1:8]; seed = int(seed); outdir = Path(outdir)
FS = 48000; lib = RP.api(libp)
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
def load(p):
    x, fs = sf.read(p, always_2d=True); assert fs == FS
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    return np.clip(x, -1, 1).astype(np.float32)[:8 * FS + FS // 2]
def render(x, level=None):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[lat:lat + 8 * FS].astype(np.float32)
S = {}; EN = {}
for nm, p in (('kick', kick), ('kick60', kick60), ('nokick', nokick)):
    x = load(p); S[nm] = {'p1': render(x), 'l6': render(x, 6.)}
    d = sosfiltfilt(butter(4, [150, 600], btype='band', fs=FS, output='sos'), (S[nm]['l6'] - S[nm]['p1']).mean(axis=1))
    B = FS // 4; en = np.array([np.sum(d[i:i + B] ** 2) for i in range(0, len(d) - B + 1, B)]); en[:2] = en[-2:] = 0
    EN[nm] = en / en.max()
for g, en in (('with a kick', EN['kick'] + EN['kick60']), ('without', EN['nokick'])):
    top = sorted(np.argsort(en)[::-1][:3]); print(f'spots {g}:', ', '.join(f'{i * .25:.2f}-{i * .25 + .25:.2f} s' for i in top))
pairs = [('nokick', 'p1', 'l6'), ('nokick', 'l6', 'l6'), ('kick', 'p1', 'l6'), ('kick60', 'p1', 'l6')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    src, a, b = pairs[j]
    if rng.random() < .5: a, b = b, a
    key[f'r4l6b_{n}'] = dict(src=src, A=a, B=b)
    sf.write(str(outdir / f'r4l6b_{n}.wav'), np.r_[S[src][a] * fade, np.zeros((FS, 2), np.float32), S[src][b] * fade], FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest())
print('files', sorted(p.name for p in outdir.glob('r4l6b_*.wav')))
