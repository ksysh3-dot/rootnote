import os, subprocess, sys
CH = {
 'read_only': r'''
import numpy as np, soundfile as sf
t, _ = sf.read("/home/ksysh/datasets/slakh2100/train/Track00060/mix.flac", start=int(30 * 44100), frames=5 * 44100, always_2d=True)
print("read", t.shape, t.dtype)
''',
 'read_resample': r'''
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
t, _ = sf.read("/home/ksysh/datasets/slakh2100/train/Track00060/mix.flac", start=int(30 * 44100), frames=5 * 44100, always_2d=True)
x = np.clip(resample_poly(t[:, :2], 160, 147, axis=0), -1, 1).astype(np.float32)
print("rs", x.shape, x.flags['C_CONTIGUOUS'])
''',
 'engine_noise_stereo': r'''
import sys; sys.path.insert(0, "."); sys.path.insert(0, "study")
import numpy as np, test_engine as T, research_core_xcheck as X
rng = np.random.default_rng(1); x = (0.1 * rng.standard_normal((240000, 2))).astype(np.float32)
lib = X.open_lib(X.REF); e = T.Engine(lib, 48000, vb_on=1, vb_algo=6, ramp_ms=0); y = e.process(x.copy(), block=256); e.close(); print("engine ok")
''',
 'engine_t60_read_sf_noresample': r'''
import sys; sys.path.insert(0, "."); sys.path.insert(0, "study")
import numpy as np, soundfile as sf, test_engine as T, research_core_xcheck as X
t, _ = sf.read("/home/ksysh/datasets/slakh2100/train/Track00060/mix.flac", start=int(30 * 44100), frames=5 * 44100, always_2d=True)
x = t[:, :2].astype(np.float32)
lib = X.open_lib(X.REF); e = T.Engine(lib, 44100, vb_on=1, vb_algo=6, ramp_ms=0); y = e.process(x.copy(), block=256); e.close(); print("engine@44.1k ok")
''',
 'engine_t60_full_read': r'''
import sys; sys.path.insert(0, "."); sys.path.insert(0, "study")
import numpy as np, soundfile as sf, test_engine as T, research_core_xcheck as X
from scipy.signal import resample_poly
t, _ = sf.read("/home/ksysh/datasets/slakh2100/train/Track00060/mix.flac", always_2d=True)
t = t[30 * 44100:35 * 44100]
x = np.clip(resample_poly(t[:, :2], 160, 147, axis=0), -1, 1).astype(np.float32)
lib = X.open_lib(X.REF); e = T.Engine(lib, 48000, vb_on=1, vb_algo=6, ramp_ms=0); y = e.process(x.copy(), block=256); e.close(); print("engine full-read ok")
''',
}
env = dict(os.environ, MALLOC_CHECK_='3', PYTHONPATH='.:study')
for k, code in CH.items():
    r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    print(k, '->', r.returncode, (r.stdout.strip() or r.stderr.strip())[-160:], flush=True)
