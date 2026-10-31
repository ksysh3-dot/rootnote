"""Applies the 18.15 guards and decision rule (= 18.12 thresholds, plus V3e 10 Hz <= +1 dB) mechanically to the six A5'' rows; bb (A5' best) and b0 (base) are references. Inputs: suite/<row>/results.json, burst_pp.json, right_<row>.json, primary_summary.json (a5_ptable.py), fosc_pp.json."""
import json, sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5PP')
from pathlib import Path
import a5pprows as AR
V = Path('/home/ksysh/r3a-dev/plan16/A5PP')
b = AR.BASEL
labs = ['v15'] + AR.GRID
J = {l: json.loads((V / 'suite' / l / 'results.json').read_text()) for l in labs}
SV = {l: {c['id']: c['value'] for c in J[l]['checks']} for l in labs}
P1 = {c['id']: c.get('p1') for c in J['v15']['checks']}
json.dump(dict(SV=SV, P1=P1), open(V / 'suite_values_pp.json', 'w'), indent=1)
BU = json.load(open(V / 'burst_pp.json'))
PR = json.load(open(V / 'primary_summary.json'))
FO = json.load(open(V / 'fosc_pp.json'))
FR = {l: json.load(open(V / f'right_{l}.json'))['summary']['all10']['right_vs_R3_dB_sa'] for l in AR.GRID}
p1_b473 = BU['p1|4.73']['burst_R1']
NEW = AR.NEW


def fosc_delta(l):
    """max over the six synthetic signals of (median |f_osc error| row - base), cent"""
    return max(FO[l][k]['med_abs'] - FO[b][k]['med_abs'] for k in FO[b])


def guards(l):
    s, s0, sv = SV[l], SV[b], SV['v15']
    g = {}
    g['V3a peak <= +2 ms'] = (s['V3a'] - s0['V3a'], s['V3a'] - s0['V3a'] <= 2)
    g['rise90 bare <= +2 ms'] = (s['V3h.bare.rise90'] - s0['V3h.bare.rise90'], s['V3h.bare.rise90'] - s0['V3h.bare.rise90'] <= 2)
    g['rise90 25 dB <= +2 ms'] = (s['V3h.25.rise90'] - s0['V3h.25.rise90'], s['V3h.25.rise90'] - s0['V3h.25.rise90'] <= 2)
    g['V3b <= +1 dB'] = (s['V3b'] - s0['V3b'], s['V3b'] - s0['V3b'] <= 1)
    g['V3i.trans <= 0.5 /s'] = (s['V3i.trans'], s['V3i.trans'] <= 0.5)
    for k in ('V4b.bass+pink', 'V4b.bass+kick+pink'):
        d = 100 * (s[k] - s0[k])
        g[k + ' <= +1 %p'] = (d, d <= 1)
    r = BU[l + '|4.73']['burst_R1']
    g['LOGOFF 4.73 R1 <= max(3, P1+1)'] = (r, r <= max(3.0, p1_b473 + 1))
    g['V3e 10 Hz beat <= +1 dB'] = (s['V3e.df10.beat'] - s0['V3e.df10.beat'], s['V3e.df10.beat'] - s0['V3e.df10.beat'] <= 1)
    d = FR[l] - FR[b]
    g['right layer F >= -0.5 dB'] = (d, d >= -0.5)
    for f_ in ('35', '45'):
        k = f'V3g.{f_}.noREL'
        g[f'{k} <= v1.5 + 5 hops'] = (s[k] - sv[k], s[k] - sv[k] <= 5)
    d = PR[l]['mid'] - PR[b]['mid']
    g['body: 150-600 Hz level >= base - 2 dB'] = (d, d >= -2.0)
    # pitch following (18.12)
    g['V3c.enter <= +5 ms'] = (s['V3c.enter'] - s0['V3c.enter'], s['V3c.enter'] - s0['V3c.enter'] <= 5)
    g['V3e 4 Hz beat <= +1 dB'] = (s['V3e.df4.beat'] - s0['V3e.df4.beat'], s['V3e.df4.beat'] - s0['V3e.df4.beat'] <= 1)
    d = fosc_delta(l)
    g['f_osc glide/vib median err <= +10 cent'] = (d, d <= 10)
    return g


G = {l: guards(l) for l in AR.GRID if l != b}
print('GUARDS vs base %s (value, pass)   [v1.5 noREL 35/45: %s / %s; base V3c.enter %s, V3e.df4.beat %s]' % (b, SV['v15']['V3g.35.noREL'], SV['v15']['V3g.45.noREL'], SV[b]['V3c.enter'], SV[b]['V3e.df4.beat']))
tab = {}
for l, g in G.items():
    ok = all(v[1] for v in g.values())
    fails = [k for k, v in g.items() if not v[1]]
    tab[l] = (ok, fails)
    print(f'\n{AR.NAMES[l]} [{l}]: ALL PASS = {ok}   fails: {fails}')
    for k, (v, o) in g.items():
        print(f'   {k:42s} {v:9.3f} {"ok" if o else "FAIL"}')
print('\nPRIMARY: pooled 20-150/150-600 ratio (dB, lower = better), gain vs base = base - row; windows improved (of 7)')
for l in ['p1', 'v15'] + AR.GRID:
    nimp = sum(1 for a, c in zip(PR[l]['per_window'], PR[b]['per_window']) if a < c)
    print(f'  {AR.NAMES[l]:30s} [{l}] ratio {PR[l]["ratio"]:7.2f}   gain {PR[b]["ratio"] - PR[l]["ratio"]:+6.2f}   windows improved {nimp}   jumps>6dB {PR[l]["jumps"]}')
qual = []
for l in NEW:
    gain = PR[b]['ratio'] - PR[l]['ratio']
    nimp = sum(1 for a, c in zip(PR[l]['per_window'], PR[b]['per_window']) if a < c)
    if tab[l][0] and gain >= 3.0 and nimp >= 5:
        qual.append(l)
print('\nqualifying (six A5pp rows only: all guards pass, gain >= 3 dB, >= 5 of 7 windows better):', qual)
if qual:
    best = min(PR[l]['ratio'] for l in qual)
    ties = [l for l in qual if PR[l]['ratio'] - best <= 0.5]
    # tie within 0.5 dB: closest to base = larger beta, larger psiSlew
    pick = min(ties, key=lambda l: AR.ROWS[l][2]['betaOnsetMs'])   # tie within 0.5 dB: the shorter betaOnsetMs (smaller change)
    print('ADOPT:', AR.NAMES[pick], pick)
else:
    print('ADOPT: none')
