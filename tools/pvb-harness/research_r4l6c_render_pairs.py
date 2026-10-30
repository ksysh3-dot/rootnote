"""R4-L crackle: signal or playback? On the synthetic 100 Hz bass the 6 dB file differs from P1 almost only by a clean
+2.5 dB on the partial lines (bass + pink: 76 % of the added layer on the lines, nothing above 1 kHz: -67 dB), yet it
is heard as noise on the phone. Pair set (phone speaker, Rootnote off): the bare bass (no kick, no pink noise) P1/L6
and L6/L6 (null), each in a random order. If the bare-bass 6 dB also crackles, the pink noise is not needed (points to
playback); if it is clean, the noise-tracking interaction matters. Each file = A (8 s) + 1 s silence + B (8 s).
Key JSON SHA-256 printed, listening spots from |l6 - p1| (150-600 Hz), key-free.
Usage: render_r4l6c_pairs.py <lib> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
libp, outdir, keyfile, seed = sys.argv[1:5]; seed = int(seed); outdir = Path(outdir)
FS = 48000; lib = RP.api(libp); lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
t = np.arange(9 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
def render(x, level=None):
    x = np.stack([x, x], 1).astype(np.float32); e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:lat + 8 * FS].astype(np.float32)
S = {'p1': render(bass), 'l6': render(bass, 6.)}
d = sosfiltfilt(butter(4, [150, 600], btype='band', fs=FS, output='sos'), (S['l6'] - S['p1']).mean(axis=1))
B = FS // 4; en = np.array([np.sum(d[i:i + B] ** 2) for i in range(0, len(d) - B + 1, B)]); en[:2] = en[-2:] = 0
print('spots:', ', '.join(f'{i * .25:.2f}-{i * .25 + .25:.2f} s' for i in sorted(np.argsort(en)[::-1][:3])))
pairs = [('p1', 'l6'), ('l6', 'l6')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    a, b = pairs[j]
    if rng.random() < .5: a, b = b, a
    key[f'r4l6c_{n}'] = dict(src='bare bass', A=a, B=b)
    sf.write(str(outdir / f'r4l6c_{n}.wav'), np.r_[S[a] * fade, np.zeros((FS, 2), np.float32), S[b] * fade], FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest())
print('files', sorted(p.name for p in outdir.glob('r4l6c_*.wav')))
