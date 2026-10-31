import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
from pcommon import *
key = sys.argv[1]
x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
print('x shape', x.shape)
for algo in (15, 6):
    r = render_capture(x, algo)
    y, L, F, lat = r['y'], r['layer'], r['full'], r['lat']
    dry = y - L
    xin = (np.stack([x, x], 1) if x.ndim == 1 else x)[:len(y)].astype(np.float64)
    print('algo', algo, 'lat', lat, 'rms y', np.sqrt((y**2).mean()), 'rms layer', np.sqrt((L**2).mean()), 'rms out-layer', np.sqrt((dry**2).mean()))
    print('  max|y-full|', np.abs(y - F).max(), ' max|L-R| of layer', np.abs(L[:, 0] - L[:, 1]).max(), ' peak y', np.abs(y).max(), 'peak x', np.abs(xin).max())
    a = dry[:, 0]; b = xin[:, 0]
    g = (a @ b) / (b @ b); res = a - g * b
    print('  dry ~ g*x : g', g, 'rel residual rms', np.sqrt((res ** 2).mean()) / np.sqrt((a ** 2).mean()))
