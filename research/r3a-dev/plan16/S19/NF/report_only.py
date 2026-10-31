import json
from pathlib import Path
A = Path('/home/ksysh/r3a-dev/plan16/A5P'); N = Path('/home/ksysh/r3a-dev/plan16/S19/NF')
rows = ['b0p0', 'b3p2', 'nfa48', 'nfa72', 'nfa96', 'nfb48', 'nfb96']
def sv(l):
    d = A if l in ('b0p0', 'b3p2') else N
    return {c['id']: c['value'] for c in json.load(open(d / 'suite' / l / 'results.json'))['checks']}
p1 = {c['id']: c['p1'] for c in json.load(open(A / 'suite/b3p2/results.json'))['checks']}
keys = ['V3c.enter', 'V3e.df4.beat', 'V3e.df10.beat', 'V6b', 'V3h.25.tail', 'V3h.bare.tail', 'V3d', 'V3a', 'V3h.25.rise90', 'V3b']
print('P1', [p1[k] for k in keys])
print('keys', keys)
for l in rows:
    d = sv(l); print(l, [round(d[k], 2) for k in keys])
R = {}
for src in (A, N):
    R.update(json.load(open(src / 'rerise_p.json'))) if src == N else None
RA = json.load(open(A / 'rerise_p.json'))
for l in ['p1'] + rows:
    r = (R if l in R else RA)[l]
    print('rerise', l, round(r['rerise_median'], 2), 'tail_raw', round(r['tail_raw_ms'], 1), 'tail_bp', round(r['tail_bp_ms'], 1))
F = json.load(open(N / 'fosc_p.json'))
for l, v in F.items():
    print('fosc', l, {k: round(x['med_abs'], 1) for k, x in v.items() if x['med_abs'] is not None})
L = json.load(open(N / 'logoff45_p.json'))
for l, v in L.items():
    print('logoff45', l, v)
B = json.load(open(N / 'burst_p.json'))
for k, v in B.items():
    print('burst', k, round(v['burst_R1'], 2))
for l in rows[2:] + ['b3p2', 'b0p0']:
    f = json.load(open((A if l in ('b0p0', 'b3p2') else N) / f'right_{l}.json'))['summary']['all10']
    print('F', l, round(f['right_vs_R3_dB_sa'], 2), 'V6b-ish', round(f['right_vs_R3_dB_v6b'], 2))
