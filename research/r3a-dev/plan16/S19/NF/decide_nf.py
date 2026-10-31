"""S19-NF mechanical decision (CHOICES.md). References (p1, b0p0 = v1.6-a, b3p2 = v1.6-b at nFuture 24) are read from plan16/A5P; the new rows from this directory.
Writes decide_nf.log via stdout redirection by the caller."""
import json, sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/NF')
from pathlib import Path
import numpy as np
import a5prows as AR
A = Path('/home/ksysh/r3a-dev/plan16/A5P'); N = Path('/home/ksysh/r3a-dev/plan16/S19/NF')
NEW = AR.NEW; B = 'b3p2'; AL = 'b0p0'


def suite(d, l):
    j = json.loads((d / 'suite' / l / 'results.json').read_text())
    return {c['id']: c['value'] for c in j['checks']}, {c['id']: c.get('p1') for c in j['checks']}


SV = {l: suite(N, l)[0] for l in NEW}
SV[B], P1 = suite(A, B)
SV[AL] = suite(A, AL)[0]
BU_A = json.load(open(A / 'burst_p.json')); BU_N = json.load(open(N / 'burst_p.json'))
BU = {l: BU_N[f'{l}|4.73']['burst_R1'] for l in NEW}
BU[B] = BU_A[f'{B}|4.73']['burst_R1']; BU[AL] = BU_A[f'{AL}|4.73']['burst_R1']; BU['p1'] = BU_A['p1|4.73']['burst_R1']
PRA = json.load(open(A / 'primary_summary.json')); PRN = json.load(open(N / 'primary_summary.json'))
PR = {l: PRN[l] for l in NEW}
for l in ('p1', AL, B):
    PR[l] = PRA[l]
FR = {l: json.load(open(N / f'right_{l}.json'))['summary']['all10']['right_vs_R3_dB_sa'] for l in NEW}
for l in (AL, B):
    FR[l] = json.load(open(A / f'right_{l}.json'))['summary']['all10']['right_vs_R3_dB_sa']
S12 = {}
for l in ['p1', AL, B] + NEW:
    S12[l] = float(np.median([v['ratio_db'] for v in json.load(open(N / f'songs12_{l}.json')).values()]))

# guards: (name, value getter(row)->float, P1 value, margin, higher_is_worse)
GU = []


def add(name, get, p1, margin, hw=True):
    GU.append((name, get, p1, margin, hw))


add('V3a peak (ms)', lambda l: SV[l]['V3a'], P1['V3a'], 2)
add('V3h.bare.rise90 (ms)', lambda l: SV[l]['V3h.bare.rise90'], P1['V3h.bare.rise90'], 2)
add('V3h.25.rise90 (ms)', lambda l: SV[l]['V3h.25.rise90'], P1['V3h.25.rise90'], 2)
add('V3b (dB)', lambda l: SV[l]['V3b'], P1['V3b'], 1)
add('V3i.trans (/s)', lambda l: SV[l]['V3i.trans'], P1['V3i.trans'], 0.5)
for k in ('V4b.bass+pink', 'V4b.bass+kick+pink'):
    add(k + ' (%p)', (lambda kk: lambda l: 100 * SV[l][kk])(k), 100 * P1[k], 1)
add('LOGOFF 4.73 R1 (dB)', lambda l: BU[l], BU['p1'], 1)
for f_ in ('35', '45'):
    add(f'V3g.{f_}.noREL (hops)', (lambda kk: lambda l: SV[l][kk])(f'V3g.{f_}.noREL'), P1[f'V3g.{f_}.noREL'], 5)
add('body 150-600 Hz level (dB)', lambda l: PR[l]['mid'], PR['p1']['mid'], 2, hw=False)
add('right layer F (dB)', lambda l: FR[l], None, 0.5, hw=False)
add('V3d pre-echo (dB)', lambda l: SV[l]['V3d'], P1['V3d'], 0.5)

print('=== MAIN (pooled 7-window 20-150/150-600 ratio, dB, lower = better) ===')
print(f'{"row":14s} {"nF":>3s} {"ratio":>8s} {"gain vs v1.6-b":>14s} {"windows better":>14s} {"12-song med":>11s}  per-window')
for l in ['p1', AL, B] + NEW:
    nimp = sum(1 for a, c in zip(PR[l]['per_window'], PR[B]['per_window']) if a < c)
    print(f'{AR.NAMES[l]:14s} {AR.NFUT.get(l, "-")!s:>3s} {PR[l]["ratio"]:8.2f} {PR[B]["ratio"] - PR[l]["ratio"]:+14.2f} {nimp:14d} {S12[l]:11.2f}  ' + ' '.join(f'{x:6.1f}' for x in PR[l]['per_window']))

res = {}
for l in NEW:
    gain = PR[B]['ratio'] - PR[l]['ratio']
    nimp = sum(1 for a, c in zip(PR[l]['per_window'], PR[B]['per_window']) if a < c)
    main = gain >= 2.0 and nimp >= 5 and S12[l] <= S12[B]
    fails = []; rows = []
    for name, get, p1, m, hw in GU:
        v, vb = get(l), get(B)
        if hw:
            worse_b = v > vb + m; worse_p1 = True if p1 is None else v > p1
            d = v - vb
        else:
            worse_b = v < vb - m; worse_p1 = True if p1 is None else v < p1
            d = v - vb
        f = worse_b and worse_p1
        rows.append((name, v, vb, p1, d, m, worse_b, worse_p1, f))
        if f:
            fails.append(name)
    res[l] = dict(main=main, gain=gain, nimp=nimp, fails=fails, rows=rows)

print('\n=== GUARDS (value | v1.6-b | P1 | delta vs v1.6-b | margin | worse_b worse_P1 -> FAIL) ===')
for l in NEW:
    print(f'\n{AR.NAMES[l]} [{l}]')
    for name, v, vb, p1, d, m, wb, wp, f in res[l]['rows']:
        print(f'   {name:30s} {v:9.3f} | {vb:9.3f} | {("%9.3f" % p1) if p1 is not None else "      n/a"} | {d:+8.3f} | {m:4.1f} | {int(wb)} {int(wp)} {"FAIL" if f else "ok"}')
print('\n=== DECISION ===')
qual = []
for l in NEW:
    r = res[l]
    ok = r['main'] and not r['fails']
    print(f'{AR.NAMES[l]:14s} main={r["main"]} (gain {r["gain"]:+.2f}, windows {r["nimp"]}/7, 12-song {S12[l]:.2f} vs {S12[B]:.2f}) guard fails={r["fails"]} -> {"QUALIFIES" if ok else "no"}')
    if ok:
        qual.append(l)
if qual:
    best = min(PR[l]['ratio'] for l in qual)
    ties = [l for l in qual if PR[l]['ratio'] - best <= 0.5]
    pick = min(ties, key=lambda l: (AR.NFUT[l], 0 if l.startswith('nfb') else 1))
    print('ADOPT:', AR.NAMES[pick], pick, 'nFuture', AR.NFUT[pick])
else:
    print('ADOPT: none (stay v1.6-b nFuture 24)')
