"""Ranking + 14-song table (writes rank.json, table.txt)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *

def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'

res = {}
lines = ['song | n_elig | P1 med/p95 | v1.5 med/p95 | v1.6a med/p95 | input M med | worst v1.5 window (D, time)']
for i, p in enumerate(MUSIC):
    nm = os.path.basename(p)[:-5]
    envs = {e: np.load(C / f's{i:02d}_{e}.npz')['env'] for e in ENG}
    inp = np.load(C / f's{i:02d}_input.npz')['env']
    n = min(len(inp), *[len(v) for v in envs.values()])
    S = {}
    for e in ENG:
        t, M, pk, lev = mod_series(envs[e][:n]); S[e] = (M, pk, lev)
    _, Mi, _, _ = mod_series(inp[:n])
    elig = (S['v15'][2] > -70) & (t >= 2.0)
    ex = {e: S[e][0] - Mi for e in ENG}
    D = S['v15'][0] - S['P1'][0]
    stat = {}
    for e in ENG:
        v = ex[e][elig]
        stat[e] = (float(np.median(v)), float(np.percentile(v, 95))) if v.size else (float('nan'),) * 2
    Dm = np.where(elig, D, -1e9)
    kw = int(np.argmax(Dm))
    res[nm] = dict(stat=stat, n_elig=int(elig.sum()), n=len(t), worst=dict(t=float(t[kw]), D=float(D[kw])), Dmed=float(np.median(D[elig])) if elig.any() else None,
                   inp_med=float(np.median(Mi[elig])) if elig.any() else None)
    lines.append(f"{i:02d} {nm[:34]:34s} | {elig.sum():3d}/{len(t)} | {stat['P1'][0]:.2f}/{stat['P1'][1]:.2f} | {stat['v15'][0]:.2f}/{stat['v15'][1]:.2f} | {stat['v16a'][0]:.2f}/{stat['v16a'][1]:.2f} | {np.median(Mi[elig]):.2f} | D={D[kw]:+.2f} @ {mmss(t[kw])}")
    if 'Apparition' in nm:
        # top 3 with >= 8 s separation
        order = np.argsort(-Dm, kind='stable')
        pick = []
        for k in order:
            if Dm[k] < -1e8: break
            if all(abs(t[k] - t[j]) >= 8.0 for j in pick): pick.append(k)
            if len(pick) == 3: break
        top = []
        for k in pick:
            top.append(dict(t0=float(t[k]), t1=float(t[k] + 2), D=float(D[k]), M=dict((e, float(S[e][0][k])) for e in ENG), Min=float(Mi[k]),
                            pk=dict((e, float(S[e][1][k])) for e in ENG), lev=dict((e, float(S[e][2][k])) for e in ENG)))
        res['_apparition_top'] = top
        np.savez(B1 / 'app_series.npz', t=t, D=D, elig=elig, Mi=Mi, **{f'M_{e}': S[e][0] for e in ENG}, **{f'pk_{e}': S[e][1] for e in ENG}, **{f'lev_{e}': S[e][2] for e in ENG})
json.dump(res, open(B1 / 'rank.json', 'w'), indent=1)
open(B1 / 'table.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
for k in res.get('_apparition_top', []): print(k)
