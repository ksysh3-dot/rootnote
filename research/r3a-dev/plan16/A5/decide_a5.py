"""Applies the 18.9 guards and decision rule mechanically. Inputs: suite/<row>/results.json, burst_a5.json, right_<row>.json, primary_summary.json (a5_ptable.py)."""
import json, sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
from pathlib import Path
import a5rows as AR
V = Path('/home/ksysh/r3a-dev/plan16/A5')
labs = ['v15', 'base'] + AR.A5LABELS
J = {l: json.loads((V / 'suite' / l / 'results.json').read_text()) for l in labs}
SV = {l: {c['id']: c['value'] for c in J[l]['checks']} for l in labs}
P1 = {c['id']: c.get('p1') for c in J['v15']['checks']}
json.dump(dict(SV=SV, P1=P1), open(V / 'suite_values_a5.json', 'w'), indent=1)
BU = json.load(open(V / 'burst_a5.json'))
PR = json.load(open(V / 'primary_summary.json'))
FR = {l: json.load(open(V / f'right_{l}.json'))['summary']['all10']['right_vs_R3_dB_sa'] for l in labs}
b = 'base'
p1_b473 = BU['p1|4.73']['burst_R1']


def guards(l):
    s, s0, sv = SV[l], SV[b], SV['v15']
    g = {}
    g['V3a peak <= +2 ms'] = (s['V3a'] - s0['V3a'], s['V3a'] - s0['V3a'] <= 2, s['V3a'] > P1['V3a'])
    g['rise90 bare <= +2 ms'] = (s['V3h.bare.rise90'] - s0['V3h.bare.rise90'], s['V3h.bare.rise90'] - s0['V3h.bare.rise90'] <= 2, s['V3h.bare.rise90'] > P1['V3h.bare.rise90'])
    g['rise90 25 dB <= +2 ms'] = (s['V3h.25.rise90'] - s0['V3h.25.rise90'], s['V3h.25.rise90'] - s0['V3h.25.rise90'] <= 2, s['V3h.25.rise90'] > P1['V3h.25.rise90'])
    g['V3b <= +1 dB'] = (s['V3b'] - s0['V3b'], s['V3b'] - s0['V3b'] <= 1, s['V3b'] > P1['V3b'])
    g['V3i.trans <= 0.5 /s'] = (s['V3i.trans'], s['V3i.trans'] <= 0.5, s['V3i.trans'] > P1['V3i.trans'])
    for k in ('V4b.bass+pink', 'V4b.bass+kick+pink'):
        d = 100 * (s[k] - s0[k])
        g[k + ' <= +1 %p'] = (d, d <= 1, s[k] > P1[k])
    r = BU[l + '|4.73']['burst_R1']
    g['LOGOFF 4.73 R1 <= max(3, P1+1)'] = (r, r <= max(3.0, p1_b473 + 1), r > p1_b473)
    g['V3e 10 Hz beat <= +1 dB'] = (s['V3e.df10.beat'] - s0['V3e.df10.beat'], s['V3e.df10.beat'] - s0['V3e.df10.beat'] <= 1, s['V3e.df10.beat'] > P1['V3e.df10.beat'])
    d = FR[l] - FR[b]
    g['right layer F >= -0.5 dB'] = (d, d >= -0.5, None)
    for f_ in ('35', '45'):
        k = f'V3g.{f_}.noREL'
        g[f'{k} <= v1.5 + 5 hops'] = (s[k] - sv[k], s[k] - sv[k] <= 5, None)
    d = PR[l]['mid'] - PR[b]['mid']
    g['body: 150-600 Hz level >= base - 2 dB'] = (d, d >= -2.0, None)
    return g


G = {l: guards(l) for l in AR.A5LABELS}
print('GUARDS vs v1.6-a base (value, pass, worse-than-P1)   [v1.5 noREL 35/45: %s / %s]' % (SV['v15']['V3g.35.noREL'], SV['v15']['V3g.45.noREL']))
tab = {}
for l, g in G.items():
    ok = all(v[1] for v in g.values())
    fails = [k for k, v in g.items() if not v[1]]
    tab[l] = (ok, fails)
    print(f'\n{AR.NAMES[l]}: ALL PASS = {ok}   fails: {fails}')
    for k, (v, o, wp) in g.items():
        print(f'   {k:40s} {v:8.3f} {"ok  " if o else "FAIL"} {"(>P1)" if wp else ""}')
print('\nPRIMARY: pooled 20-150/150-600 ratio (dB, lower = better), gain vs base = base - row')
for l in ['p1', 'v15', 'base'] + AR.A5LABELS:
    print(f'  {AR.NAMES[l]:22s} ratio {PR[l]["ratio"]:7.2f}   gain {PR["base"]["ratio"] - PR[l]["ratio"]:+6.2f}   jumps>6dB {PR[l]["jumps"]}')
qual = [l for l in AR.A5LABELS if tab[l][0] and PR['base']['ratio'] - PR[l]['ratio'] >= 6.0]
print('\nqualifying (all guards pass and gain >= 6 dB):', qual)
if qual:
    best = min(PR[l]['ratio'] for l in qual)
    ties = [l for l in qual if PR[l]['ratio'] - best <= 1.0]
    pick = max(ties, key=lambda l: int(l[1:l.index('m')]))
    print('ADOPT:', AR.NAMES[pick])
else:
    print('ADOPT: none')
