import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
from scipy.signal import butter, sosfiltfilt
z = np.load(B1 / 'app_series.npz')
t, D, el = z['t'], z['D'], z['elig']
print('windows', len(t), 'elig', el.sum(), 'D>0', (D[el] > 0).sum(), 'D>1', (D[el] > 1).sum(), 'D>2', (D[el] > 2).sum(), 'D median', np.median(D[el]))
for e in ('P1', 'v15', 'v16a'):
    print(e, 'M med', np.median(z['M_' + e][el]), 'lev med', np.median(z['lev_' + e][el]))
# top 12 D windows
o = np.argsort(-np.where(el, D, -1e9))[:12]
for k in o:
    print(f'{int(t[k]//60)}:{t[k]%60:05.2f} D={D[k]:+.2f} M15={z["M_v15"][k]:.2f} MP1={z["M_P1"][k]:.2f} Min={z["Mi"][k]:.2f} lev15={z["lev_v15"][k]:.1f} levP1={z["lev_P1"][k]:.1f}')
# level / floor fraction of P1 and v15 envelope
for e in ('P1', 'v15'):
    env = np.load(C / f's09_{e}.npz')['env']
    print(e, 'frac of 5ms boxes at floor', (env <= -89.9).mean(), 'frac < -70', (env < -70).mean())
