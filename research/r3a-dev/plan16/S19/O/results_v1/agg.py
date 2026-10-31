"""S19-O aggregation + mechanical 19.2 decision rule -> results.txt / results.json"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from pathlib import Path
O = Path('/home/ksysh/r3a-dev/plan16/S19/O'); RES = O / 'res'
db = lambda x: 10 * np.log10(np.maximum(x, 1e-300))
RATIO = {'f4': -26.186107380800024, 'b3p2': -26.006522010827688, 'b0p0': -22.840447781473937, 'p1': -29.708126533984213}
R = {}
for f in sorted(RES.glob('*.json')):
    j = json.load(open(f)); R[(j['row'], j['song'])] = j
SONGS = list(range(14))
CL = ['noevent', 'event', 'novoice', 'all', 'nc20', 'mid']
EDGES = np.concatenate([[0], np.geomspace(1e-3, 1e3, 241)])
out = {}
lines = []
P = lambda *a: lines.append(' '.join(str(x) for x in a))


def win(row, var, cls):
    return sum(R[(row, i)]['v'][var]['win'][cls] for i in (9, 6))


def songv(row, var, cls, i):
    return R[(row, i)]['v'][var]['song'][cls]


def med_db(row, var, cls, ref_row, ref_var, ref_cls=None):
    ref_cls = ref_cls or cls
    x = []
    for i in SONGS:
        a = songv(row, var, cls, i); b = songv(ref_row, ref_var, ref_cls, i)
        if a > 0 and b > 0:
            x.append(db(a / b))
    return float(np.median(x))


def table(row):
    vs = list(R[(row, 0)]['v'].keys())
    T = {}
    b1all_w = win('b0p0', 'base', 'all')
    for v in vs:
        t = {}
        for c in ('noevent', 'event', 'all', 'nc20', 'mid'):
            t['w_' + c] = float(db(win(row, v, c) / win(row, 'base', c))) if v != 'base' or True else 0
            t['s_' + c] = med_db(row, v, c, row, 'base')
        t['w_all_vs_row1'] = float(db(win(row, v, 'all') / b1all_w))
        t['s_all_vs_row1'] = med_db(row, v, 'all', 'b0p0', 'base')
        t['w_noevent_abs'] = 100 * win(row, v, 'noevent') / b1all_w
        t['w_event_abs'] = 100 * win(row, v, 'event') / b1all_w
        t['w_proj'] = RATIO[row] + t['w_all']
        t['w_proj2'] = RATIO[row] + t['w_all'] - t['w_mid']
        t['w_proj_vs_p1'] = t['w_proj'] - RATIO['p1']
        T[v] = t
    return T


for row in ('f4', 'b3p2'):
    out[row] = table(row)

# ---- base sanity
for row in ('f4', 'b3p2', 'b0p0'):
    w_all = win(row, 'base', 'all')
    P(f'[{row}] base recon windows: noevent {100*win(row,"base","noevent")/w_all:.1f}% event {100*win(row,"base","event")/w_all:.1f}% novoice {100*win(row,"base","novoice")/w_all:.2f}%  | row all vs row1 {db(w_all/win("b0p0","base","all")):+.2f} dB (recon), render {db(win(row,"base","rall")/win("b0p0","base","rall")):+.2f} dB')
P()
hdr = f'{"var":6s} | {"noev":>6s} {"event":>6s} {"all":>6s} {"nc20":>6s} {"mid":>6s} | {"allVsR1":>7s} {"noev%R1":>7s} {"ev%R1":>6s} | {"projRatio":>9s} {"vsP1":>6s} {"proj2":>7s}'
for row in ('f4', 'b3p2'):
    T = out[row]
    P(f'=== {row}: 7 user windows pooled (dB vs own baseline recon; abs % of row1 recon total energy)')
    P(hdr)
    for v, t in T.items():
        P(f'{v:6s} | {t["w_noevent"]:+6.2f} {t["w_event"]:+6.2f} {t["w_all"]:+6.2f} {t["w_nc20"]:+6.2f} {t["w_mid"]:+6.2f} | {t["w_all_vs_row1"]:+7.2f} {t["w_noevent_abs"]:7.1f} {t["w_event_abs"]:6.1f} | {t["w_proj"]:9.2f} {t["w_proj_vs_p1"]:+6.2f} {RATIO[row]+t["w_all"]-t["w_mid"]:7.2f}')
    P()
    P(f'=== {row}: 14-song median of per-song dB (vs own baseline recon; allVsR1 vs b0p0 baseline)')
    P(f'{"var":6s} | {"noev":>6s} {"event":>6s} {"all":>6s} {"nc20":>6s} {"mid":>6s} | {"allVsR1":>7s}')
    for v, t in T.items():
        P(f'{v:6s} | {t["s_noevent"]:+6.2f} {t["s_event"]:+6.2f} {t["s_all"]:+6.2f} {t["s_nc20"]:+6.2f} {t["s_mid"]:+6.2f} | {t["s_all_vs_row1"]:+7.2f}')
    P()

# ---- render vs recon
P('=== render vs reconstruction, 20-150 Hz mean power per sample: 10log10(render/recon) dB (recon 3 kHz block vs render 48 kHz box)')
for row in ('f4', 'b3p2', 'b0p0'):
    s = []
    for nm, rc, cc in (('noevent', 'rnoevent', 'noevent'), ('event', 'revent', 'event'), ('all', 'rall', 'all')):
        w = db((win(row, 'base', rc) / 240) / (win(row, 'base', cc) / 16))
        sm = np.median([db((R[(row, i)]['v']['base']['song'][rc] / 240) / (R[(row, i)]['v']['base']['song'][cc] / 16)) for i in SONGS])
        s.append(f'{nm} win {w:+.2f} song-med {sm:+.2f}')
    P(f'[{row}]', ' | '.join(s))
P()
rr = {}
for row in ('f4', 'b3p2', 'b0p0'):
    for key in ('noevent', 'event'):
        rc = 'r' + key
        rr[(row, key)] = [db((R[(row, i)]['v']['base']['song'][rc] / 240) / (R[(row, i)]['v']['base']['song'][key] / 16)) for i in SONGS]
P('per-song noevent render/recon dB (f4):', ' '.join(f'{x:+.1f}' for x in rr[('f4', 'noevent')]))
P('per-song event   render/recon dB (f4):', ' '.join(f'{x:+.1f}' for x in rr[('f4', 'event')]))
P()

# ---- deviations (f4 real songs, all sustain segments pooled over 14 songs)
def devstat(var, key):
    n = 0; ss = 0.0; h = np.zeros(len(EDGES) - 1)
    for i in SONGS:
        d = R[('f4', i)]['v'][var]['dev'][key]
        n += d['n']; ss += d['ss']; h += np.array(d['h'])
    if n == 0:
        return None
    c = np.cumsum(h) / n
    p95 = EDGES[1:][np.searchsorted(c, 0.95)]
    p50 = EDGES[1:][np.searchsorted(c, 0.5)]
    return dict(n=int(n), rms=float(np.sqrt(ss / n)), p50=float(p50), p95=float(p95))


P('=== real songs (f4), deviation from the original trajectory over all sustain-segment hops, 14 songs pooled: F in cent, a2 amplitude in dB')
P(f'{"var":6s} | {"F rms":>7s} {"F p50":>7s} {"F p95":>7s} | {"a rms":>7s} {"a p50":>7s} {"a p95":>7s}')
dv = {}
for fc in (4, 8, 16, 32):
    for tag in ('a', 'ea', 'b', 'eb', 'c', 'ec'):
        v = f'{tag}{fc}'
        fcnt = devstat(v, 'cent'); acnt = devstat(v, 'db')
        dv[v] = (fcnt, acnt)
        P(f'{v:6s} | ' + (f'{fcnt["rms"]:7.2f} {fcnt["p50"]:7.2f} {fcnt["p95"]:7.2f}' if fcnt else '      -       -       -') + ' | ' + (f'{acnt["rms"]:7.2f} {acnt["p50"]:7.2f} {acnt["p95"]:7.2f}' if acnt else '      -       -       -'))
fcnt = devstat('d1', 'cent'); acnt = devstat('d1', 'db')
P(f'{"d1":6s} | {fcnt["rms"]:7.2f} {fcnt["p50"]:7.2f} {fcnt["p95"]:7.2f} | {acnt["rms"]:7.2f} {acnt["p50"]:7.2f} {acnt["p95"]:7.2f}')
P()
# coverage
tot_on = sum(R[('f4', i)]['onhops'] for i in SONGS); tot_seg = sum(R[('f4', i)]['seghops'] for i in SONGS); nseg = sum(R[('f4', i)]['nseg'] for i in SONGS); dur = sum(R[('f4', i)]['dur'] for i in SONGS)
P(f'coverage f4: sustain segments {nseg} ({nseg/dur:.1f}/s), segment hops {tot_seg} = {100*tot_seg/tot_on:.1f}% of ON hops; crossfade events {sum(R[("f4", i)]["nxf"] for i in SONGS)} ({sum(R[("f4", i)]["nxf"] for i in SONGS)/dur:.1f}/s)')
P()

# ---- decision rule (mechanical), windows pooled primary, songs median alongside
def decide(row):
    T = out[row]; dec = {}
    for scope in ('w', 's'):
        g = lambda v: -T[v][f'{scope}_noevent']                 # gain: reduction of noevent energy, dB
        d1 = g('d1')
        gA = {fc: g(f'a{fc}') for fc in (4, 8, 16, 32)}; gB = {fc: g(f'b{fc}') for fc in (4, 8, 16, 32)}; gC = {fc: g(f'c{fc}') for fc in (4, 8, 16, 32)}
        bestA, bestB = max(gA.values()), max(gB.values())
        if d1 <= 1.0:
            form = 'inspect synthesis path (d <= 1 dB)'
            sel = None
        else:
            if bestA - bestB >= 2:
                form = 'f only (a)'; sel = gA
            elif bestB - bestA >= 2:
                form = 'amplitude only (b)'; sel = gB
            else:
                form = 'both (c)'; sel = gC
        fc = None
        if sel is not None:
            bg = max(sel.values())
            fc = max(f for f, v in sel.items() if v >= bg - 1.0)
        # crossfade
        ev = {T_: -T[f'xf{T_}'][f'{scope}_nc20'] for T_ in (5, 10, 20, 40)}
        best = max(ev.values())                                        # gain = reduction of event-box energy
        Tsel = None
        # lowest event-box energy == highest gain; ties within 0.5 dB -> shorter T
        for T_ in (5, 10, 20, 40):
            if ev[T_] >= best - 0.5:
                Tsel = T_; break
        stop = (gC[4] <= 0.1) and all(v <= 0.1 for v in ev.values())
        dec[scope] = dict(d1_gain=d1, gainA=gA, gainB=gB, gainC=gC, form=form, fc=fc, xf_gain=ev, T=Tsel, stop=stop)
    return dec


D = {row: decide(row) for row in ('f4', 'b3p2')}
for row in ('f4', 'b3p2'):
    for scope, nm in (('w', 'windows pooled (primary)'), ('s', '14-song median')):
        d = D[row][scope]
        P(f'=== decision rule [{row}] {nm}')
        P(f'  (d) 1 Hz noevent gain {d["d1_gain"]:+.2f} dB  (rule: need > 1 dB)')
        P('  gain noevent dB  a:', {k: round(v, 2) for k, v in d['gainA'].items()}, ' b:', {k: round(v, 2) for k, v in d['gainB'].items()}, ' c:', {k: round(v, 2) for k, v in d['gainC'].items()})
        P(f'  -> form: {d["form"]}  fc: {d["fc"]}')
        P('  crossfade event-box (+-20 ms note change) gain dB by T:', {k: round(v, 2) for k, v in d['xf_gain'].items()}, f' -> T {d["T"]} ms; stop condition {d["stop"]}')
    P()
json.dump(dict(table=out, decision=D, dev={k: v for k, v in dv.items()}), open(O / 'results.json', 'w'), indent=1, default=float)
open(O / 'results.txt', 'w').write('\n'.join(lines))
print('\n'.join(lines))
