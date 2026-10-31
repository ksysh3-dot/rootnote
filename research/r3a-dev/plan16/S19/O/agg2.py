"""S19-O aggregation v2 -> results2.txt / results2.json (rule applied on the 12 songs without Apparition/Reminiscence; 7 windows held out)"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from pathlib import Path
from s19o_lib2 import future_needed
O = Path('/home/ksysh/r3a-dev/plan16/S19/O'); RES = O / 'res2'
db = lambda x: 10 * np.log10(np.maximum(x, 1e-300))
RATIO = {'f4': -26.186107380800024, 'b3p2': -26.006522010827688, 'b0p0': -22.840447781473937, 'p1': -29.708126533984213}
R = {}
for f in sorted(RES.glob('*.json')):
    j = json.load(open(f)); R[(j['row'], j['song'])] = j
S12 = [i for i in range(14) if i not in (9, 6)]
lines = []
P = lambda *a: lines.append(' '.join(str(x) for x in a))
COLS = ['noevent', 'ne_join', 'ne_int', 'event', 'all', 'nc20', 'mid']


def win(row, var, cls):
    return sum(R[(row, i)]['v'][var]['win'][cls] for i in (9, 6))


def sg(row, var, cls, i):
    return R[(row, i)]['v'][var]['song'][cls]


def d_win(row, var, cls, rrow, rvar):
    return float(db(win(row, var, cls) / win(rrow, rvar, cls)))


def d_s12(row, var, cls, rrow, rvar):
    x = []
    for i in S12:
        a, b = sg(row, var, cls, i), sg(rrow, rvar, cls, i)
        if a > 0 and b > 0:
            x.append(db(a / b))
    return float(np.median(x))


REF = {'f4': ('f4', 'base'), 'b3p2': ('b3p2', 'base'), 'r1r': ('b0p0', 'base')}
MEAS = {'f4': RATIO['f4'], 'b3p2': RATIO['b3p2'], 'r1r': RATIO['b0p0']}
T = {}
for row in ('f4', 'b3p2', 'r1r'):
    T[row] = {}
    for v in R[(row, 0)]['v']:
        t = {}
        for c in COLS:
            t['w_' + c] = d_win(row, v, c, row, 'base'); t['s_' + c] = d_s12(row, v, c, row, 'base')
        rr, rv = REF[row]
        t['w_all_ref'] = d_win(row, v, 'all', rr, rv); t['w_mid_ref'] = d_win(row, v, 'mid', rr, rv)
        t['s_all_ref'] = d_s12(row, v, 'all', rr, rv)
        t['w_proj'] = MEAS[row] + t['w_all_ref']; t['w_proj2'] = MEAS[row] + t['w_all_ref'] - t['w_mid_ref']
        t['s_proj'] = MEAS[row] + t['s_all_ref']
        T[row][v] = t

P('Reconstruction note: k=2,3 of traced voices, before kOutSos, no percussive/other layer, no fade voices; projected = measured ratio of the reference row + recon dB change vs the reference row baseline (r1r reference = b0p0 recon baseline, measured -22.84; f4 -26.19; b3p2 -26.01; P1 -29.71)')
P()
for row in ('f4', 'r1r', 'b3p2'):
    P(f'=== {row}: dB vs {REF[row][0]} baseline recon.  W = 7 windows pooled (held-out), S = median of the 12 songs w/o Apparition/Reminiscence')
    P(f'{"var":8s} | S: {"noev":>6s} {"join":>6s} {"int":>6s} {"event":>6s} {"all":>6s} {"nc20":>6s} {"mid":>6s} | W: {"noev":>6s} {"join":>6s} {"int":>6s} {"event":>6s} {"all":>6s} {"nc20":>6s} {"mid":>6s} | {"projW":>7s} {"vsP1":>6s} {"proj2W":>7s}')
    for v, t in T[row].items():
        P(f'{v:8s} |    ' + ' '.join(f'{t["s_"+c]:+6.2f}' for c in COLS) + ' |    ' + ' '.join(f'{t["w_"+c]:+6.2f}' for c in COLS) + f' | {t["w_proj"]:7.2f} {t["w_proj"]-RATIO["p1"]:+6.2f} {t["w_proj2"]:7.2f}')
    P()
# r1r base vs b0p0 base
t = T['r1r']['base']
_b = ('r1r', 'base'); _r = ('b0p0', 'base')
P(f'r1r base recon vs b0p0 base recon (same classes): W noevent {d_win(*_b,"noevent",*_r):+.2f} all {d_win(*_b,"all",*_r):+.2f} mid {d_win(*_b,"mid",*_r):+.2f}; S12 noevent {d_s12(*_b,"noevent",*_r):+.2f} all {d_s12(*_b,"all",*_r):+.2f}')
P(f'f4 base share of noevent that is join: W {100*win("f4","base","ne_join")/win("f4","base","noevent"):.1f}%  S12 median {np.median([100*sg("f4","base","ne_join",i)/sg("f4","base","noevent",i) for i in S12]):.1f}%')
P()

# ---- future needed
P('=== future needed by zero-phase (forward-backward 2nd-order Butterworth) smoothing, ms (impulse response above 5% / 1% of its peak)')
for fc in (4, 8, 16, 32):
    fn = future_needed(fc)
    P(f'fc {fc:2d} Hz: {fn[0.05]:6.1f} ms (5%)  {fn[0.01]:6.1f} ms (1%);  hop = 5.33 ms: D=1 -> 5.3 ms, 2 -> 10.7, 3 -> 16.0')
P()

# ---- decision rule
def decide(row, scope):
    g = lambda v: -T[row][v][f'{scope}_noevent']
    out = {}
    d1 = g('d1')
    gA = {fc: g(f'a{fc}') for fc in (4, 8, 16, 32)}; gB = {fc: g(f'b{fc}') for fc in (4, 8, 16, 32)}; gC = {fc: g(f'c{fc}') for fc in (4, 8, 16, 32)}
    if d1 <= 1.0:
        form, sel = 'inspect synthesis path ((d) gain <= 1 dB)', None
    else:
        bA, bB = max(gA.values()), max(gB.values())
        if bA - bB >= 2: form, sel = 'f only (a)', gA
        elif bB - bA >= 2: form, sel = 'amplitude only (b)', gB
        else: form, sel = 'both (c)', gC
    fc = None
    if sel is not None:
        bg = max(sel.values()); fc = max(f for f, v in sel.items() if v >= bg - 1.0)
    ev = {Tm: -T[row][f'xf{Tm}'][f'{scope}_nc20'] for Tm in (5, 10, 20, 40)}
    best = max(ev.values()); Tsel = next(Tm for Tm in (5, 10, 20, 40) if ev[Tm] >= best - 0.5)
    stop = (gC[4] <= 0.1) and all(v <= 0.1 for v in ev.values())
    return dict(d1_gain=d1, gA=gA, gB=gB, gC=gC, form=form, fc=fc, xf_gain=ev, T=Tsel, stop=stop)


D = {}
for row in ('f4', 'r1r', 'b3p2'):
    D[row] = {}
    for scope, nm in (('s', 'S = 12-song median (selection)'), ('w', 'W = 7 windows (held-out check)')):
        d = decide(row, scope); D[row][scope] = d
        P(f'=== rule [{row}] {nm}')
        P(f'  (d) 1 Hz noevent gain {d["d1_gain"]:+.2f} dB (need > 1)')
        P('  noevent gain dB  a:', {k: round(v, 2) for k, v in d['gA'].items()}, ' b:', {k: round(v, 2) for k, v in d['gB'].items()}, ' c:', {k: round(v, 2) for k, v in d['gC'].items()})
        P(f'  -> form: {d["form"]}  fc: {d["fc"]}')
        P('  crossfade nc20 gain dB by T:', {k: round(v, 2) for k, v in d['xf_gain'].items()}, f'-> T {d["T"]} ms; stop {d["stop"]}')
    P()

# ---- realizable (FIR) vs zero-phase: noevent gain and projected for arms b, c (S12 | W)
P('=== realizable symmetric FIR (D hops of future) vs zero-phase vs causal: noevent gain dB (S12 | W) and all-band change (S12)')
for row in ('f4', 'r1r', 'b3p2'):
    P(f'[{row}]')
    for arm in ('b', 'c'):
        for fc in (4, 8, 16, 32):
            cells = []
            for tag, nm in ((f'{arm}{fc}D1', 'D1'), (f'{arm}{fc}D2', 'D2'), (f'{arm}{fc}D3', 'D3'), (f'{arm}{fc}', 'zp'), (f'e{arm}{fc}', 'causal')):
                t = T[row][tag]
                cells.append(f'{nm} {-t["s_noevent"]:+.2f}|{-t["w_noevent"]:+.2f}')
            P(f'  {arm}{fc:<3d}', '  '.join(cells), f'   | all(S12) zp {T[row][f"{arm}{fc}"]["s_all"]:+.2f} D2 {T[row][f"{arm}{fc}D2"]["s_all"]:+.2f}')
P()

# ---- crossfade dips (150-600 Hz)
P('=== (f) crossfade: voice 150-600 Hz level minimum inside the crossfade / original (dB), all events of the 14 songs pooled: median / p10 / n')
for row in ('f4', 'r1r', 'b3p2'):
    for Tm in (5, 10, 20, 40):
        x = np.concatenate([np.array(R[(row, i)]['v'][f'xf{Tm}']['dips']) for i in range(14)])
        P(f'  {row:5s} T {Tm:2d} ms: median {np.median(x):+.2f}  p10 {np.percentile(x,10):+.2f}  n {len(x)}')
P()

# ---- r1r phase error
EDGES = np.concatenate([[0], np.geomspace(1e-3, 1e3, 241)])
def hq(key, q):
    n = sum(R[('r1r', i)]['phase_err'][key]['n'] for i in range(14)); h = sum(np.array(R[('r1r', i)]['phase_err'][key]['h']) for i in range(14))
    c = np.cumsum(h) / n
    return [EDGES[1:][np.searchsorted(c, qq)] for qq in q], n
for key in ('all', 'first30'):
    (m, p90), n = hq(key, (0.5, 0.9))
    P(f'r1r phase error vs b0p0 theta_hat ({key}, ON hops, n {n}): fundamental median {m:.3f} rad ({np.degrees(m):.1f} deg), p90 {p90:.3f} rad ({np.degrees(p90):.0f} deg); k=2 doubles it')
P()

# ---- deviations on real songs f4
def devstat(var, key):
    n = 0; ss = 0.0; h = np.zeros(len(EDGES) - 1)
    for i in range(14):
        d = R[('f4', i)]['v'][var]['dev'][key]; n += d['n']; ss += d['ss']; h += np.array(d['h'])
    if n == 0: return None
    c = np.cumsum(h) / n
    return n, np.sqrt(ss / n), EDGES[1:][np.searchsorted(c, 0.5)], EDGES[1:][np.searchsorted(c, 0.95)]
P('=== f4 real songs: deviation from original trajectory in sustain segments (14 songs): F cent rms/p50/p95 | a2 dB rms/p50/p95')
for fc in (4, 8, 16, 32):
    for tag in ('a', 'ea', 'b', 'eb', 'b%dD2' % fc, 'b%dD1' % fc):
        v = tag + str(fc) if tag in ('a', 'ea', 'b', 'eb') else tag
        f_ = devstat(v, 'cent'); a_ = devstat(v, 'db')
        P(f'  {v:8s}', (f'{f_[1]:6.2f} {f_[2]:6.2f} {f_[3]:6.2f}' if f_ else '   -'), '|', (f'{a_[1]:6.2f} {a_[2]:6.2f} {a_[3]:6.2f}' if a_ else '   -'))
P()
json.dump(dict(T=T, D=D), open(O / 'results2.json', 'w'), indent=1, default=float)
open(O / 'results2.txt', 'w').write('\n'.join(lines))
print('\n'.join(lines))
