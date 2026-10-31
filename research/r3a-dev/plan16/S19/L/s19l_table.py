"""S19-L tables from res/*.json (numbers only)."""
import json, sys
import numpy as np
from pathlib import Path
R = Path('/home/ksysh/r3a-dev/plan16/S19/L/res')
ROWS = ['inp', 'p1', 'v15', 'b0p0', 'b3p2', 'f4']
NAME = {'inp': 'input', 'p1': 'P1', 'v15': 'v1.5', 'b0p0': 'v1.6-a', 'b3p2': 'v1.6-b', 'f4': 'f4'}
USER = (6, 9); HELD = [i for i in range(14) if i not in USER]
db = lambda p: 10 * np.log10(max(p, 1e-30))
BN = ['20-60', '60-100', '100-130', '130-150', '150-200', '200-300', '300-600']
OUT = []
def pr(s=''):
    print(s); OUT.append(s)

def load(l, i):
    return json.load(open(R / f'{l}_s{i:02d}.json'))
def usersegs(l):
    # order: rem windows then app windows -> sort by song,t0 in P order (app first as primary)
    segs = []
    for i in (9, 6):
        for s in load(l, i)['segs']:
            s = dict(s); s['song'] = i; segs.append(s)
    return segs
def bands_db(f):
    mid = f['150-200'] + f['200-300'] + f['300-600']
    return [db(f[b] / mid) for b in BN], db(f['20-140'] / mid), db(f['150-260'] / mid)
def boxes(l, i, k):
    z = np.load(R / f'{l}_s{i:02d}_boxes.npz'); return z[f'eb{k}'], z[f'rm{k}']
def burst(eb, rm, thr):
    return float(eb[eb > thr * rm].sum() / eb.sum())
def boxstats(eb, rm):
    d = 10 * np.log10(eb + 1e-30)
    return dict(med=float(np.median(d)), p95=float(np.percentile(d, 95)), b2=burst(eb, rm, 2), b4=burst(eb, rm, 4), steady=float(np.minimum(eb, rm).sum() / eb.sum()))

res = {}
pr('== 1/2. primary ratio, leakage share, pooled over the 7 windows ==')
pr('row | primary 20-150/150-600 dB (pooled) | per window | lo dBFS | leak(above-150 part) % | below-150 part % | cross % | true low-band (below part through band) dBFS | leak-part dBFS')
for l in ROWS:
    sg = usersegs(l)
    lo = sum(s['p_lo'] for s in sg); mid = sum(s['p_mid'] for s in sg); ab = sum(s['e_ab'] for s in sg); be = sum(s['e_be'] for s in sg)
    pw = [db(s['p_lo']) - db(s['p_mid']) for s in sg]
    lw = [100 * s['e_ab'] / s['p_lo'] for s in sg]
    res[l] = dict(ratio=db(lo) - db(mid), lo=db(lo / 7), ab=db(ab / 7), be=db(be / 7), leak=100 * ab / lo, below=100 * be / lo, per=pw, perleak=lw, mid=db(mid / 7), lo_abs=lo / 7)
    r = res[l]
    pr(f'{NAME[l]:7s} | {r["ratio"]:7.2f} | ' + ' '.join(f'{x:6.1f}' for x in pw) + f' | {r["lo"]:6.1f} | {r["leak"]:5.1f} | {r["below"]:5.1f} | {100 - r["leak"] - r["below"]:6.1f} | {r["be"]:6.1f} | {r["ab"]:6.1f}')
pr('per-window leak share %: ' + ' ; '.join(f'{NAME[l]} ' + ' '.join(f'{x:4.0f}' for x in res[l]['perleak']) for l in ROWS))
pr('windows order: ' + ' '.join(f'{"app" if s["song"] == 9 else "rem"}{s["t0"]:g}' for s in usersegs('p1')))
pr()
pr('== 3. leakage-free spectrum (Hann FFT of the whole 2 s window, pooled energies), dB re 150-600 ==')
pr('row | ' + ' | '.join(BN) + ' | 20-140/150-600 | 150-260 re 150-600 | 150-600 dBFS-rel input (dB)')
fp = {}
for l in ROWS:
    sg = usersegs(l)
    f = {k: sum(s['fft'][k] for s in sg) for k in sg[0]['fft']}
    fp[l] = f
    b, r, r260 = bands_db(f)
    mid = f['150-200'] + f['200-300'] + f['300-600']
    midin = sum(sum(s['fft'][k] for k in ('150-200', '200-300', '300-600')) for s in usersegs('inp'))
    res[l].update(bands=b, r140=r, r260=r260, mid_rel_in=db(mid / midin))
    pr(f'{NAME[l]:7s} | ' + ' | '.join(f'{x:6.1f}' for x in b) + f' | {r:6.1f} | {r260:6.1f} | {db(mid / midin):6.1f}')
pr('difference to P1 (dB) of absolute band energies (not re 150-600), i.e. level of band in row minus P1:')
for l in ROWS[2:]:
    pr(f'{NAME[l]:7s} | ' + ' | '.join(f'{db(fp[l][b] ) - db(fp["p1"][b]):+6.1f}' for b in BN) + f' | 20-140 {db(fp[l]["20-140"]) - db(fp["p1"]["20-140"]):+6.1f} | 150-260 {db(fp[l]["150-260"]) - db(fp["p1"]["150-260"]):+6.1f} | 150-600 {db(sum(fp[l][k] for k in ("150-200","200-300","300-600"))) - db(sum(fp["p1"][k] for k in ("150-200","200-300","300-600"))):+6.1f}')
pr('per-window 20-140/150-600 dB: ')
for l in ROWS:
    pr(f'{NAME[l]:7s} | ' + ' '.join(f'{bands_db(s["fft"])[1]:6.1f}' for s in usersegs(l)))
