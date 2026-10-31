import numpy as np, common16 as C, research_core_xcheck as X
tr = C.get_core('Track00001'); tc1, ts = C.get_p1('Track00001')
d, hop, tc = X.hops_of(tr)
raw = tr.reshape(-1, 8, 22)
h = 2000
print('core hop', h, 'tc', tc[h], 'P1 nearest', tc1[np.argmin(abs(tc1 - tc[h]))], 'dt min', np.min(np.abs(tc1[:, None][:50] - tc[h])))
print('core track ids', raw[h, :, X.F_TRACK], 'state', raw[h, :, X.F_STATE], 'ftr', raw[h, :, X.F_FTR], 'coast', raw[h, :, X.F_COAST])
i = np.argmin(abs(tc1 - tc[h]))
print('p1 ids', ts[i, :, 0], ts[i, :, 13], 'f', ts[i, :, 2], 'state', ts[i, :, 1])
dt = np.array([np.min(np.abs(tc1 - t)) for t in tc[:3000:7]])
print('grid offset max', dt.max(), 'median', np.median(dt))
