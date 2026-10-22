#!/usr/bin/env python3
"""Feed the exact JVM input PCM to C API and compare every model's actual JNI output."""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_engine as T

lib = T.load_lib(sys.argv[1]); root = Path(sys.argv[2]); count = 0
for fs in (44100, 48000):
    for algorithm in (3, 4, 6, 7, 8, 9, 10):
        x = np.fromfile(root / f'alpha2-{fs}-{algorithm}.in.f32', dtype='<f4').reshape(-1, 2)
        jni = np.fromfile(root / f'alpha2-{fs}-{algorithm}.out.f32', dtype='<f4').reshape(-1, 2)
        e = T.Engine(lib, fs, vb_on=1, vb_algo=algorithm, vb_level_db=9, out_db=-18, ramp_ms=0)
        try:
            y = np.concatenate([e.process(x[i:i + 2048]) for i in range(0, len(x), 2048)])
            assert np.array_equal(jni, y), (fs, algorithm, float(np.max(abs(jni - y))))
        finally: e.close()
        count += 1
print(f'Alpha2 JNI/CAPI: {count}/{count} bit exact for actual input/output PCM')