pr()
pr('== 4. 20-140 Hz steady vs dynamic (5 ms boxes, linear-phase 20-140, pooled boxes of 7 windows) ==')
pr('row | median box dBFS | p95 box dBFS | burst share >2x run-median (energy) % | >4x % | steady share % | per-window median dB')
for l in ROWS:
    ebs, rms, pm = [], [], []
    for i in (9, 6):
        z = load(l, i)
        for k, _ in enumerate(z['segs']):
            e, r = boxes(l, i, k); ebs.append(e); rms.append(r); pm.append(10 * np.log10(np.median(e) + 1e-30))
    s = boxstats(np.concatenate(ebs), np.concatenate(rms)); res[l]['box'] = s
    pr(f'{NAME[l]:7s} | {s["med"]:6.1f} | {s["p95"]:6.1f} | {100 * s["b2"]:5.1f} | {100 * s["b4"]:5.1f} | {100 * s["steady"]:5.1f} | ' + ' '.join(f'{x:6.1f}' for x in pm))
pr()
pr('== 5. 150-260 Hz (k=2 region of low notes): level re 150-600 (item 3) and 2-12 Hz envelope modulation excess (layer - input), 7 windows ==')
pr('row | 150-260 re 150-600 dB | mean M_layer (dB rms) | mean M_input | mean excess | per-window excess')
Mi_all = [s['mod']['Mi'][0] for s in usersegs('inp')]
for l in ROWS:
    sg = usersegs(l)
    Ml = [s['mod']['Ml'][0] for s in sg]; Mi = [s['mod']['Mi'][0] for s in sg]
    ex = np.array(Ml) - np.array(Mi); res[l]['mod'] = float(np.mean(ex))
    pr(f'{NAME[l]:7s} | {res[l]["r260"]:6.1f} | {np.mean(Ml):5.2f} | {np.mean(Mi):5.2f} | {np.mean(ex):+5.2f} | ' + ' '.join(f'{x:+5.2f}' for x in ex))
pr()
pr('== 6. held-out: 12 other songs, 30 s excerpt from 60 s; median over songs ==')
pr('row | leak share % (med) | primary-band 20-150/150-600 dB (med) | 20-140/150-600 dB (med) | 150-260 re 150-600 dB (med) | mod excess 150-260 (med of per-song medians) | burst>2x % 20-140 (med) | median box dBFS 20-140 (med)')
H = {}
for l in ROWS:
    lk, pm, r140, r260, mo, bs, mb = [], [], [], [], [], [], []
    for i in HELD:
        z = load(l, i)
        if not z['segs']:
            continue
        s = z['segs'][0]
        lk.append(100 * s['e_ab'] / s['p_lo']); pm.append(db(s['p_lo']) - db(s['p_mid']))
        b, r, rr = bands_db(s['fft']); r140.append(r); r260.append(rr)
        e, rm = boxes(l, i, 0); st = boxstats(e, rm); bs.append(100 * st['b2']); mb.append(st['med'])
    H[l] = dict(leak=lk, pm=pm, r140=r140, r260=r260)
    pr(f'{NAME[l]:7s} | {np.median(lk):5.1f} | {np.median(pm):6.1f} | {np.median(r140):6.1f} | {np.median(r260):6.1f} | ', )
    OUT.pop();
    # modulation excess with v15 eligibility
    ex = []
    for i in HELD:
        s = load(l, i)['segs'][0]; s15 = load('v15', i)['segs'][0]; si = load('inp', i)['segs'][0]
        lev = np.array(s15['mod']['levm']); ok = lev > -70
        t = np.array(s['mod']['t']); ok &= (t - s['t0']) >= 0
        d = np.array(s['mod']['Ml']) - np.array(si['mod']['Mi'])
        if ok.sum() >= 3:
            ex.append(float(np.median(d[ok])))
    pr(f'{NAME[l]:7s} | {np.median(lk):5.1f} | {np.median(pm):6.1f} | {np.median(r140):6.1f} | {np.median(r260):6.1f} | {np.median(ex):+5.2f} (n={len(ex)}) | {np.median(bs):5.1f} | {np.median(mb):6.1f}')
pr('held-out per-song 20-140/150-600 dB (songs ' + ','.join(map(str, HELD)) + '):')
for l in ROWS:
    pr(f'{NAME[l]:7s} | ' + ' '.join(f'{x:6.1f}' for x in H[l]['r140']))
pr('held-out per-song leak share %:')
for l in ROWS:
    pr(f'{NAME[l]:7s} | ' + ' '.join(f'{x:5.0f}' for x in H[l]['leak']))
pr('held-out per-song primary ratio dB:')
for l in ROWS:
    pr(f'{NAME[l]:7s} | ' + ' '.join(f'{x:6.1f}' for x in H[l]['pm']))
pr()
pr('== gap to P1 (user windows, pooled) ==')
pr('row | primary gap dB (row - P1) | true low-band (below part through band) gap dB | leak-part gap dB | 20-140 abs gap dB (FFT) | 20-140/150-600 gap dB | 150-260 re 150-600 gap')
for l in ROWS[2:]:
    r, q = res[l], res['p1']
    pr(f'{NAME[l]:7s} | {r["ratio"] - q["ratio"]:+6.2f} | {r["be"] - q["be"]:+6.1f} | {r["ab"] - q["ab"]:+6.1f} | {db(fp[l]["20-140"]) - db(fp["p1"]["20-140"]):+6.1f} | {r["r140"] - q["r140"]:+6.1f} | {r["r260"] - q["r260"]:+6.1f}')
open('/home/ksysh/r3a-dev/plan16/S19/L/tables.txt', 'w').write('\n'.join(OUT) + '\n')
