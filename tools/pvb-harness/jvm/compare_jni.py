"""Runs the input written by JniSmokeTest.kt through the C API with the same settings (defaults, 4096-frame
blocks) and requires the JNI output to be bit-identical."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from test_engine import load_lib, Engine

lib = load_lib(sys.argv[1])
jni = np.fromfile(sys.argv[2], dtype='<f4').reshape(-1, 2)
x = np.fromfile(sys.argv[2] + '.in', dtype='<f4').reshape(-1, 2)
e = Engine(lib, 48000)
y = e.process(x, block=4096)
a = e.analyze(240, dt=10.0)
e.close()
same = np.array_equal(y, jni)
print(f"[{'PASS' if same else 'FAIL'}] JNI output == C API output (bit exact), max diff {np.max(np.abs(y - jni)):.3g}")
ana_jni = np.fromfile(sys.argv[2] + '.ana', dtype='<f4')
ana_c = np.concatenate([a['inp'], a['out'], a['diff'], a['eq'], a['info']]).astype(np.float32)
same_ana = ana_jni.shape == ana_c.shape and np.array_equal(ana_jni, ana_c, equal_nan=True)
print(f"[{'PASS' if same_ana else 'FAIL'}] JNI analysis == C API analysis (bit exact, NaN where nothing to show)")
sys.exit(0 if same and same_ana else 1)
