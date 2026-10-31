import numpy as np, common16 as C
for key in ('bare100',):
    z = np.load(C.CACHE / f's_{key}.npz')
    for nm in ('det', 'bh'):
        x = z[nm]
        j = np.arange(len(x)); t = (j - 191) / 3000 + 1359 / 48000
        m = (t > 0.9) & (t < 1.4)
        c = np.cos(2 * np.pi * 100 * t[m]); s = np.sin(2 * np.pi * 100 * t[m])
        B = np.stack([s, c], 1); co, *_ = np.linalg.lstsq(B, x[m], rcond=None)
        A = np.hypot(*co); ph = np.arctan2(co[1], co[0])   # x = A sin(wt + ph)
        print(key, nm, 'amp %.4f phase %.4f rad -> delay %.3f ms (positive = stream lags truth)' % (A, ph, -ph / (2 * np.pi * 100) * 1000))
# also: truth amplitude: scale*1.0 for the fundamental
import proxy16 as PX
print('scale', PX.SCALE)
