"""S19-HP tables + the mechanical 19.7 / 19.7.1 decision (definitions: HP/CHOICES.md). Reads HP/res/*.json and suite results.json only."""
import json, sys
import numpy as np
from pathlib import Path
HP = Path('/home/ksysh/r3a-dev/plan16/S19/HP'); R = HP / 'res'
A5S = Path('/home/ksysh/r3a-dev/plan16/A5P/suite')
FS = 48000; BOX = 240
ROWS = ['p1', 'v15', 'b3p2', 'hp8_150c1', 'hp8_135c1', 'hp8_150c0']
HPR = ROWS[3:]
NAME = {'p1': 'P1', 'v15': 'v1.5', 'b3p2': 'v1.6-b', 'hp8_150c1': 'BW8 150 c1', 'hp8_135c1': 'BW8 135 c1', 'hp8_150c0': 'BW8 150 c0'}
USER = (6, 9); HELD = [i for i in range(14) if i not in USER]
db = lambda p: 10 * np.log10(max(p, 1e-30))
OUT = []
def pr(s=''):
    print(s); OUT.append(s)
def load(l, i):
    return json.load(open(R / f'{l}_s{i:02d}.json'))
D = {(l, i): load(l, i) for l in ROWS + ['b3p2_19'] for i in range(14)}
def usersegs(l):
    segs = []
    for i in (9, 6):
        for s in D[(l, i)]['segs']:
            s = dict(s); s['song'] = i; segs.append(s)
    return segs
mid = lambda f: f['150-200'] + f['200-300'] + f['300-600']
def fpool(sg):
    return {k: sum(s['fft'][k] for s in sg) for k in sg[0]['fft']}
names = [f'{"app" if s["song"] == 9 else "rem"}{s["t0"]:g}' for s in usersegs('p1')]

# ---------------------------------------------------------------- onset-masked 20-140 energy (G1)
def masked(l, seg_l, seg_ref, iso=0.0, full=False):
    """sum of 5 ms boxes of row l whose start lies in [t, t+100 ms) of an onset of the v1.6-b set (seg_ref), and the number of such boxes.
    iso > 0 (supplementary, not in the decision): only onsets with no other onset in the preceding iso seconds; full=True also returns the sum/number of the other boxes"""
    ons = np.array(seg_ref['onsets']); eb = np.array(seg_l['eb']); s = (seg_l['b0'] + np.arange(len(eb))) * BOX / FS
    if iso > 0 and len(ons):
        ons = ons[np.concatenate([[True], np.diff(ons) >= iso])]
    if len(ons) == 0:
        return (0.0, 0, float(eb.sum()), len(eb)) if full else (0.0, 0)
    k = np.searchsorted(ons, s, 'right') - 1
    m = (k >= 0) & (s - ons[np.maximum(k, 0)] < 0.1)
    if full:
        return float(eb[m].sum()), int(m.sum()), float(eb[~m].sum()), int((~m).sum())
    return float(eb[m].sum()), int(m.sum())

pr('windows (order): ' + ' '.join(names)); pr()
pr('== 1. MAIN, user windows pooled (7) ==')
pr('row | 20-140 dBFS (box mean) | gain vs v1.6-b | 20-140/150-600 dB (FFT) | gain vs v1.6-b | windows improved (abs, of 7) | 150-600 vs v1.6-b | 150-200 vs v1.6-b | 200-300 | 300-600')
U = {}
for l in ROWS:
    sg = usersegs(l); f = fpool(sg)
    U[l] = dict(lvl=db(np.mean([s['e140'] for s in sg])), r=db(f['20-140']) - db(mid(f)), per=[db(s['e140']) for s in sg], perr=[db(s['fft']['20-140']) - db(mid(s['fft'])) for s in sg], f=f)
for l in ROWS:
    u, b = U[l], U['b3p2']
    nimp = sum(1 for a, c in zip(u['per'], b['per']) if a < c)
    pr(f'{NAME[l]:11s} | {u["lvl"]:7.1f} | {u["lvl"] - b["lvl"]:+6.2f} | {u["r"]:7.1f} | {u["r"] - b["r"]:+6.2f} | {nimp} | {db(mid(u["f"])) - db(mid(b["f"])):+6.2f} | {db(u["f"]["150-200"]) - db(b["f"]["150-200"]):+6.2f} | {db(u["f"]["200-300"]) - db(b["f"]["200-300"]):+6.2f} | {db(u["f"]["300-600"]) - db(b["f"]["300-600"]):+6.2f}')
