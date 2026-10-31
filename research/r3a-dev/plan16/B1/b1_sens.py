"""SENSITIVITY (post hoc, report only): floor of the dB envelope raised to -60 dB; counts of windows with D>0 (registered band)."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
print('song | floor -60: median excess P1 / v1.5 / v1.6a | n windows D>0 (floor -90) / D>1 | eligible')
for i, p in enumerate(MUSIC):
    envs = {e: np.load(C / f's{i:02d}_{e}.npz')['env'] for e in ENG}
    inp = np.load(C / f's{i:02d}_input.npz')['env']
    n = min(len(inp), *[len(v) for v in envs.values()])
    t, _, _, lev = mod_series(envs['v15'][:n]); el = (lev > -70) & (t >= 2)
    Mi = mod_series(np.maximum(inp[:n], -60))[1]
    S60 = {e: mod_series(np.maximum(envs[e][:n], -60))[1] for e in ENG}
    S90 = {e: mod_series(envs[e][:n])[1] for e in ('P1', 'v15')}
    D90 = (S90['v15'] - S90['P1'])[el]
    print(f"{i:02d} " + ' / '.join(f'{np.median((S60[e] - Mi)[el]):.2f}' for e in ENG) + f" | {int((D90 > 0).sum())} / {int((D90 > 1).sum())} | {el.sum()}")
