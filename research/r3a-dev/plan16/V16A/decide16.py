"""Applies the 18.3 guards and decision rules mechanically. Inputs: suite_values16.json (tables16.py), burst16.json, rerise16.json, right_<label>.json, rho16.json.
Row labels: label -> display name below. Guards are vs v1.5 (same library, both params 0); a row value worse than P1 is flagged '(>P1)'."""
import json
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/V16A')
SV = json.load(open(V / 'suite_values16.json')); P1 = json.load(open(V / 'suite_p1_values16.json'))
BU = json.load(open(V / 'burst16.json')); RR = json.load(open(V / 'rerise16.json'))
NAME = {'v15': 'v1.5', 'c8': 'A1 8', 'c16': 'A1 16', 'c32': 'A1 32', 'a2': 'A2 1.5', 'c16a2': 'A1+A2 16/1.5', 'c8a2': 'A1+A2 8/1.5'}
labs = [l for l in NAME if l in SV]
RIGHT = {l: json.load(open(V / f'right_{l}.json'))['summary']['all10']['right_vs_R3_dB_sa'] for l in labs}
b = 'v15'
p1_burst473 = BU['P1|4.73']['burst_R1']


def guards(l):
    s, s0 = SV[l], SV[b]
    g = {}
    g['V3a peak <= +2 ms'] = (s['V3a'] - s0['V3a'], s['V3a'] - s0['V3a'] <= 2, s['V3a'] > P1['V3a'])
    g['rise90 bare <= +2 ms'] = (s['V3h.bare.rise90'] - s0['V3h.bare.rise90'], s['V3h.bare.rise90'] - s0['V3h.bare.rise90'] <= 2, s['V3h.bare.rise90'] > P1['V3h.bare.rise90'])
    g['rise90 25 dB <= +2 ms'] = (s['V3h.25.rise90'] - s0['V3h.25.rise90'], s['V3h.25.rise90'] - s0['V3h.25.rise90'] <= 2, s['V3h.25.rise90'] > P1['V3h.25.rise90'])
    g['V3b <= +1 dB'] = (s['V3b'] - s0['V3b'], s['V3b'] - s0['V3b'] <= 1, s['V3b'] > P1['V3b'])
    g['V3i.trans <= 0.5 /s'] = (s['V3i.trans'], s['V3i.trans'] <= 0.5, s['V3i.trans'] > P1['V3i.trans'])
    for k in ('V4b.bass+pink', 'V4b.bass+kick+pink'):
        d = 100 * (s[k] - s0[k])
        g[k + ' <= +1 %p'] = (d, d <= 1, s[k] > P1[k])
    r = BU[NAME[l] + '|4.73']['burst_R1']
    g['LOGOFF 4.73 R1 <= max(3, P1+1)'] = (r, r <= max(3.0, p1_burst473 + 1), r > p1_burst473)
    g['V3e 10 Hz beat <= +1 dB'] = (s['V3e.df10.beat'] - s0['V3e.df10.beat'], s['V3e.df10.beat'] - s0['V3e.df10.beat'] <= 1, s['V3e.df10.beat'] > P1['V3e.df10.beat'])
    d = RIGHT[l] - RIGHT[b]
    g['right layer F >= -0.5 dB'] = (d, d >= -0.5, None)
    return g


G = {l: guards(l) for l in labs if l != b}
print('GUARDS (value, pass, worse-than-P1)')
for l, g in G.items():
    print(f'\n{NAME[l]}: ALL PASS = {all(v[1] for v in g.values())}')
    for k, (v, ok, wp) in g.items():
        print(f'   {k:36s} {v:8.3f} {"ok  " if ok else "FAIL"} {"(>P1)" if wp else ""}')
passall = {l: all(v[1] for v in G[l].values()) for l in G}
tail = {l: SV[l]['V3h.25.tail'] for l in labs}
print('\nV3h 25 dB tail (ms):', {NAME[l]: round(t, 2) for l, t in tail.items()}, ' P1', P1['V3h.25.tail'])
# A1
a1 = [l for l in ('c8', 'c16', 'c32') if passall.get(l)]
a1_ok = [l for l in a1 if tail[b] - tail[l] >= 10]
best = None
if a1_ok:
    mn = min(tail[l] for l in a1_ok)
    ties = [l for l in a1_ok if tail[l] - mn <= 2.0]
    best = max(ties, key=lambda l: int(l[1:]))
print('A1 guard-passing:', [NAME[l] for l in a1], ' tail reduced >= 10 ms:', [NAME[l] for l in a1_ok], ' -> A1 best:', NAME.get(best))
# A2
d_v6b = SV[b]['V6b'] - SV['a2']['V6b']
a2_adopt = passall['a2'] and d_v6b >= 3
print(f'A2: V6b {SV[b]["V6b"]:.2f} -> {SV["a2"]["V6b"]:.2f} (reduction {d_v6b:.2f} %p), guards pass {passall["a2"]} -> adopt {a2_adopt}')
# combined
if best and a2_adopt:
    comb = {'c8': 'c8a2', 'c16': 'c16a2'}.get(best)
    for lab in ('c16a2', 'c8a2'):
        if lab in passall:
            print(f'combined {NAME[lab]}: guards pass {passall[lab]}; tail {tail[lab]:.2f} (A1 alone {tail[lab.replace("a2", "")]:.2f}), V6b {SV[lab]["V6b"]:.2f} (A2 alone {SV["a2"]["V6b"]:.2f})')
    if comb in passall:
        print('=> combination row for best A1:', NAME[comb], 'passes' if passall[comb] else 'FAILS')
