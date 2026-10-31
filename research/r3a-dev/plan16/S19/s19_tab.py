import json, numpy as np
from pathlib import Path
S19 = Path('/home/ksysh/r3a-dev/plan16/S19')
R = json.load(open(S19 / 's19_attr.json'))
TYPES = ['birth', 'REL>ON', 'ON>REL', 'release', 'window', 'fosc_jump', 'amp_jump', 'note_chg']
ROWS = ['b0p0', 'b3p2', 'f4']
def shares(r):
    t = r['total']; 
    return dict(novoice=100*r['novoice']/t, none=100*r['noevent']/t, **{k: 100*r['excl'][k]/t for k in TYPES}), {k: 100*r['anym'][k]/t for k in TYPES}
db = lambda x: 10*np.log10(x+1e-30)
ref = R['b0p0']['win']['res']['total']
print('=== USER WINDOWS pooled (14 s): exclusive share % | any-match % | rate /s (in-band voices) | share per (event/s) | abs energy % of row1 total')
for lab in ROWS:
    w = R[lab]['win']; ex, an = shares(w['res']); dur = w['dur']
    print(f"[{lab}] total20-150 rel row1 {100*w['res']['total']/ref:.0f}% ({db(w['res']['total']/ref):+.2f} dB); novoice {ex['novoice']:.1f} none {ex['none']:.1f}")
    for k in TYPES:
        rate = w['counts'][k]/dur
        print(f"  {k:10s} excl {ex[k]:5.1f}  any {an[k]:5.1f}  rate {rate:6.2f}/s  share/rate {ex[k]/max(rate,1e-9):6.2f}  abs {100*w['res']['excl'][k]/ref:5.1f}%")
print('\n=== 14 SONGS median over songs (energy-weighted per song)')
meds = {}
for lab in ROWS:
    S = R[lab]['songs']
    ex_l = []; an_l = []; rate_l = []; tot = []
    for s in S:
        ex, an = shares(s['res']); ex_l.append(ex); an_l.append(an); rate_l.append({k: s['counts'][k]/s['dur'] for k in TYPES}); tot.append(s['res']['total'])
    meds[lab] = tot
    print(f"[{lab}] median novoice {np.median([e['novoice'] for e in ex_l]):.1f} none {np.median([e['none'] for e in ex_l]):.1f}  lag(median) {np.median([s['lag'][1] for s in S]):.0f} boxes, corr {np.median([s['lag'][0] for s in S]):.2f}")
    for k in TYPES:
        e = np.median([x[k] for x in ex_l]); a = np.median([x[k] for x in an_l]); r = np.median([x[k] for x in rate_l])
        epe = np.median([x[k]/max(rr[k],1e-9) for x, rr in zip(ex_l, rate_l)])
        print(f"  {k:10s} excl {e:5.1f}  any {a:5.1f}  rate {r:6.2f}/s  share/rate(med) {epe:6.2f}")
print('\n=== row ratios (total 20-150 energy, dB, per-song median) b3p2/b0p0, f4/b0p0')
a = np.array(meds['b0p0']); print(np.median(db(np.array(meds['b3p2'])/a)), np.median(db(np.array(meds['f4'])/a)))
print('per-song lag/corr b0p0:', [(s['lag'][1], round(s['lag'][0],2)) for s in R['b0p0']['songs']])
print('\n=== row2 vs row1: per-type abs energy change (windows, % of row1 total) and (14-song pooled-median of per-song abs change/row1 song total)')
for k in TYPES+['noevent','novoice']:
    g = lambda lab: (R[lab]['win']['res']['excl'][k] if k in TYPES else R[lab]['win']['res'][k])
    d2 = 100*(g('b3p2')-g('b0p0'))/ref; d3 = 100*(g('f4')-g('b0p0'))/ref
    pr = []
    for s1, s2 in zip(R['b0p0']['songs'], R['b3p2']['songs']):
        x1 = s1['res']['excl'][k] if k in TYPES else s1['res'][k]; x2 = s2['res']['excl'][k] if k in TYPES else s2['res'][k]
        pr.append(100*(x2-x1)/s1['res']['total'])
    print(f"  {k:10s} win b3p2-b0p0 {d2:+6.1f}%  f4-b0p0 {d3:+6.1f}% | songs med b3p2-b0p0 {np.median(pr):+5.1f}%")
print('\n=== "none" class split: top voice with 2*f_osc<=150 (direct in-band k=2, not splatter) -> share of total 20-150 energy %')
for lab in ROWS:
    w = R[lab]['win']['res']; sg = [100*s['res']['none_direct']/s['res']['total'] for s in R[lab]['songs']]; sn = [100*s['res']['noevent']/s['res']['total'] for s in R[lab]['songs']]
    print(f"[{lab}] windows none {100*w['noevent']/w['total']:.1f} of which direct {100*w['none_direct']/w['total']:.1f} | songs median none {np.median(sn):.1f} direct {np.median(sg):.1f}")
