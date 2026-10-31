"""Plan16 T report from t_raw_*.pkl -> t_report.txt"""
import sys, pickle, time
import numpy as np
from collections import defaultdict
T = '/home/ksysh/r3a-dev/plan16/T'
KEYS = ['Track00026', 'Track00024']
D = {k: pickle.load(open(f'{T}/t_raw_{k}.pkl', 'rb')) for k in KEYS}
L = []
P = lambda s='': L.append(s)
MS = [1, 2, 3, 4, 5, 6, 7, 8, 0.5, 1 / 3, 0.25]
MN = {1: 'k=1 (a)', 2: 'k=2', 3: 'k=3', 4: 'k=4', 5: 'k=5', 6: 'k=6', 7: 'k=7', 8: 'k=8', 0.5: 'x1/2', 1 / 3: 'x1/3 (info)', 0.25: 'x1/4 (info)'}


def wq(x, w, qs):
    o = np.argsort(x); x, w = np.asarray(x)[o], np.asarray(w)[o]; cw = np.cumsum(w) / w.sum()
    return [float(x[min(np.searchsorted(cw, q), len(x) - 1)]) for q in qs]


def shares(d, base_filter=None):
    """exact layer shares by category + proxy shares"""
    en = d['energy']; R_ = d['R_']; ns = len(d['nd'])
    cat = {'a': sum(en[R_[('a', i)]] for i in range(ns)), 'b': sum(en[R_[('b', i)]] for i in range(ns)), 'c': sum(en[R_[('c', i)]] for i in range(ns)),
           'd': en[R_['d']], 'e': en[R_['e']]}
    return cat


def proxy(recs, filt=None):
    c = defaultdict(float)
    for r in recs:
        if filt and not filt(r):
            continue
        c[r['c']['cat']] += r['wc']
    return c


def pct(x, tot):
    return 100 * x / tot if tot > 0 else float('nan')


def decide(a, b, c, d, e):
    s_abc = a + b + c; s_de = d + e
    if s_abc >= 60: return 'METRIC (a+b+c >= 60 %)'
    if s_de >= 50: return 'ENGINE (e+d >= 50 %)'
    return 'MIXED'