pr()
pr('per window 20-140 dBFS | ' + ' '.join(f'{n:>8s}' for n in names));
for l in ROWS:
    pr(f'{NAME[l]:11s} | ' + ' '.join(f'{x:8.1f}' for x in U[l]['per']))
pr('per window 20-140 gap to P1 (dB) | ')
for l in ROWS[1:]:
    pr(f'{NAME[l]:11s} | ' + ' '.join(f'{a - b:+8.1f}' for a, b in zip(U[l]['per'], U['p1']['per'])))
pr('per window 20-140/150-600 dB | ')
for l in ROWS:
    pr(f'{NAME[l]:11s} | ' + ' '.join(f'{x:8.1f}' for x in U[l]['perr']))
pr('rank (highest 20-140 first): ')
for l in ROWS:
    o = np.argsort(U[l]['per'])[::-1]
    pr(f'{NAME[l]:11s} | ' + ' > '.join(f'{names[k]}({U[l]["per"][k]:.0f})' for k in o))
pr()
pr('== 2. MAIN, held-out 12 songs (30 s excerpt), median over songs ==')
pr('row | 20-140 dBFS | gain vs v1.6-b | 20-140/150-600 dB | gain vs v1.6-b | 150-600 vs v1.6-b | 150-200 vs v1.6-b | #songs where abs not worse than v1.6-b')
H_ = {}
for l in ROWS:
    lv, r, c1, c2 = [], [], [], []
    for i in HELD:
        s = D[(l, i)]['segs'][0]; s0 = D[('b3p2', i)]['segs'][0]; f = s['fft']; f0 = s0['fft']
        lv.append(db(s['e140'])); r.append(db(f['20-140']) - db(mid(f))); c1.append(db(mid(f)) - db(mid(f0))); c2.append(db(f['150-200']) - db(f0['150-200']))
    H_[l] = dict(lv=np.array(lv), r=np.array(r), c1=np.array(c1), c2=np.array(c2))
for l in ROWS:
    h, b = H_[l], H_['b3p2']
    pr(f'{NAME[l]:11s} | {np.median(h["lv"]):7.1f} | {np.median(h["lv"]) - np.median(b["lv"]):+6.2f} | {np.median(h["r"]):7.1f} | {np.median(h["r"]) - np.median(b["r"]):+6.2f} | {np.median(h["c1"]):+6.2f} | {np.median(h["c2"]):+6.2f} | {int((h["lv"] <= b["lv"] + 1e-9).sum())}')
pr()
pr('== G1. onset ringing: 20-140 Hz energy of the 5 ms boxes inside [onset, onset+100 ms) (onsets of v1.6-b trace) ==')
G1 = {}
for l in ROWS:
    tot, nb_, ntot = 0.0, 0, 0
    for i in (9, 6):
        for sl, sr in zip(D[(l, i)]['segs'], D[('b3p2', i)]['segs']):
            e, n = masked(l, sl, sr); tot += e; nb_ += n; ntot += len(sl['eb'])
    hl = []
    for i in HELD:
        e, n = masked(l, D[(l, i)]['segs'][0], D[('b3p2', i)]['segs'][0]); hl.append(db(e / max(len(D[(l, i)]['segs'][0]['eb']), 1)))
    G1[l] = dict(user_db=db(tot / ntot), frac=nb_ / ntot, held=float(np.median(hl)))
pr('row | user 7 windows: mean 20-140 energy per box over all boxes, masked-only sum (dB re total boxes) | masked fraction of boxes | vs v1.6-b | held-out median (dB) | vs v1.6-b')
for l in ROWS:
    g, b = G1[l], G1['b3p2']
    pr(f'{NAME[l]:11s} | {g["user_db"]:7.1f} | {100 * g["frac"]:5.1f} % | {g["user_db"] - b["user_db"]:+6.2f} | {g["held"]:7.1f} | {g["held"] - b["held"]:+6.2f}')
