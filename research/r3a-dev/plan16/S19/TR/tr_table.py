import json, glob
import numpy as np
R = [json.load(open(f)) for f in sorted(glob.glob('/home/ksysh/r3a-dev/plan16/S19/TR/res/s*.json'))]
assert len(R) == 37
db = lambda a, b: 10 * np.log10(a / b)
def stat(v):
    v = np.array(v); return f'med {np.median(v):+.2f}  p10 {np.percentile(v,10):+.2f}  p90 {np.percentile(v,90):+.2f}  min {v.min():+.2f} max {v.max():+.2f}'
out = []
P = out.append
P('# S19-TR results (core - P1, dB; eligible frames = P1 layer 150-600 > -70 dBFS)')
sets = {'all37': R, 'vanila14': [r for r in R if r['group'] == 'v'], 'rayark23': [r for r in R if r['group'] == 'r']}
for row in ('v15', 'v16c'):
    P(f'\n## {row}')
    for sn, S in sets.items():
        P(f'[{sn}] n={len(S)}')
        for k, lab in (('mid', '150-600'), ('a', '150-200'), ('b', '200-300')):
            P(f'  layer {lab}: ' + stat([db(r[row]['E'][k], r['p1']['E'][k]) for r in S]))
        for o, ol in (('yL', 'limited out'), ('yU', 'pre-limiter')):
            for m, ml in (('rms_el', 'rms elig'), ('rms_all', 'rms all'), ('k_el', 'K elig'), ('k_all', 'K all')):
                P(f'  {ol} {ml}: ' + stat([db(r[row][o][m], r['p1'][o][m]) for r in S]))
    m = np.median([db(r[row]['E']['mid'], r['p1']['E']['mid']) for r in R])
    t = -m
    P(f'TRIM {row}: median(all37) {m:+.3f} -> trim {t:+.3f} -> rounded 0.5: {np.round(t*2)/2:+.1f}')
P('\n## per song (v15 mid, v16c mid, v15 limited-out K all, v16c same)')
for r in R:
    P(f"{r['song']:2d} {r['group']} elig {r['n_elig']:3d}/{r['nframes']} {r['name'][:40]:40s} v15 {db(r['v15']['E']['mid'],r['p1']['E']['mid']):+6.2f}  v16c {db(r['v16c']['E']['mid'],r['p1']['E']['mid']):+6.2f}   outK v15 {db(r['v15']['yL']['k_all'],r['p1']['yL']['k_all']):+5.2f} v16c {db(r['v16c']['yL']['k_all'],r['p1']['yL']['k_all']):+5.2f}")
open('/home/ksysh/r3a-dev/plan16/S19/TR/tables.txt', 'w').write('\n'.join(out))
print('\n'.join(out))
