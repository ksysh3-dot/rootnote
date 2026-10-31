"""layer extraction check: output == vb-off output + layer ?  (one song)"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
from pcommon import *
key = sys.argv[1]
x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
e = T.Engine(lib, FS, vb_on=0, vb_algo=6, ramp_ms=0)
y0 = np.ascontiguousarray(x, np.float32).copy()
for i in range(0, len(y0), BLOCK):
    b = y0[i:i + BLOCK]; lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
lat0 = int(lib.pvb_latency(e.h)); e.close()
y0 = y0[lat0:lat0 + 30 * FS].astype(np.float64)
print('vb off lat', lat0, 'rms', np.sqrt((y0 ** 2).mean()))
for algo in (15, 6):
    r = render_capture(x, algo)
    y, L = r['y'], r['layer']
    d = y - L - y0
    sl = slice(int(0.5 * FS), None)
    print('algo', algo, 'lat', r['lat'], 'rms y', np.sqrt((y ** 2).mean()), 'rms layer', np.sqrt((L ** 2).mean()),
          '| y-layer-y_vboff: max abs', np.abs(d[sl]).max(), 'rms', np.sqrt((d[sl] ** 2).mean()), 'rel to rms(y)', np.sqrt((d[sl] ** 2).mean()) / np.sqrt((y[sl] ** 2).mean()))
    # alternative layer definition: vb on - vb off
    alt = y - y0
    print('   (vb on - vb off) vs captured layer: rel diff rms', np.sqrt(((alt - L)[sl] ** 2).mean()) / np.sqrt((L[sl] ** 2).mean()),
          ' corr', float(np.corrcoef(alt[sl, 0], L[sl, 0])[0, 1]))