pr('(masked-only energy shares: mean over the same boxes for all rows; it is the total energy of masked boxes divided by all boxes of the segments)')
pr()
pr('-- G1 supplementary (NOT in the decision; chosen after seeing that 87 % of the boxes are masked): isolated onsets only (no other birth in the preceding 150 ms), mean 20-140 energy per box inside the 100 ms after them vs per box elsewhere --')
pr('row | user 7 windows: masked boxes % | masked per-box dB | other per-box dB | contrast dB (masked - other) | contrast vs v1.6-b | held-out median contrast | vs v1.6-b')
GI = {}
for l in ROWS:
    em = nm = eo = no = 0
    for i in (9, 6):
        for sl, sr in zip(D[(l, i)]['segs'], D[('b3p2', i)]['segs']):
            a, b_, c, d_ = masked(l, sl, sr, iso=0.15, full=True); em += a; nm += b_; eo += c; no += d_
    hc = []
    for i in HELD:
        a, b_, c, d_ = masked(l, D[(l, i)]['segs'][0], D[('b3p2', i)]['segs'][0], iso=0.15, full=True)
        hc.append(db(a / max(b_, 1)) - db(c / max(d_, 1)))
    GI[l] = dict(frac=nm / (nm + no), m=db(em / max(nm, 1)), o=db(eo / max(no, 1)), con=db(em / max(nm, 1)) - db(eo / max(no, 1)), held=float(np.median(hc)))
for l in ROWS:
    g, b = GI[l], GI['b3p2']
    pr(f'{NAME[l]:11s} | {100 * g["frac"]:5.1f} | {g["m"]:7.1f} | {g["o"]:7.1f} | {g["con"]:+6.2f} | {g["con"] - b["con"]:+6.2f} | {g["held"]:+6.2f} | {g["held"] - b["held"]:+6.2f}')
pr()

# ---------------------------------------------------------------- suite
def suite(l):
    p = (A5S / l / 'results.json') if l in ('b3p2', 'v15') else (HP / 'suite' / l / 'results.json')
    j = json.load(open(p)); return {c['id']: c['value'] for c in j['checks']}, {c['id']: c.get('p1') for c in j['checks']}
SV, SP = {}, {}
for l in ['v15', 'b3p2'] + HPR:
    SV[l], SP[l] = suite(l)
P1 = SP['b3p2']
pr('== G3. V2 phase alignment (|dphi| rad) and attack (report only) ==')
pr('row | V2.k2 | V2.k3 | V3a peak ms | V3h.bare.rise90 | V3h.25.rise90 | V3h.6.rise90 | V3b dB | V3h.bare.tail | V3h.25.tail')
pr(f'{"P1":11s} | ' + ' | '.join(f'{P1[k]:+.4f}' if k.startswith('V2') else f'{P1[k]:.2f}' for k in ('V2.k2', 'V2.k3', 'V3a', 'V3h.bare.rise90', 'V3h.25.rise90', 'V3h.6.rise90', 'V3b', 'V3h.bare.tail', 'V3h.25.tail')))
for l in ['v15', 'b3p2'] + HPR:
    pr(f'{NAME[l]:11s} | ' + ' | '.join(f'{SV[l][k]:+.4f}' if k.startswith('V2') else f'{SV[l][k]:.2f}' for k in ('V2.k2', 'V2.k3', 'V3a', 'V3h.bare.rise90', 'V3h.25.rise90', 'V3h.6.rise90', 'V3b', 'V3h.bare.tail', 'V3h.25.tail')))
pr()
pr('== G4. analysis trace identity vs v1.6-b (14 songs, SHA1 of the full-song trace) ==')
G4 = {}
for l in ['b3p2_19', 'v15'] + HPR:
    full = sum(D[(l, i)]['tr_sha_all'] == D[('b3p2', i)]['tr_sha_all'] for i in range(14))
    keep = sum(D[(l, i)]['tr_sha_keep'] == D[('b3p2', i)]['tr_sha_keep'] for i in range(14))
    G4[l] = (full, keep)
    pr(f'{l:11s} | all 22 fields identical in {full}/14 songs | all but psi_2/psi_3 identical in {keep}/14 songs')
pr()

# ---------------------------------------------------------------- excursion proxy
pr('== EXCURSION PROXY (report only): app input HP LR4 100 Hz dry + layer, 20-400 Hz ==')
pr('row | user windows: peak dBFS (max) | median of 200 ms peaks (dBFS, mean over windows) | 2-12 Hz pulsing M dB (mean) | peak: dry only | M: dry only || held-out median: peak | pk200 median | M')
X = {}
for l in ROWS:
    sg = usersegs(l)
    pk = max(s['sum']['peak'] for s in sg); p2 = np.mean([s['sum']['pk200_med'] for s in sg]); M = np.mean([s['sum']['M'] for s in sg])
    pkd = max(s['dry']['peak'] for s in sg); Md = np.mean([s['dry']['M'] for s in sg])
    hp = np.median([D[(l, i)]['segs'][0]['sum']['peak'] for i in HELD]); hq = np.median([D[(l, i)]['segs'][0]['sum']['pk200_med'] for i in HELD])
    hm = np.median([D[(l, i)]['segs'][0]['sum']['M'] for i in HELD])
    X[l] = dict(pk=pk, p2=p2, M=M, per_pk=[s['sum']['peak'] for s in sg], per_M=[s['sum']['M'] for s in sg])
    pr(f'{NAME[l]:11s} | {pk:7.2f} | {p2:7.2f} | {M:6.3f} | {pkd:7.2f} | {Md:6.3f} || {hp:7.2f} | {hq:7.2f} | {hm:6.3f}')
