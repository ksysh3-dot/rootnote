"""SUPPLEMENTARY (post hoc): same measure on the 20-150 Hz layer band (input 40-150 Hz)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
def mmss(t): return f'{int(t // 60)}:{t % 60:04.1f}'
res = {}; lines = ['song | n_elig | P1 med/p95 | v1.5 med/p95 | v1.6a med/p95 | worst v1.5 window (D, time)  [20-150 Hz layer band, input 40-150 Hz]']
for i, p in enumerate(MUSIC):
    nm = os.path.basename(p)[:-5]
    envs = {e: np.load(C / f's{i:02d}_{e}_lo.npz')['env'] for e in ENG}
    inp = np.load(C / f's{i:02d}_input_lo.npz')['env']
    # eligibility from the registered 150-600 v1.5 level, same as the registered table
    e15 = np.load(C / f's{i:02d}_v15.npz')['env']
    n = min(len(inp), len(e15), *[len(v) for v in envs.values()])
    S = {e: mod_series(envs[e][:n]) for e in ENG}
    t, _, _, lev = mod_series(e15[:n])
    Mi = mod_series(inp[:n])[1]
    elig = (lev > -70) & (t >= 2.0)
    ex = {e: S[e][1] - Mi for e in ENG}
    D = S['v15'][1] - S['P1'][1]
    stat = {e: (float(np.median(ex[e][elig])), float(np.percentile(ex[e][elig], 95))) for e in ENG}
    Dm = np.where(elig, D, -1e9); kw = int(np.argmax(Dm))
    res[nm] = dict(stat=stat, worst=dict(t=float(t[kw]), D=float(D[kw])), n_D_gt1=int((D[elig] > 1).sum()), n_D_gt2=int((D[elig] > 2).sum()), n_elig=int(elig.sum()), Dmed=float(np.median(D[elig])))
    lines.append(f"{i:02d} {nm[:34]:34s} | {elig.sum():3d} | {stat['P1'][0]:.2f}/{stat['P1'][1]:.2f} | {stat['v15'][0]:.2f}/{stat['v15'][1]:.2f} | {stat['v16a'][0]:.2f}/{stat['v16a'][1]:.2f} | D={D[kw]:+.2f} @ {mmss(t[kw])} | n(D>1)={res[nm]['n_D_gt1']} n(D>2)={res[nm]['n_D_gt2']}")
    if 'Apparition' in nm:
        order = np.argsort(-Dm, kind='stable'); pick = []
        for k in order:
            if Dm[k] < -1e8: break
            if all(abs(t[k] - t[j]) >= 8.0 for j in pick): pick.append(k)
            if len(pick) == 3: break
        res['_apparition_top_lo'] = [dict(t0=float(t[k]), D=float(D[k]), M={e: float(S[e][1][k]) for e in ENG}, Min=float(Mi[k]), pk={e: float(S[e][2][k]) for e in ENG}) for k in pick]
json.dump(res, open(B1 / 'rank_lo.json', 'w'), indent=1)
open(B1 / 'table_lo.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
for k in res['_apparition_top_lo']: print(k)
