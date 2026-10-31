import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12common import *
np.set_printoptions(linewidth=200, precision=4, suppress=True)
# 1. reproduce cached v15 trace?
a = np.load(TMP / 'app_v15_trace.npz'); b = np.load(B1 / 'cache/app_trace_v15.npz')
print('trace shapes', a['hop'].shape, b['hop'].shape, 'identical f_osc:', np.array_equal(a['f_osc'], b['f_osc']), 'A:', np.array_equal(a['A'], b['A']))
# 2. P1 harmonic rows
h = np.load(TMP / 'app_P1_harm.npz')['rows']
print('P1 harm rows', h.shape)
r = h[len(h) // 2]
print('header', r[:28])
for t in range(12):
    tk = r[28 + 56 * t: 28 + 56 * (t + 1)]
    if tk[0] != 0 or tk[1] != 0:
        print('track', t, tk[:14]); print('   harm', tk[14:].reshape(7, 6))
# 3. lay latency / timing check
print('layer lens', len(np.load(TMP / 'app_P1_layer.npy')), len(np.load(TMP / 'app_v15_layer.npy')))
# core index from limbs
L = h[:, 3:7].astype(np.int64)
ci = L[:, 0] + (L[:, 1] << 16) + (L[:, 2] << 32) + (L[:, 3] << 48)
print('core idx first/last', ci[:3], ci[-3:], 'row0 first', h[:3, 0], h[-3:, 0])
tr = a
print('v15 hop first', tr['hop'][:3, 0], 'step', np.diff(tr['hop'][:5, 0]))
# filter response of OUT_SOS at 3k vs 48k
for fs in (3000, 48000):
    w, H = sosfreqz(OUT_SOS, worN=[50, 75, 100, 150, 200, 300, 600], fs=fs)
    print('OUT_SOS fs', fs, np.round(20 * np.log10(np.abs(H) + 1e-12), 1))
