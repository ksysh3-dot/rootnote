"""tables + mechanical 16.7 decision.  python s_report.py > s_report.txt"""
import json
import numpy as np
H = '/home/ksysh/r3a-dev/plan16/'
A = json.load(open(H + 'A/ladder_raw.json'))['res']
S = json.load(open(H + 'S/s_raw.json'))
Sres, bnd, s1info = S['res'], S['bnd'], S['s1info']
SONGS = [k for k in A if k.startswith('Track')]
EVAL = ['Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
res = {k: dict(A[k]) for k in A}
SR = ['S1', 'S2-LA', 'S2-core', 'S2b-LA', 'S2b-core']
for k in res:
    for rn in SR:
        res[k][rn] = Sres[k].get(rn)
ROWS = ['P1', 'R0', 'R1', 'R2', 'R3', 'R2s'] + SR
db = lambda x: 10 * np.log10(max(x, 1e-300))
print('# S report (16.7)  consistency of recomputed R2/R3 vs A ladder_raw (max rel diff):', {k: f'{v:.1e}' for k, v in S['check'].items()})


def pooled(rn, tn, f):
    return sum(res[k][rn][tn][f] for k in SONGS if res[k].get(rn))


E3 = {tn: pooled('R3', tn, 'E_right') for tn in ('v6b', 'strict')}
v5 = {rn: (res['t60_36_48'][rn]['v5a'] if res['t60_36_48'].get(rn) else None) for rn in ROWS}
pre = {}
for rn in ROWS:
    g = []; l = []
    for k in SONGS:
        if res[k].get(rn):
            g += res[k][rn]['pre']['gap']; l += res[k][rn]['pre']['leg']
    pre[rn] = (np.array(g), np.array(l))
table = {}
for tn in ('v6b', 'strict'):
    for rn in ROWS:
        ks = [k for k in SONGS if res[k].get(rn)]
        Er = sum(res[k][rn][tn]['E_right'] for k in ks); Ew = sum(res[k][rn][tn]['E_wrong'] for k in ks)
        g2 = E3[tn] / Er if Er > 0 else float('nan')
        w = sum(res[k][rn][tn]['v6b_wrong'] for k in ks); r_ = sum(res[k][rn][tn]['v6b_right'] for k in ks)
        e5 = [k for k in EVAL if k in ks]; w5 = sum(res[k][rn][tn]['v6b_wrong'] for k in e5); r5 = sum(res[k][rn][tn]['v6b_right'] for k in e5)
        g, l = pre[rn]
        table[(tn, rn)] = dict(right_db=db(Er / E3[tn]), wf=Ew / E3[tn], wm=Ew * g2 / E3[tn], gdb=db(g2) if np.isfinite(g2) else float('nan'),
                               v5a=None if v5[rn] is None else v5[rn]['frac'], pre=float(np.median(g)) if len(g) else float('nan'), pre_p90=float(np.percentile(g, 90)) if len(g) else float('nan'),
                               v6=100 * w / max(w + r_, 1e-30), v6e5=100 * w5 / max(w5 + r5, 1e-30), n=len(g))
v5R3 = v5['R3']['frac']
out = {}
for tn in ('v6b', 'strict'):
    print(f"\n## energies, truth = {tn}")
    print('row     | right dB vs R3 (F) | wrong/R3right F | wrong/R3right M (gain dB) | V5a % (new crit: minus R3 = %p) | pre-echo med dB (N=57; p90) | V6b wrong share % (eval5)')
    for rn in ROWS:
        t = table[(tn, rn)]
        v5s = '-' if t['v5a'] is None else f"{100 * t['v5a']:.1f} ({100 * (t['v5a'] - v5R3):+.1f} %p)"
        print(f"{rn:8s}| {t['right_db']:+7.2f} | {t['wf']:.4f} | {t['wm']:.4f} ({t['gdb']:+.2f} dB) | {v5s} | {t['pre']:+.2f} (p90 {t['pre_p90']:+.1f}) | {t['v6']:.2f} ({t['v6e5']:.2f})")
    # pass conditions with new V5a criterion
    for var in ('M', 'F'):
        p1 = table[(tn, 'P1')]['wm' if var == 'M' else 'wf']
        print(f"  variant {var}: P1 ref {p1:.4f}, limit {0.5 * p1:.4f}")
        for rn in ['R2', 'R1'] + SR:
            t = table[(tn, rn)]
            c1 = t['wm' if var == 'M' else 'wf'] <= 0.5 * p1
            c2 = True if var == 'M' else t['right_db'] >= -1
            c3 = t['v5a'] is not None and (t['v5a'] - v5R3) <= 0.02
            c4 = t['pre'] <= 1.0
            print(f"    {rn:8s} c1 {'Y' if c1 else 'n'} c2 {'Y' if c2 else 'n'} c3(V5a-R3<=2%p) {'Y' if c3 else 'n'} c4 {'Y' if c4 else 'n'} -> {'PASS' if all([c1, c2, c3, c4]) else 'fail'}")
    # 16.7 shares
    for var, key in (('F', 'wf'), ('M', 'wm')):
        r1, r2 = table[(tn, 'R1')][key], table[(tn, 'R2')][key]
        den = np.log(r1 / r2)
        sh = {rn: np.log(table[(tn, rn)][key] / r2) / den for rn in ('S1', 'S2-LA', 'S2-core', 'S2b-LA', 'S2b-core')}
        print(f"  shares ({var}): R1/R2 = {r1 / r2:.1f}  S1/R2 = {table[(tn, 'S1')][key] / r2:.2f} S2-LA/R2 = {table[(tn, 'S2-LA')][key] / r2:.2f} S2-core/R2 = {table[(tn, 'S2-core')][key] / r2:.2f}")
        print(f"     share_cand (S1) = {sh['S1']:.3f}   share_seg S2-core = {sh['S2-core']:.3f}   S2-LA = {sh['S2-LA']:.3f}   [info: S2b-LA {sh['S2b-LA']:.3f}, S2b-core {sh['S2b-core']:.3f}]")
        out[(tn, var)] = sh

# missing shares
print('\n## S1 missing (candidate absent), 10 songs')
segs_n = sum(len(s1info[k]) for k in SONGS)
miss = sum(i['missing'] for k in SONGS for i in s1info[k])
lenient = sum(1 for k in SONGS for i in s1info[k] if i['missing'] and i['lenient'])
tm = sum(Sres[k]['s1_time']['miss'] for k in SONGS); tt = sum(Sres[k]['s1_time']['tot'] for k in SONGS)
print(f"segment-level (HEADLINE): {miss}/{segs_n} = {100 * miss / segs_n:.1f} %   (of those missing, a 0.5x/2x/3x candidate exists: {lenient})")
print(f"time-weighted (segment time t>0.5 s without S1 layer): {tm:.1f}/{tt:.1f} s = {100 * tm / tt:.1f} %")
print('per song missing/segments:', {k[-2:]: f"{sum(i['missing'] for i in s1info[k])}/{len(s1info[k])}" for k in SONGS if s1info[k]})
dl = np.array([i['first_delay'] * 1e3 for k in SONGS for i in s1info[k] if not i['missing']])
print('S1 candidate first in-tolerance hop minus MIDI start (ms), covered segments: median/p10/p90', [round(float(np.percentile(dl, q)), 1) for q in (50, 10, 90)], 'N', len(dl))
for f_ in (0.10,):
    print(f"override threshold {100 * f_:.0f} %: segment-level {'EXCEEDS' if miss / segs_n > f_ else 'below'}; time-weighted {'EXCEEDS' if tm / tt > f_ else 'below'}")

# S2 association counts
print('\n## S2 association counts (pooled over the 10 songs)')
for tag in ('S2-LA', 'S2-core', 'S2b-LA', 'S2b-core'):
    c = {f: sum(bnd[k][tag + '_cnt'][f] for k in SONGS) for f in ('n_real', 'n_silence', 'n_incompat', 'n_kept', 'seg_missing')}
    print(tag, c, f"(truth segments {segs_n}; segments without a kept interval {c['seg_missing']} = {100 * c['seg_missing'] / segs_n:.1f} %)")

# boundary error distributions
def q(a):
    a = np.array([x for x in a if x is not None], float)
    return None if not len(a) else dict(med=round(float(np.median(a)), 1), p10=round(float(np.percentile(a, 10)), 1), p90=round(float(np.percentile(a, 90)), 1), n=int(len(a)))


print('\n## boundary errors (ms, signed: real - reference; median / p10 / p90 / N)')
for tag in ('S2-LA', 'S2-core', 'S2b-LA', 'S2b-core'):
    agg = {f: [] for f in ('d_on_midi', 'd_off_midi', 'd_on_stem', 'd_off_stem', 'single', 'd_on_nearest', 'd_on_nearest_stem', 'd_off_nearest', 'd_off_nearest_stem')}
    cnt = dict(n_att=0, n_att_noonset=0, n_seg=0, n_seg_nooff=0)
    for k in SONGS:
        b = bnd[k][tag]
        if not b:
            continue
        for f in agg:
            agg[f] += b[f]
        for f in cnt:
            cnt[f] += b[f]
    sg = np.array(agg['single'], bool)
    sel = lambda f, m: [x for x, mm in zip(agg[f], m) if mm]
    print(f"\n{tag}  (kept intervals {len(sg)}, single-note >=80 % occupancy: {int(sg.sum())})")
    for f in ('d_on_midi', 'd_off_midi', 'd_on_stem', 'd_off_stem'):
        print(f"  {f:10s} all: {q(agg[f])}   single-note: {q(sel(f, sg))}")
    print(f"  nearest real onset vs attack segments (+-300 ms): vs MIDI {q(agg['d_on_nearest'])}  vs stem {q(agg['d_on_nearest_stem'])};  no onset within 300 ms: {cnt['n_att_noonset']}/{cnt['n_att']} = {100 * cnt['n_att_noonset'] / max(cnt['n_att'], 1):.1f} %")
    print(f"  nearest real offset vs all segments (+-300 ms): vs MIDI {q(agg['d_off_nearest'])}  vs stem {q(agg['d_off_nearest_stem'])};  no offset within 300 ms: {cnt['n_seg_nooff']}/{cnt['n_seg']} = {100 * cnt['n_seg_nooff'] / max(cnt['n_seg'], 1):.1f} %")
print('\nS1 / R2: MIDI boundary used (error 0 by construction); vs stem activity = A report (onset median +12.3 ms, p10 +0.2, p90 +42.5; offset median +20.2, p10 -0.1, p90 +55.3).')

# per-song
print('\n## per song (truth v6b): right dB vs R3 / wrong/R3right / V6b share %')
for rn in ['R2', 'R1'] + SR:
    cells = []
    for k in SONGS:
        t = res[k].get(rn); r3 = res[k]['R3']['v6b']['E_right']
        if not t or r3 <= 0:
            cells.append(f"{k[-2:]}: n/a"); continue
        sh = 100 * t['v6b']['v6b_wrong'] / max(t['v6b']['v6b_wrong'] + t['v6b']['v6b_right'], 1e-30)
        cells.append(f"{k[-2:]}: {db(t['v6b']['E_right'] / r3):+.1f}/{t['v6b']['E_wrong'] / r3:.3f}/{sh:.1f}")
    print(rn.ljust(8), ' | '.join(cells))
print('songs without bass MIDI (absolute wrong energy):')
for k in SONGS:
    if not res[k]['n_segments']:
        print(' ', k, {rn: round(res[k][rn]['v6b']['E_wrong'], 6) for rn in SR if res[k].get(rn)})

# decision
print('\n## DECISION (16.7, mechanical)')
for tn in ('v6b', 'strict'):
    for var in ('F', 'M'):
        sh = out[(tn, var)]
        sc, ss = sh['S1'], sh['S2-core']
        big = 'candidate' if sc > ss else 'segmentation'
        both = sc >= 0.5 and ss >= 0.5
        override = miss / segs_n > 0.10
        print(f"truth {tn}, gain {var}: share_cand {sc:.3f}, share_seg(S2-core) {ss:.3f} -> larger = {big}; both >= 0.5: {both}; S1 missing {100 * miss / segs_n:.1f} % (> 10 %: {override}; time-weighted {100 * tm / tt:.1f} %)")
