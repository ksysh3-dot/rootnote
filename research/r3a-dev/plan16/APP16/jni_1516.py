"""JNI output of models 15 and 16 (written by Alpha2JniTest) vs the C API, bit exact."""
import sys
from pathlib import Path
import numpy as np
H = Path.home() / 'r3-app/tools/pvb-harness'
sys.path.insert(0, str(H))
import test_engine as T

lib = T.load_lib(str(H / 'build_app16/libpvbcapi.so')); root = H / 'build_app16/jvm-alpha2'
for fs in (44100, 48000):
    for algorithm in (15, 16):
        x = np.fromfile(root / f'alpha2-{fs}-{algorithm}.in.f32', dtype='<f4').reshape(-1, 2)
        jni = np.fromfile(root / f'alpha2-{fs}-{algorithm}.out.f32', dtype='<f4').reshape(-1, 2)
        e = T.Engine(lib, fs, vb_on=1, vb_algo=algorithm, vb_level_db=9, out_db=-18, ramp_ms=0)
        y = np.concatenate([e.process(x[i:i + 2048]) for i in range(0, len(x), 2048)]); e.close()
        print(fs, algorithm, 'bit exact' if np.array_equal(jni, y) else 'DIFF', float(np.abs(jni).max()))
