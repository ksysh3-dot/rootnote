"""time series of top voices + layer env in a window. usage: t0 t1 [step_hops]"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
import api084 as CA
t0 = float(sys.argv[1]); t1 = float(sys.argv[2]); step = int(sys.argv[3]) if len(sys.argv) > 3 else 6
eng = sys.argv[4] if len(sys.argv) > 4 else 'v15'
tr = {k: v for k, v in np.load(C / f'app_trace_{eng}.npz').items()}
tc = CA.hop_time(tr['hop'][:, 0])[0]
idx = np.where((tc >= t0) & (tc < t1))[0]
A = tr['A'][idx]; st = tr['state'][idx]; vid = tr['voice'][idx]; ft = tr['f_track'][idx]; fo = tr['f_osc'][idx]; co = tr['coasting'][idx]
sound = ((st == 2) | (st == 3)) & (A > 1e-5)
e = {}
for v in np.unique(vid[sound]): e[v] = (np.where((vid == v) & sound, A, 0) ** 2).sum()
top = sorted(e, key=lambda v: -e[v])[:3]
env = np.load(C / f's09_{eng}.npz')['env']; envP = np.load(C / 's09_P1.npz')['env']; envI = np.load(C / 's09_input.npz')['env']
print('t(s) | layer dBFS(150-600) v | P1 | input(40-600) || per voice: id state f_track f_osc Adb co')
for k in range(0, len(idx), step):
    tk = tc[idx[k]]; j = int(tk * ER)
    cols = []
    for v in top:
        m = np.where((vid[k] == v))[0]
        if len(m):
            s = m[0]; cols.append(f'{int(v)} s{int(st[k, s])} ft{ft[k, s]:6.1f} fo{fo[k, s]:6.1f} A{20 * np.log10(A[k, s] + 1e-9):6.1f} c{int(co[k, s])}')
        else: cols.append(f'{int(v)} --')
    print(f'{tk - t0:5.3f} | {env[j]:6.1f} | {envP[j]:6.1f} | {envI[j]:6.1f} || ' + ' || '.join(cols))
