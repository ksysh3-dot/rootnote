import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import guards as G, numpy as np
th = G.th_grid()[0]
for key in ('steady8', 'vib_30_5'):
    sig, S = G.get_S(key)
    ev, pc = G.DT.detect_song(S, th)
    flat = [e for l in ev for e in l if e['kind'] == 'Ep']
    print(key, 'via', {v: sum(1 for e in flat if e['via'] == v) for v in (1, 2)}, 'new', sum(1 for e in flat if e.get('new')))
    for e in flat[:6]:
        r = [x for x in S.runs if x['vid'] == e['vid'] and x['T'][0] <= e['t'] <= x['T'][-1]][0]
        i = e['ib']
        print(' ', e['via'], round(e['t'], 3), 'f', round(e['f'], 1), 'fold', round(e['fold'], 1), 'f around', np.round(r['f'][max(i - 4, 0):i + 5], 1), 'rho', np.round(r['rho'][max(i - 4, 0):i + 5], 1))
    nr = len(S.runs); print(' runs', nr, 'run lens', sorted([len(x['hs']) for x in S.runs])[-5:])
