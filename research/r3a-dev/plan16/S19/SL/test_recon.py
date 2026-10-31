"""pipeline check: v1.6-c layer of one song vs the trace reconstruction (alignment, scale). usage: test_recon.py SONG"""
import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/SL')
import numpy as np
import sl_lib as Z

song = sys.argv[1]
t = time.time()
xin = Z.read_any(song)
x, tr = Z.HM.render_song(xin, 'v16c')
print('render', round(time.time() - t), len(x) / Z.FS, flush=True)
d = Z.trace_of(tr)
print('theta range', d['theta_hat'].min(), d['theta_hat'].max(), 'max |dtheta| per hop', np.abs(np.diff(d['theta_hat'], axis=0)).max(), flush=True)
t = time.time()
y = Z.rebuild(d, d['a_2'].astype(np.float64), d['a_3'].astype(np.float64))
print('rebuild', round(time.time() - t), flush=True)
# alignment: band 20-150 of real layer vs recon over a stretch
from scipy.signal import butter, sosfiltfilt, resample_poly
t0 = {'lastcarn': 63.5, 'beyond': 193.0, 'v09': 201.0, 'v06': 96.0}[song]
i0 = int(t0 * Z.FS); n = int(2 * Z.FS)
bp = butter(4, [150, 600], 'bandpass', fs=Z.FS, output='sos'); bp3 = butter(4, [150, 600], 'bandpass', fs=Z.CFS, output='sos')
xr = sosfiltfilt(bp, x)[i0 - 4800:i0 + n + 4800]
xr3 = resample_poly(xr, 1, 16)           # 48k -> 3k
best = None
for lag in range(-60, 61):
    n0 = Z.core_idx(t0) + lag
    yy = sosfiltfilt(bp3, y)[n0 - 300:n0 + 6000 + 300]
    m = min(len(yy), len(xr3))
    c = np.corrcoef(yy[:m], xr3[:m])[0, 1]
    if best is None or c > best[0]:
        best = (c, lag)
print('best corr / lag (core samples, 0 = by_attr alignment):', best)
# metrics real vs recon
xm = xin.astype(np.float64).mean(1)[:len(x)]
r = Z.win_metrics_real(x, xm, [t0])[0]
q = Z.win_metrics_recon(y, [t0])[0]
for k in ('m1', 'm4', 'b260'):
    print(k, 'real', Z.db(r[k]), 'recon', Z.db(q[k]), 'diff', Z.db(q[k]) - Z.db(r[k]))
print('Ml real', r['Ml'], 'recon', q['Ml'], 'Mi', r['Mi'])
sus = Z.sustain_flags(d)
print('sustain frac of ON hops', sus.sum() / max((d['state'] == 2).sum(), 1))
