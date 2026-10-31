"""Q7: voice-management candidates evaluated OFFLINE by post-hoc reweighting of the existing core-A traces: weight (A c sigma)^2 * q^2,
q a continuous one-pole-smoothed weight per voice (state initialised to 1 at birth). Same V6b labels as q1.py."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
from q1 import since

DT = 16 / 3000.0
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def al(tau_ms):
    return 1.0 - np.exp(-DT / (tau_ms / 1000.0))


def sstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1); return t * t * (3 - 2 * t)


def onepole(target, a_up, a_dn, q0=1.0):
    q = np.empty(len(target)); s = q0
    for i, t in enumerate(target):
        s += (a_up if t > s else a_dn) * (t - s)
        q[i] = s
    return q


# ---------------------------------------------------------------------------------------------- data
def build(name):
    rf = C.ref(name)
    tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22)
    H = len(tc); st = d['state']
    w = np.where(st > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
    wrong = np.zeros((H, 8), bool); bmatch = np.zeros((H, 8), int)      # bmatch: 0 none, 1..4 matched bass note at x0.5, x1, x2, x3
    lab = np.zeros((H, 8), bool)
    for h in range(H):
        if tc[h] <= 0.5:
            continue
        js = np.flatnonzero((w[h] > 0) & (st[h] > 0))
        if not len(js):
            continue
        fn = C.targets_at(rf, tc[h], 'a'); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
        m = (rf['ss'] <= tc[h]) & (tc[h] < rf['es'])
        fb = 440 * 2 ** ((rf['ps'][m] + rf['tp'] - 69) / 12)
        tb = np.outer(fb, [.5, 1, 2, 3]) if len(fb) else np.zeros((0, 4))
        for j in js:
            lab[h, j] = True
            f = d['fosc'][h][j]
            wrong[h, j] = (not len(tgt)) or np.min(C.cents(f, tgt)) > 50
            if len(tb):
                cc = C.cents(f, tb)           # (nb, 4)
                if cc.min() <= 50:
                    bmatch[h, j] = int(np.argmin(cc.min(axis=0))) + 1
    # coasting voices within resolution of a tracked ON voice
    neartr = np.zeros((H, 8), bool)
    for h in range(H):
        trk = [j for j in range(8) if st[h][j] == 2 and d['coast'][h][j] == 0]
        if not trk:
            continue
        ft = d['fosc'][h][trk]
        for j in range(8):
            if st[h][j] > 0 and d['coast'][h][j] > 0:
                f = d['fosc'][h][j]; neartr[h, j] = np.any(np.abs(ft - f) <= max(6.0, .06 * f))
    onmask = (tc[:, None] >= 0) & (since(rf['ss'], tc) < 0.2)[:, None] & np.ones((1, 8), bool)
    return dict(rf=rf, d=d, raw=raw, tc=tc, st=st, w=w, wrong=wrong, lab=lab, neartr=neartr, bmatch=bmatch, onwin=onmask)


def voice_series(D):
    d, raw, st = D['d'], D['raw'], D['st']
    hs, js = np.nonzero(st > 0)
    vid = d['voice'][hs, js]
    o = np.lexsort((hs, vid)); hs, js, vid = hs[o], js[o], vid[o]
    cuts = np.r_[0, np.flatnonzero(np.diff(vid) != 0) + 1, len(vid)]
    for a, b in zip(cuts[:-1], cuts[1:]):
        h_, j_ = hs[a:b], js[a:b]
        coast = d['coast'][h_, j_] > 0
        ftr = raw[h_, j_, X.F_FTR].copy()
        last = ftr.copy()
        cur = ftr[0] if ftr[0] > 0 else d['fosc'][h_[0], j_[0]]
        for i in range(len(h_)):
            if not coast[i] and ftr[i] > 0:
                cur = ftr[i]
            last[i] = cur
        yield dict(h=h_, j=j_, coast=coast, fosc=d['fosc'][h_, j_], ftr_last=last, raw=raw[h_, j_, X.F_RAW], neartr=D['neartr'][h_, j_], on=st[h_, j_] == 2)


# ---------------------------------------------------------------------------------------------- candidates
def cand_a(tc_ms):
    return lambda s: onepole((~s['coast']).astype(float), al(10), al(tc_ms))


def cand_b(lo, hi, tau):
    return lambda s: onepole(1 - sstep(np.abs(s['fosc'] - s['ftr_last']) / np.maximum(s['ftr_last'], 1), lo, hi), al(tau), al(tau))


def cand_c(tdn, qmin):
    def f(s):
        p = (s['raw'] <= -15).astype(float)
        m = onepole(p, al(50), al(tdn))
        return qmin + (1 - qmin) * m
    return f


def cand_d():
    return lambda s: onepole(1.0 - (s['coast'] & s['neartr']).astype(float), al(10), al(10))


def prod(*fs):
    return lambda s: np.prod([f(s) for f in fs], axis=0)


CANDS = {'baseline q=1': lambda s: np.ones(len(s['h']))}
for t in (40, 80, 160):
    CANDS[f'(a) coast decay tau_c={t} ms'] = cand_a(t)
for (lo, hi) in ((.01, .03), (.015, .04), (.02, .06)):
    for tau in (20, 60):
        CANDS[f'(b) f_off ({lo*100:g}%,{hi*100:g}%) tau={tau} ms'] = cand_b(lo, hi, tau)
for tdn in (300, 600):
    for qmin in (.3, .5):
        CANDS[f'(c) slow fit tau_dn={tdn} ms qmin={qmin}'] = cand_c(tdn, qmin)
CANDS['(d) coasting near tracked ON'] = cand_d()
CANDS['(e1) a80 * d'] = prod(cand_a(80), cand_d())
CANDS['(e2) a80 * b(1.5,4,20)'] = prod(cand_a(80), cand_b(.015, .04, 20))
CANDS['(e3) a80 * b(1.5,4,20) * d'] = prod(cand_a(80), cand_b(.015, .04, 20), cand_d())
CANDS['(e4) a160 * b(2,6,60) * d'] = prod(cand_a(160), cand_b(.02, .06, 60), cand_d())
CANDS['(e5) a40 * b(1,3,20) * d'] = prod(cand_a(40), cand_b(.01, .03, 20), cand_d())


def main():
    data = {}
    for n in C.TRACKS:
        data[n] = build(n)
        P('built', n)
    res = {}
    for cname, fn in CANDS.items():
        acc = {n: dict(Wt=0., Ww=0., Rt=0., Rn=0., Wn_t=0., Ww_n=0., Ron_t=0., Ron_n=0., cross=0, ontime=0., rate=[], rqlow=0, rn=0) for n in C.TRACKS}
        for n in C.TRACKS:
            D = data[n]; Q = np.ones(D['w'].shape)
            a = acc[n]
            for s in voice_series(D):
                q = fn(s); Q[s['h'], s['j']] = q
                on = s['on']
                if on.any():
                    low = q < .5
                    # crossings between consecutive ON hops
                    idx = np.flatnonzero(on)
                    cr = 0
                    for k in range(1, len(idx)):
                        if idx[k] == idx[k - 1] + 1 and low[idx[k]] != low[idx[k - 1]]:
                            cr += 1
                    ot = on.sum() * DT
                    a['cross'] += cr; a['ontime'] += ot
                    if ot >= 0.5:
                        a['rate'].append(cr / ot)
            L = D['lab']; w = D['w']; wr = D['wrong']
            wq = w * Q ** 2
            a['Wt'] = wq[L].sum(); a['Ww'] = wq[L & wr].sum()
            a['Rt'] = w[L & ~wr].sum(); a['Rn'] = wq[L & ~wr].sum()
            m = L & ~wr & D['onwin']
            a['Ron_t'] = w[m].sum(); a['Ron_n'] = wq[m].sum()
            onr = L & ~wr & (D['st'] == 2)
            a['rn'] = int(onr.sum()); a['rqlow'] = int((Q[onr] < .5).sum())
        res[cname] = acc
    # ------------------------------------------------------------------ report
    def pooled(acc, excl=()):
        ns = [n for n in C.TRACKS if n not in excl]
        g = lambda k: sum(acc[n][k] for n in ns)
        return g
    P('\n### Q7 results. wrong share = sum(w q^2 wrong)/sum(w q^2); right kept = sum(w q^2 right)/sum(w right); re-attack = right weight within 0-200 ms after a bass MIDI onset;')
    P('crossings = q through 0.5 between consecutive ON hops, per second of ON time (pooled event rate; mean / p95 over voices with >= 0.5 s ON); ON-low = fraction of right-weight ON voice-hops with q < 0.5')
    P('| candidate | wrong % pooled | wrong % w/o T24 | right kept % pooled | right kept % w/o T24 | right kept % T60 | re-attack kept % T60 | re-attack kept % pooled | cross/s pooled (mean / p95 per voice) | ON-low % |')
    P('|---|---|---|---|---|---|---|---|---|---|')
    summary = {}
    for cname, acc in res.items():
        g = pooled(acc); g2 = pooled(acc, ('Track00024',)); t60 = acc['Track00060']
        rates = np.concatenate([acc[n]['rate'] for n in C.TRACKS]) if any(len(acc[n]['rate']) for n in C.TRACKS) else np.array([0.])
        row = dict(wrong=100 * g('Ww') / g('Wt'), wrong_x=100 * g2('Ww') / g2('Wt'), rk=100 * g('Rn') / g('Rt'), rk_x=100 * g2('Rn') / g2('Rt'),
                   rk60=100 * t60['Rn'] / t60['Rt'], ra60=100 * t60['Ron_n'] / max(t60['Ron_t'], 1e-30), rap=100 * g('Ron_n') / max(g('Ron_t'), 1e-30),
                   cross=g('cross') / g('ontime'), cmean=float(rates.mean()), cp95=float(np.percentile(rates, 95)), onlow=100 * g('rqlow') / max(g('rn'), 1))
        summary[cname] = row
        P(f'| {cname} | {row["wrong"]:.1f} | {row["wrong_x"]:.1f} | {row["rk"]:.1f} | {row["rk_x"]:.1f} | {row["rk60"]:.1f} | {row["ra60"]:.1f} | {row["rap"]:.1f} | {row["cross"]:.3f} ({row["cmean"]:.3f} / {row["cp95"]:.3f}) | {row["onlow"]:.2f} |')
    P('\nper-track wrong share % (columns in track order ' + ', '.join(n[-2:] for n in C.TRACKS) + ') and per-track right kept %:')
    for cname, acc in res.items():
        P(f'  {cname}: wrong ' + ' '.join(f'{100*acc[n]["Ww"]/max(acc[n]["Wt"],1e-30):5.1f}' for n in C.TRACKS) + ' | right kept ' + ' '.join(f'{100*acc[n]["Rn"]/max(acc[n]["Rt"],1e-30):5.1f}' for n in C.TRACKS))
    # ------------------------------------------------------------------ musical centrality of the right weight
    tot = np.zeros(5); onw = np.zeros(5)
    for n in C.TRACKS:
        D = data[n]; m = D['lab'] & ~D['wrong']
        for k in range(5):
            tot[k] += D['w'][m & (D['bmatch'] == k)].sum()
    P('\nright weight by what it matches: only non-bass instruments (bass MIDI note not within 50 cent of 0.5/1/2/3 f): %.1f %%; bass note x0.5: %.1f %%, x1 (fundamental): %.1f %%, x2: %.1f %%, x3: %.1f %%  (bass notes include the tp octave shift; a voice matching both is counted for its nearest bass ratio)'
      % tuple(100 * tot[[0, 1, 2, 3, 4]] / tot.sum()))
    # the same for the weight lost by the e3 candidate
    for cname in ('(e3) a80 * b(1.5,4,20) * d', '(a) coast decay tau_c=80 ms'):
        fn = CANDS[cname]; lost = np.zeros(5)
        for n in C.TRACKS:
            D = data[n]; Q = np.ones(D['w'].shape)
            for s in voice_series(D):
                Q[s['h'], s['j']] = fn(s)
            m = D['lab'] & ~D['wrong']
            for k in range(5):
                lost[k] += (D['w'] * (1 - Q ** 2))[m & (D['bmatch'] == k)].sum()
        P(f'right weight LOST by {cname}: share of the lost weight by match class [none, x0.5, x1, x2, x3] = ' + ', '.join(f'{100*v/lost.sum():.1f} %' for v in lost) +
          f'; lost fraction within each class = ' + ', '.join(f'{100*lost[k]/tot[k]:.1f} %' for k in range(5)))
    json.dump(summary, open(C.D16 / 'q7.json', 'w'), indent=1, default=float)
    open(C.D16 / 'q7_report.txt', 'w').write('\n'.join(out))


if __name__ == '__main__':
    main()