pr('per window peak dBFS | ' + ' '.join(f'{n:>8s}' for n in names))
for l in ROWS:
    pr(f'{NAME[l]:11s} | ' + ' '.join(f'{x:8.2f}' for x in X[l]['per_pk']))
pr('per window pulsing M (dB) | ')
for l in ROWS:
    pr(f'{NAME[l]:11s} | ' + ' '.join(f'{x:8.3f}' for x in X[l]['per_M']))
dryM = [s['dry']['M'] for s in usersegs('b3p2')]; dryP = [s['dry']['peak'] for s in usersegs('b3p2')]
pr('dry-only (HP100) per window peak: ' + ' '.join(f'{x:.2f}' for x in dryP) + ' ; M: ' + ' '.join(f'{x:.3f}' for x in dryM))
pr()

# ---------------------------------------------------------------- decision
pr('== DECISION (19.7 / 19.7.1, mechanical) ==')
b = 'b3p2'
res = {}
for l in HPR:
    u, ub = U[l], U[b]
    d_abs = u['lvl'] - ub['lvl']; d_r = u['r'] - ub['r']
    nimp = sum(1 for a, c in zip(u['per'], ub['per']) if a < c)
    held_ok = np.median(H_[l]['lv']) <= np.median(H_[b]['lv']) + 1e-9 and np.median(H_[l]['r']) <= np.median(H_[b]['r']) + 1e-9
    main_ok = d_abs <= -3 and d_r <= -3 and nimp >= 5 and held_ok
    # G1
    g1 = G1[l]['user_db'] - G1[b]['user_db']; g1_bad = (G1[l]['user_db'] > G1['p1']['user_db']) and g1 > 1.0
    # G2
    body = db(mid(u['f'])) - db(mid(ub['f'])); body_p1 = db(mid(u['f'])) - db(mid(U['p1']['f'])); g2_bad = body_p1 < 0 and body < -1.0
    # G3
    g3 = []
    for k in ('V2.k2', 'V2.k3'):
        v, v0, vp = abs(SV[l][k]), abs(SV[b][k]), abs(P1[k])
        g3.append((k, v, abs(v) > 0.3 or (v > vp and v - v0 > 0.1)))
    g3_bad = any(x[2] for x in g3)
    # G4
    need = G4[l][0] if l.endswith('c0') else G4[l][1]
    g4_bad = need != 14
    ok = main_ok and not (g1_bad or g2_bad or g3_bad or g4_bad)
    res[l] = dict(ok=ok, abs=u['lvl'], d_abs=d_abs, d_r=d_r, nimp=nimp, held_ok=held_ok, body=body)
    pr(f'{NAME[l]:11s}: main(abs {d_abs:+.2f} dB, ratio {d_r:+.2f} dB, windows {nimp}/7, held-out ok {held_ok}) -> {"PASS" if main_ok else "FAIL"}; '
       f'G1 onset {g1:+.2f} dB (P1 {"below" if G1[l]["user_db"] <= G1["p1"]["user_db"] else "above"}) -> {"FAIL" if g1_bad else "ok"}; G2 body {body:+.2f} dB -> {"FAIL" if g2_bad else "ok"}; '
       f'G3 ' + ', '.join(f'{k} {v:.4f}' for k, v, _ in g3) + f' -> {"FAIL" if g3_bad else "ok"}; G4 trace {need}/14 -> {"FAIL" if g4_bad else "ok"}; ROW {"PASSES" if ok else "does not pass"}')
passing = [l for l in HPR if res[l]['ok']]
if passing:
    best = min(res[l]['abs'] for l in passing)
    ties = [l for l in passing if res[l]['abs'] - best <= 1.0]
    pick = max(ties, key=lambda l: res[l]['body'])   # within 1 dB: smaller body loss
    pr(f'ADOPT (model 16 -> v1.6-c): {NAME[pick]} [{pick}]; passing rows: {passing}')
else:
    pr('ADOPT: none')
open(HP / 'tables.txt', 'w').write('\n'.join(OUT) + '\n')
