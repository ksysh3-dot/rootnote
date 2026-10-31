"""Isolate the heap corruption seen in the V0 cross-check: run each (lib, algo, signal) in its own process with MALLOC_CHECK_=3."""
import os, subprocess, sys, json
CHILD = r'''
import sys
sys.path.insert(0, "."); sys.path.insert(0, "study")
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
import research_core_xcheck as X
import test_engine as T
which, algo, sig, block = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
lib = X.open_lib(X.CAND if which == "cand" else X.REF)
if sig == "bkp":
    b, _, _ = X.bass_sig(3.0); x = b + .2 * X.kick_sig(3.0) + X.pink_gf(3.0)
    x = np.stack([x, x], 1).astype(np.float32)
elif sig == "t60":
    t, _ = sf.read(str(X.SLAKH / "Track00060" / "mix.flac"), start=int(30 * 44100), frames=5 * 44100, always_2d=True)
    x = np.clip(resample_poly(t[:, :2], 160, 147, axis=0), -1, 1).astype(np.float32)
elif sig == "pink":
    p = X.pink_gf(3.0); x = np.stack([p, p], 1).astype(np.float32)
e = T.Engine(lib, 48000, vb_on=1, vb_algo=algo, ramp_ms=0)
y = e.process(np.ascontiguousarray(x, np.float32).copy(), block=block)
e.close()
print("ok", float(np.abs(y).max()))
'''
env = dict(os.environ, MALLOC_CHECK_='3', PYTHONPATH='.:study')
res = {}
for which in ('ref', 'cand'):
    for sig in ('bkp', 't60'):
        for algo in range(0, 15):
            r = subprocess.run([sys.executable, '-c', CHILD, which, str(algo), sig, '256'], env=env, capture_output=True, text=True)
            tag = f'{which}/{sig}/algo{algo}'
            res[tag] = (r.returncode, (r.stdout.strip() or r.stderr.strip())[-100:])
            if r.returncode != 0:
                print('CRASH', tag, r.returncode, r.stderr.strip()[-200:], flush=True)
print('done; crashes:', [k for k, v in res.items() if v[0] != 0])
print('ok runs:', sum(1 for v in res.values() if v[0] == 0), 'of', len(res))
