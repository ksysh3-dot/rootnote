"""Applies the 18.5 guards and decision rule mechanically. Inputs: suite_values16.json (rerun with all labels below), burst16b.json, rerise16b.json, right_<label>.json.
Guards are the 18.3 four categories (vs v1.5) + V3g 35/45 Hz noREL <= v1.5 + 5 hops. Adoption: all guards pass AND V3h 25 dB tail >= 10 ms shorter than the v1.6-a base (A2 only);
several -> shortest tail, tie within 2 ms -> (i). A value worse than P1 is flagged '(>P1)'."""
import json
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/V16A')
NAME = {'v15': 'v1.5', 'a2': 'v1.6-a base (A2 1.5)', 'c8a2': 'A1 8/1.5 (uncond)', 'i8a2': 'A1p (i) 8', 'i16a2': 'A1p (i) 16', 'ii8a2': 'A1p (ii) 8', 'ii16a2': 'A1p (ii) 16'}
labs = list(NAME)
J = {l: json.loads((V / 'suite' / l / 'results.json').read_text()) for l in labs}
SV = {l: {c['id']: c['value'] for c in J[l]['checks']} for l in labs}
P1 = {c['id']: c.get('p1') for c in J['v15']['checks']}
json.dump(dict(SV=SV, P1=P1), open(V / 'suite_values16b.json', 'w'), indent=1)
BU = json.load(open(V / 'burst16b.json')); RR = json.load(open(V / 'rerise16b.json'))
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
    r = BU[NAME[l] + '|4.73']['burst_R1'] if NAME[l] + '|4.73' in BU else None
    g['LOGOFF 4.73 R1 <= max(3, P1+1)'] = (r, r <= max(3.0, p1_burst473 + 1), r > p1_burst473)
    g['V3e 10 Hz beat <= +1 dB'] = (s['V3e.df10.beat'] - s0['V3e.df10.beat'], s['V3e.df10.beat'] - s0['V3e.df10.beat'] <= 1, s['V3e.df10.beat'] > P1['V3e.df10.beat'])
    d = RIGHT[l] - RIGHT[b]
    g['right layer F >= -0.5 dB'] = (d, d >= -0.5, None)
    for f_ in ('35', '45'):
        k = f'V3g.{f_}.noREL'
        g[f'{k} <= v1.5 + 5 hops'] = (s[k] - s0[k], s[k] - s0[k] <= 5, None)
    return g


G = {l: guards(l) for l in labs if l != b}
print('GUARDS (value, pass, worse-than-P1)   [v1.5 noREL 35/45: %s / %s]' % (SV[b]['V3g.35.noREL'], SV[b]['V3g.45.noREL']))
for l, g in G.items():
    print(f'\n{NAME[l]}: ALL PASS = {all(v[1] for v in g.values())}')
    for k, (v, ok, wp) in g.items():
        print(f'   {k:36s} {v:8.3f} {"ok  " if ok else "FAIL"} {"(>P1)" if wp else ""}')
passall = {l: all(v[1] for v in G[l].values()) for l in G}
tail = {l: SV[l]['V3h.25.tail'] for l in labs}
print('\nV3h 25 dB tail (ms):', {NAME[l]: round(t, 2) for l, t in tail.items()}, ' P1', P1['V3h.25.tail'])
base = tail['a2']
cand = [l for l in ('i8a2', 'i16a2', 'ii8a2', 'ii16a2') if passall[l] and base - tail[l] >= 10]
print(f'guards pass: {[NAME[l] for l in G if l in ("i8a2", "i16a2", "ii8a2", "ii16a2") and passall[l]]}; tail >= 10 ms under base ({base:.2f} -> <= {base - 10:.2f}): {[NAME[l] for l in cand]}')
best = None
if cand:
    mn = min(tail[l] for l in cand)
    ties = [l for l in cand if tail[l] - mn <= 2.0]
    pri = [l for l in ties if l.startswith('i') and not l.startswith('ii')]
    best = (pri or ties)[0] if not pri else min(pri, key=lambda l: tail[l])
    if not pri:
        best = min(ties, key=lambda l: tail[l])
print('=> adopted:', NAME.get(best, 'none (v1.6-a = A2 only)'))
print('\nRERISE (output layer, 6 dB+ notes / n, median dB):', {k: (v['rerise_n_above6'], round(v['rerise_median'], 2), round(v['tail_bp_ms'], 1)) for k, v in RR.items()})
