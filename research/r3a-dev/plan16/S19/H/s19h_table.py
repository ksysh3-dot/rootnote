"""S19-H tables from res/*.json (numbers only) + analytic filter response."""
import json
import numpy as np
from pathlib import Path
from scipy.signal import sosfreqz, butter
R = Path('/home/ksysh/r3a-dev/plan16/S19/H/res')
FS = 48000
ROWS = ['p1', 'v15', 'b3p2']; NAME = {'p1': 'P1', 'v15': 'v1.5', 'b3p2': 'v1.6-b'}
VARS = ['none', 'bw4_120', 'bw8_120', 'bw4_135', 'bw8_135', 'bw4_150', 'bw8_150', 'lr4_150']
USER = (6, 9); HELD = [i for i in range(14) if i not in USER]
db = lambda p: 10 * np.log10(max(p, 1e-30))
OUT = []
def pr(s=''):
    print(s); OUT.append(s)
def load(l, i):
    return json.load(open(R / f'{l}_s{i:02d}.json'))
def usersegs(l, v):
    segs = []
    for i in (9, 6):
        for s in load(l, i)['var'][v]:
            s = dict(s); s['song'] = i; segs.append(s)
    return segs
def fsum(sg, k):
    return sum(s['fft'][k] for s in sg)
def mid(f):
    return f['150-200'] + f['200-300'] + f['300-600']
def fpool(sg):
    return {k: fsum(sg, k) for k in sg[0]['fft']}
wl = lambda sg: ' '.join(f'{"app" if s["song"] == 9 else "rem"}{s["t0"]:g}' for s in sg)

pr('windows order: ' + wl(usersegs('p1', 'none')))
pr()
pr('== 1. user windows pooled (7): sub-150 level, ratios, bursts ==')
pr('row/variant | 20-140 mean dBFS (box mean) | 20-140 median box dBFS | primary 20-150/150-600 dB | 20-140/150-600 dB (FFT) | burst>2x % (pooled boxes)')
U = {}
for l in ROWS:
    for v in VARS:
        if l != 'b3p2' and v != 'none':
            continue
        sg = usersegs(l, v)
        e = np.concatenate([s['eb'] for s in sg]); r = np.concatenate([s['rm'] for s in sg])
        f = fpool(sg)
        U[(l, v)] = dict(lvl=db(np.mean([s['e140'] for s in sg])), med=db(np.median(e)), prim=db(sum(s['p_lo'] for s in sg)) - db(sum(s['p_mid'] for s in sg)),
                         r140=db(f['20-140']) - db(mid(f)), b2=100 * e[e > 2 * r].sum() / e.sum(), f=f, per=[db(s['e140']) for s in sg],
                         perr=[db(s['fft']['20-140']) - db(mid(s['fft'])) for s in sg])
        u = U[(l, v)]
        pr(f'{NAME[l]:6s} {v:8s} | {u["lvl"]:7.1f} | {u["med"]:7.1f} | {u["prim"]:7.2f} | {u["r140"]:7.1f} | {u["b2"]:5.1f}')
pr()
pr('== 2. body change vs same row uncut (pooled window FFT band energies, dB) ==')
pr('row/variant | 150-600 | 150-200 | 200-300 | 300-600 | 100-130 | 130-150')
for l in ROWS:
    for v in VARS[1:]:
        if l != 'b3p2' and v != 'none':
            continue
        a = U[(l, v)]['f']; b = U[(l, 'none')]['f']
        pr(f'{NAME[l]:6s} {v:8s} | {db(mid(a)) - db(mid(b)):+6.2f} | {db(a["150-200"]) - db(b["150-200"]):+6.2f} | {db(a["200-300"]) - db(b["200-300"]):+6.2f} | {db(a["300-600"]) - db(b["300-600"]):+6.2f} | {db(a["100-130"]) - db(b["100-130"]):+6.1f} | {db(a["130-150"]) - db(b["130-150"]):+6.1f}')
pr()
pr('== 3. per-window 20-140 dBFS (box mean) and 20-140/150-600 dB; windows: ' + wl(usersegs('p1', 'none')) + ' ==')
cols = [('p1', 'none'), ('v15', 'none'), ('b3p2', 'none')] + [('b3p2', v) for v in VARS[1:]]
for (l, v) in cols:
    u = U.get((l, v))
    if u is None:
        sg = usersegs(l, v); u = dict(per=[db(s['e140']) for s in sg], perr=[db(s['fft']['20-140']) - db(mid(s['fft'])) for s in sg])
    pr(f'{NAME[l]:6s} {v:8s} dBFS | ' + ' '.join(f'{x:7.1f}' for x in u['per']) + ' || ratio | ' + ' '.join(f'{x:6.1f}' for x in u['perr']))
