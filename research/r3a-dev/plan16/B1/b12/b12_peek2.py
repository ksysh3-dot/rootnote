import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_data import *
np.set_printoptions(linewidth=220, precision=5, suppress=False)
for eng in ('P1', 'v15'):
    d = load('app', eng); h = d['h']; ci = d['hci']
    ts = CA.hop_time(ci)[1]
    sel = np.where((ts >= 52.0) & (ts < 54.0))[0]
    print(eng, 'rows in window', len(sel), 'of', len(h))
    for j in sel[::60]:
        print(f'  t={ts[j]:.3f} ci={ci[j]}', h[j, 11:28])
    print('  col17 stats in window: min/med/max', h[sel, 17].min(), np.median(h[sel, 17]), h[sel, 17].max(), ' col18', np.median(h[sel, 18]), ' col19', np.median(np.abs(h[sel, 19])))
