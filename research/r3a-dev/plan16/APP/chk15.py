import sys, numpy as np
sys.path.insert(0, '/home/ksysh/r3-app/tools/pvb-harness')
import test_engine as T
lib = T.load_lib('/home/ksysh/r3-app/tools/pvb-harness/build/libpvbcapi.so')
for fs in (44100, 48000):
    n = int(fs * 1.6)
    t = np.arange(n) / fs
    x = (.1 * (1 + .7 * np.sin(2 * np.pi * 20 * t)) * np.cos(2 * np.pi * 80 * t)).astype('<f4')
    x = np.stack([x, x], 1)
    res = {}
    for a in (6, 15):
        e = T.Engine(lib, fs, vb_on=1, vb_algo=a, vb_level_db=9, out_db=-18, ramp_ms=0)
        y = np.concatenate([e.process(x[i:i + 4096]) for i in range(0, len(x), 4096)])
        lat = e.latency()
        print(fs, a, 'finite', bool(np.isfinite(y).all()), 'max', float(abs(y).max()), 'nonzero', bool((abs(y) > 1e-5).any()), 'lat', lat)
        res[a] = y
        e.close()