names = [f'{"app" if s["song"] == 9 else "rem"}{s["t0"]:g}' for s in usersegs('p1', 'none')]
pr('rank of windows by 20-140 dBFS (highest first):')
for (l, v) in cols:
    per = U[(l, v)]['per'] if (l, v) in U else [db(s['e140']) for s in usersegs(l, v)]
    o = np.argsort(per)[::-1]
    pr(f'{NAME[l]:6s} {v:8s} | ' + ' > '.join(f'{names[k]}({per[k]:.0f})' for k in o))
pr('gap to P1 uncut, per window (dB, 20-140 dBFS): ')
p1 = [db(s['e140']) for s in usersegs('p1', 'none')]
for v in VARS:
    per = [db(s['e140']) for s in usersegs('b3p2', v)]
    pr(f'v1.6-b {v:8s} | ' + ' '.join(f'{a - b:+6.1f}' for a, b in zip(per, p1)))
pr()
pr('== 4. held-out (12 songs, 30 s excerpt): median over songs ==')
pr('row/variant | 20-140 mean dBFS | 20-140/150-600 dB | primary dB | burst>2x % | 150-600 chg dB | 150-200 chg | 200-300 chg')
for l in ROWS:
    for v in VARS:
        if l != 'b3p2' and v != 'none':
            continue
        lv, r, pm, b2, c1, c2, c3 = [], [], [], [], [], [], []
        for i in HELD:
            s = load(l, i)['var'][v][0]; s0 = load(l, i)['var']['none'][0]; f = s['fft']; f0 = s0['fft']
            lv.append(db(s['e140'])); r.append(db(f['20-140']) - db(mid(f))); pm.append(db(s['p_lo']) - db(s['p_mid'])); b2.append(100 * s['b2'])
            c1.append(db(mid(f)) - db(mid(f0))); c2.append(db(f['150-200']) - db(f0['150-200'])); c3.append(db(f['200-300']) - db(f0['200-300']))
        pr(f'{NAME[l]:6s} {v:8s} | {np.median(lv):7.1f} | {np.median(r):7.1f} | {np.median(pm):7.2f} | {np.median(b2):5.1f} | {np.median(c1):+6.2f} | {np.median(c2):+6.2f} | {np.median(c3):+6.2f}')
pr()
pr('== 5. filter response (analytic; causal) ==')
def sosd(v):
    if v == 'lr4_150':
        s2 = butter(2, 150, 'highpass', fs=FS, output='sos'); return np.vstack([s2, s2])
    n, fc = v[2:].split('_'); return butter(int(n), int(fc), 'highpass', fs=FS, output='sos')
def resp(v, fr):
    s = sosd(v); w, h = sosfreqz(s, worN=np.array(fr, float), fs=FS); return h
def gd(v, f0):
    d = 0.01; h = resp(v, [f0 - d, f0 + d]); ph = np.unwrap(np.angle(h)); return -(ph[1] - ph[0]) / (2 * np.pi * 2 * d) * 1000  # ms
pr('filter | gain dB @150/200/300 | phase deg @150/200/300 | group delay ms @150/200/300')
for v in VARS[1:]:
    h = resp(v, [150, 200, 300])
    pr(f'{v:8s} | ' + '/'.join(f'{20 * np.log10(abs(x)):6.2f}' for x in h) + ' | ' + '/'.join(f'{np.degrees(np.angle(x)):6.1f}' for x in h) + ' | ' + '/'.join(f'{gd(v, f):5.2f}' for f in (150, 200, 300)))
pr('phase deg (and gain dB) at k*f, k=1..4, for f=75,100,125 Hz:')
for v in VARS[1:]:
    for f in (75, 100, 125):
        ks = [k * f for k in (1, 2, 3, 4)]; h = resp(v, ks)
        pr(f'{v:8s} f={f:3d} | ' + ' '.join(f'k{k}({kk}Hz): {np.degrees(np.angle(x)):6.1f}deg {20 * np.log10(abs(x)):6.2f}dB' for k, kk, x in zip((1, 2, 3, 4), ks, h)))
open('/home/ksysh/r3a-dev/plan16/S19/H/tables.txt', 'w').write('\n'.join(OUT) + '\n')
