"""Plan16 T post-result variant (labelled in CHOICES.md): (c) without the pitch tie; signed cents from (e) voice f to the nearest mix peak.  Not part of the rule."""
import sys, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/T')
from tlib import *
T_DIR = HOME / 'r3a-dev/plan16/T'
L = []
for key in ('Track00026', 'Track00024'):
    d = pickle.load(open(T_DIR / f't_raw_{key}.pkl', 'rb')); recs = d['recs']
    sig = Sig(key); tc = sig.tc1
    ctx = Ctx(key, tc)
    snd, tail = ctx.build_lists(0.0, 1.0)
    W = sum(r['wc'] for r in recs)
    base = {c: sum(r['wc'] for r in recs if r['c']['cat'] == c) for c in 'abcde'}
    gain = 0.0; signed = []; sw = []; nullg = dict(null_up=0.0, null_dn=0.0)
    for r in recs:
        if r['c']['cat'] in 'de' and r['wc'] > 0:
            m = int(round(r['t'] / FRAME_S))
            for si_, (f, acc) in enumerate(((r['f'], 'real'), (r['f'] * 2 ** 0.25, 'null_up'), (r['f'] * 2 ** -0.25, 'null_dn'))):
                hit = False
                for (si, f0, j) in tail[r['h']]:                      # NO pitch tie
                    s = ctx.nd[si]; n = ctx.notes[s]; S = ctx.S[s]
                    ms, me = int(round(n['s'][j] / FRAME_S)), int(round(n['e'][j] / FRAME_S))
                    lo, hi = bins_of(f)
                    if bandmax(S[m], f) >= float(S[ms:me + 1, lo:hi + 1].max()) - 30.0:
                        hit = True; break
                if hit:
                    if acc == 'real':
                        gain += r['wc']
                    else:
                        nullg[acc] += r['wc']
        if r['c']['cat'] == 'e' and r['wc'] > 0:
            row = ctx.Smix[int(round(r['t'] / FRAME_S))]
            lo, hi = bins_of(r['f'], 300.0); fb = np.arange(NB) * DF; Wd = max(30.0, 0.5 * r['f']); best = None
            for b in range(max(lo, 1), min(hi, NB - 2) + 1):
                if row[b] >= row[b - 1] and row[b] >= row[b + 1]:
                    sel = (np.abs(fb - r['f']) <= Wd) & (np.abs(fb - b * DF) >= 10.0) & (fb >= DF)
                    if row[b] - np.median(row[sel]) >= 6.0:
                        c = 1200 * math.log2(b * DF / r['f'])
                        if best is None or abs(c) < abs(best):
                            best = c
            if best is not None:
                signed.append(best); sw.append(r['wc'])
    c_loose = base['c'] + gain
    L.append(f'{key}: base (a+b+c) proxy share {100 * (base["a"] + base["b"] + base["c"]) / W:.1f} %; (c) without pitch tie: (c) proxy share {100 * c_loose / W:.1f} % (+{100 * gain / W:.1f} pp from (d)/(e)) -> (a+b+c)_loose = {100 * (base["a"] + base["b"] + c_loose) / W:.1f} % (threshold 60)')
    L.append(f'   control (same loose test with f shifted +-0.25 octave on the same (d)/(e) hops): +{100 * nullg["null_up"] / W:.1f} pp / +{100 * nullg["null_dn"] / W:.1f} pp  (vs +{100 * gain / W:.1f} pp real)')
    signed = np.array(signed); sw = np.array(sw)
    if len(signed):
        L.append(f'   (e) signed cents (nearest mix peak minus voice f, +-300 search; + = peak above voice), weighted: n {len(signed)}; share peak above {100 * sw[signed > 0].sum() / sw.sum():.0f} %; below {100 * sw[signed < 0].sum() / sw.sum():.0f} %; weighted median {np.median(np.repeat(signed, np.maximum((sw / sw.sum() * 5000).astype(int), 1))):+.0f}; deciles 10/25/50/75/90: ' +
          ' '.join(f'{x:+.0f}' for x in np.interp([.1, .25, .5, .75, .9], np.cumsum(sw[np.argsort(signed)]) / sw.sum(), np.sort(signed))))
print('\n'.join(L))
open(T_DIR / 't_variant.txt', 'w').write('\n'.join(L))