P(f'# plan16 T report -- {time.strftime("%Y-%m-%dT%H:%M:%S")}  (readings: CHOICES.md; units = energy / R3R)')
for k in KEYS:
    d = D[k]; recs = d['recs']; R3R = d['R3R']
    P(f'\n================ {k}')
    P(f'REPRO: my silent-wrong energy {d["E_sil_mine"] / R3R:.5f} (16.14: {"0.0516" if k.endswith("26") else "0.0146"}); sum of 5 category layers {d["layer_sum"] / R3R:.5f}; energy of the summed layers {d["sum_layers_energy_of_sum"] / R3R:.5f}')
    P(f'silent-wrong voice-hops {len(recs)} (counted t>0.5 s: {sum(1 for r in recs if r["wc"] > 0)}); stable-voice hop fraction (any voice, whole song): D_s=100 ms {100 * d["stable_frac"]["s100"]:.1f} %, 150 ms {100 * d["stable_frac"]["s150"]:.1f} %; stable_scan max trace hop read <= h: {d["maxread_ok"]}')
    f = np.array([r['f'] for r in recs]); w = np.array([r['wc'] for r in recs])
    q = wq(f, w, [.1, .25, .5, .75, .9])
    P(f'voice f of the silent-wrong energy (a^2 weight) deciles 10/25/50/75/90 %: ' + ' '.join(f'{x:.1f}' for x in q) + f' Hz; min {f.min():.1f} max {f.max():.1f}; weight share with f >= 4 x 36.7 Hz (146 Hz): {100 * w[f >= 146].sum() / w.sum():.1f} %; with f >= 260 Hz: {100 * w[f >= 260].sum() / w.sum():.1f} %')
    # alignment
    al = np.array([c for _, c in d['align']])
    P(f'ALIGNMENT CHECK (stem STFT argmax within +-300 cent of MIDI f0, 0.25 s into notes >= 0.4 s, {len(al)} notes): median {np.median(al):+.1f} cent, |dev| <= 50 cent: {100 * np.mean(np.abs(al) <= 50):.1f} %, <= 100 cent: {100 * np.mean(np.abs(al) <= 100):.1f} %')
    # shares
    cat = shares(d); tot = sum(cat.values())
    cp = proxy(recs); totp = sum(cp.values())
    P('\n### (a)-(e) table: exact layer energy (units) | share of layer sum % | proxy a^2 share %')
    for c_ in 'abcde':
        P(f'({c_}) | {cat[c_] / R3R:.5f} | {pct(cat[c_], tot):.1f} | {pct(cp[c_], totp):.1f}')
    P(f'sum | {tot / R3R:.5f} | 100 | 100     (E_sil rendered together {d["E_sil_mine"] / R3R:.5f})')
    sh = {c_: pct(cat[c_], tot) for c_ in 'abcde'}
    P(f'(a)+(b)+(c) = {sh["a"] + sh["b"] + sh["c"]:.1f} % (proxy {pct(cp["a"] + cp["b"] + cp["c"], totp):.1f} %); (d)+(e) = {sh["d"] + sh["e"]:.1f} % (proxy {pct(cp["d"] + cp["e"], totp):.1f} %)  =>  RULE: {decide(**sh)}   [proxy: {decide(*[pct(cp[c_], totp) for c_ in "abcde"])}]')
    # k coverage
    P('\n### k-coverage (non-exclusive, proxy weight share of ALL silent-wrong energy where some sounding non-drum note has f = m x f0 within 50 cent)')
    cov = defaultdict(float)
    for r in recs:
        for mm in r['c']['hit_k']:
            cov[mm] += r['wc']
    W = sum(r['wc'] for r in recs)
    P(' | '.join(f'{MN[m]} {pct(cov[m], W):.2f}' for m in MS))
    cb = defaultdict(float)
    for r in recs:
        if r['c']['cat'] == 'b':
            cb[r['c']['k']] += r['wc']
    P('first-match (b) by k (proxy share of all): ' + ' | '.join(f'{m} {pct(cb[m], W):.2f}' for m in (2, 3, 4, 5, 6, 7, 8, 0.5)))
    P('exact layer energy of (b) by first-match k (units): ' + ' | '.join(f'{m}: {d["energy"][d["R_"][("k", m)]] / R3R:.5f}' for m in (2, 3, 4, 5, 6, 7, 8, 0.5)))
    # per instrument
    P('\n### per-instrument share (stems with audio; exact layers, units, share of ALL layer energy %) for categories a/b/c')
    meta = d['meta']; ns = len(d['nd']); en = d['energy']; R_ = d['R_']
    agg_cls = defaultdict(float)
    for i, s in enumerate(d['nd']):
        ea, eb, ec = (en[R_[(c_, i)]] for c_ in 'abc')
        agg_cls[meta[s]['cls']] += ea + eb + ec
        if ea + eb + ec > 0:
            P(f'{s} {meta[s]["cls"]} / {meta[s]["prog"]} | a {ea / R3R:.5f} b {eb / R3R:.5f} c {ec / R3R:.5f} | {pct(ea + eb + ec, tot):.1f} % of all')
    P('by inst_class (a+b+c): ' + ' | '.join(f'{c_} {pct(v_, tot):.1f} %' for c_, v_ in sorted(agg_cls.items(), key=lambda x: -x[1]) if v_ > 0))
    # (d)/(e) dominant stem
    for c_ in 'de':
        dd = defaultdict(float); ww = 0.0
        for r in recs:
            if r['c']['cat'] == c_:
                dd[meta[r['c']['dom']]['cls'] + (' [drum]' if meta[r['c']['dom']]['drum'] else '')] += r['wc']; ww += r['wc']
        P(f'({c_}) dominant stem at f (proxy share within ({c_}) ): ' + ' | '.join(f'{c} {pct(v_, ww):.1f} %' for c, v_ in sorted(dd.items(), key=lambda x: -x[1])[:8]))
    # diagnostics per category
    P('\n### diagnostics per category (proxy weights): cents from f to the nearest V6b target (any note, 0.5/1/2/3): <=100 | 100-200 | 200-400 | >400 ; drum hit within [-150,+20] ms | kick ; engine-recipe peak at f ; mix excess dB p10/p50/p90 ; voice f p10/p50/p90')
    for c_ in 'abcde':
        rr = [r for r in recs if r['c']['cat'] == c_ and r['wc'] > 0]
        if not rr:
            continue
        w_ = np.array([r['wc'] for r in rr]); c2 = np.array([r['c2t'] for r in rr]); W_ = w_.sum()
        ex = wq([r['c']['excess'] for r in rr], w_, [.1, .5, .9]); ff = wq([r['f'] for r in rr], w_, [.1, .5, .9])
        P(f'({c_}) n {len(rr)} | ' + ' | '.join(f'{pct(w_[m].sum(), W_):.0f}%' for m in (c2 <= 100, (c2 > 100) & (c2 <= 200), (c2 > 200) & (c2 <= 400), c2 > 400)) +
          f' | drum {pct(sum(r["wc"] for r in rr if r["drum"]), W_):.0f}% kick {pct(sum(r["wc"] for r in rr if r["kick"]), W_):.0f}% | eng-peak {pct(sum(r["wc"] for r in rr if r["c"]["eng"]), W_):.0f}% | excess ' + '/'.join(f'{x:.1f}' for x in ex) + ' | f ' + '/'.join(f'{x:.0f}' for x in ff))
    P('\n### chance baseline for "<=100 cent from a V6b target": same records with f shifted by +-0.25 octave (all categories, proxy): ' +
      ' | '.join(f'{nm}: {pct(sum(r["wc"] for r in recs if r[nm] <= 100), W):.0f}%' for nm in ('c2t', 'null_up', 'null_dn')))
    P('### distance from f to the nearest mix local maximum (>= 6 dB over median, +-300 cent search), proxy shares: <=50 | 50-100 | 100-200 | 200-300 | none within 300')
    for c_ in 'cde':
        rr = [r for r in recs if r['c']['cat'] == c_ and r['wc'] > 0]
        if not rr:
            continue
        w_ = np.array([r['wc'] for r in rr]); npk = np.array([r['c']['nearpk'] for r in rr]); W_ = w_.sum()
        fin = np.isfinite(npk)
        P(f'({c_}) ' + ' | '.join(f'{pct(w_[m].sum(), W_):.0f}%' for m in (fin & (npk <= 50), fin & (npk > 50) & (npk <= 100), fin & (npk > 100) & (npk <= 200), fin & (npk > 200), ~fin)))
    rr = [r for r in recs if r['wc'] > 0]; w_ = np.array([r['wc'] for r in rr])
    for lab, g in (('real f', lambda r: r['c']['nearpk']), ('null +0.25 oct', lambda r: r['np_null'][0]), ('null -0.25 oct', lambda r: r['np_null'][1])):
        v_ = np.array([g(r) for r in rr]); fin = np.isfinite(v_)
        P(f'   all hops, {lab}: nearest mix peak <=50 {pct(w_[fin & (v_ <= 50)].sum(), w_.sum()):.0f}% | <=100 {pct(w_[fin & (v_ <= 100)].sum(), w_.sum()):.0f}% | <=200 {pct(w_[fin & (v_ <= 200)].sum(), w_.sum()):.0f}% | none in 300 {pct(w_[~fin].sum(), w_.sum()):.0f}%')
    # octave-folded distance to the sounding non-drum notes
    def fold(f, f0s, sh=0.0):
        if not f0s:
            return np.nan
        c = 1200 * np.log2(f * 2 ** sh / np.array(f0s))
        return float(np.min(np.abs((c + 600) % 1200 - 600)))
    P('### octave-folded distance (cent) from f to the nearest sounding non-drum MIDI note class (any octave), proxy shares: <=50 | 50-100 | 100-200 | >200 | no note sounding')
    for lab, sh_ in (('real f', 0.0), ('null +0.25 oct', 0.25), ('null -0.25 oct', -0.25)):
        for c_ in ('d', 'e'):
            rr = [r for r in recs if r['c']['cat'] == c_ and r['wc'] > 0]
            if not rr:
                continue
            w_ = np.array([r['wc'] for r in rr]); v_ = np.array([fold(r['f'], r['snd_f0'], sh_) for r in rr]); fin = np.isfinite(v_); W_ = w_.sum()
            P(f'({c_}) {lab}: ' + ' | '.join(f'{pct(w_[m].sum(), W_):.0f}%' for m in (fin & (v_ <= 50), fin & (v_ > 50) & (v_ <= 100), fin & (v_ > 100) & (v_ <= 200), fin & (v_ > 200), ~fin)))
    # stable / unstable split
    for nm in ('st100', 'st150'):
        P(f'\n### split by "a stable voice exists at this hop" ({nm}: D_s = {"100" if nm == "st100" else "150"} ms), proxy shares')
        for lab, flt in (('stable hops', lambda r: r[nm]), ('unstable hops', lambda r: not r[nm])):
            cc = proxy(recs, flt); tt_ = sum(cc.values())
            P(f'{lab}: weight share of all {pct(tt_, W):.1f} % | ' + ' | '.join(f'({c_}) {pct(cc[c_], tt_):.1f}' for c_ in 'abcde') + f' | (a+b+c) {pct(cc["a"] + cc["b"] + cc["c"], tt_):.1f} (d+e) {pct(cc["d"] + cc["e"], tt_):.1f}')
        rr = [r for r in recs if r[nm] and r['wc'] > 0]
        if rr:
            dd = defaultdict(float); ww = 0.0
            for r in rr:
                dd[meta[r['c']['dom']]['cls'] + (' [drum]' if meta[r['c']['dom']]['drum'] else '')] += r['wc']; ww += r['wc']
            c2 = np.array([r['c2t'] for r in rr]); w_ = np.array([r['wc'] for r in rr])
            P(f'stable subset: dominant stem at f: ' + ' | '.join(f'{c} {pct(v_, ww):.1f} %' for c, v_ in sorted(dd.items(), key=lambda x: -x[1])[:6]) + f'; cents-to-nearest V6b target median {wq(c2[np.isfinite(c2)], w_[np.isfinite(c2)], [.5])[0]:.0f}, share <=100: {pct(w_[c2 <= 100].sum(), w_.sum()):.0f} %, f p10/50/90 ' + '/'.join(f'{x:.0f}' for x in wq([r["f"] for r in rr], w_, [.1, .5, .9])))
P('\n================ pooled T26 + T24 (exact layers)')
cat = defaultdict(float); tot = 0.0; R3R = D[KEYS[0]]['R3R']
for k in KEYS:
    for c_, v_ in shares(D[k]).items():
        cat[c_] += v_; tot += v_
sh = {c_: pct(cat[c_], tot) for c_ in 'abcde'}
P(' | '.join(f'({c_}) {sh[c_]:.1f} %' for c_ in 'abcde') + f' | a+b+c {sh["a"] + sh["b"] + sh["c"]:.1f} | d+e {sh["d"] + sh["e"]:.1f}  =>  {decide(**sh)}')
open(f'{T}/t_report.txt', 'w').write('\n'.join(L))
print('\n'.join(L))
