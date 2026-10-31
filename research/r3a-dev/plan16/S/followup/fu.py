"""followup to Brief S.  Readings: followup/CHOICES.md.  Re-uses S cache logic (s_run.py); renders nothing new except re-synthesising S2-core layers split by category."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
import s_run as SR
import ladder as LD
import synth16 as SY
from data import *
import labels
from stems import stem_streams

GRID = 0.002
res1 = {}; E = {c: 0.0 for c in 'abcd'}; Etot = 0.0
sub = {}
for key in LD.SONGS:
    sig = Sig(key); dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    if not segs:
        continue
    real = SR.real_intervals_core(sig, LD.LAGS['core'])
    # classify every real interval
    kept = []; cls = []
    for r in real:
        w, occ, bo = SR.occupancy(r['t_on'], r['t_off'], segs)
        if w < 0:
            cls.append('sil')
        elif not SR.compat(r['fm'], segs[w]['f']):
            cls.append('inc')
        else:
            cls.append('kept'); kept.append(dict(r, w=w, occ=occ, ov=bo))
    matched = {q['w'] for q in kept}
    g = np.arange(0, dur + 1, GRID)
    def pres(sel):
        m = np.zeros(len(g), bool)
        for r, c in zip(real, cls):
            if c in sel:
                m |= (g >= r['t_on']) & (g < r['t_off'])
        return m
    p_kept, p_sil, p_inc = pres({'kept'}), pres({'sil'}), pres({'inc'})
    out = []
    for k, sg in enumerate(segs):
        if k in matched:
            continue
        m = (g >= max(sg['s'], 0.5)) & (g < sg['e'])
        n = m.sum() * GRID
        if n <= 0:
            out.append(dict(song=key, T=0, i=0, ii_inc=0, ii_sil=0, iii=0)); continue
        i_ = m & p_kept; r1 = m & ~i_
        ii_inc = r1 & p_inc; r2 = r1 & ~ii_inc
        ii_sil = r2 & p_sil; iii = r2 & ~ii_sil
        out.append(dict(song=key, T=n, i=i_.sum() * GRID, ii_inc=ii_inc.sum() * GRID, ii_sil=ii_sil.sum() * GRID, iii=iii.sum() * GRID))
    res1[key] = out
    # ---------- part 2
    truth = labels.Truth(key, sig.tc1)
    stem_bh, _ = stem_streams(key)
    S_ = np.array([s['s'] for s in segs]); E_ = np.array([s['e'] for s in segs])
    items = SR.s2_items(kept, segs)
    items_ok = [(it, q) for it, q in zip(items, kept) if it['j_off'] - it['j_on'] >= 4]
    voices = SR.build_voices(sig, sig.bh, [it for it, _ in items_ok])
    wmap = [q['w'] for _, q in items_ok]
    split_base = LD.make_split(truth, sig.tc1, 0.0)

    def mk(cat):
        def split(v, tt, f, a):
            right = split_base(v, tt, f, a)
            w = wmap[v['ivid']]
            idx = np.searchsorted(S_, tt, 'right') - 1
            cont = np.where((idx >= 0) & (tt < E_[np.clip(idx, 0, None)]), idx, -1)
            ca = (cont >= 0) & (cont != w)
            sil = cont < 0
            cb = sil & (tt >= E_[w]); cc = sil & (tt < S_[w])
            cd = ~(ca | cb | cc)
            m = {'a': ca, 'b': cb, 'c': cc, 'd': cd, 'all': np.ones(len(tt), bool)}[cat]
            return ~((~right) & m)          # part b (second layer) = wrong & category
        return split
    I = LD.I_MIN
    for cat in ('a', 'b', 'c', 'd', 'all'):
        _, yw = SY.render_layer16(voices, dur + 0.3, split=mk(cat))
        e = float(np.sum(yw[I:] ** 2))
        if cat == 'all':
            Etot += e
        else:
            E[cat] += e
    print('song', key, flush=True)

ER3 = sum(json.load(open('/home/ksysh/r3a-dev/plan16/A/ladder_raw.json'))['res'][k]['R3']['v6b']['E_right'] for k in LD.SONGS)
SRAW = json.load(open('/home/ksysh/r3a-dev/plan16/S/s_raw.json'))['res']
Etot_s = sum(SRAW[k]['S2-core']['v6b']['E_wrong'] for k in LD.SONGS)
lines = []
P = lines.append
P('# followup report')
for label, excl in (('all 10 songs', None), ('without Track00040', 'Track00040')):
    rows = [r for k, v in res1.items() if k != excl for r in v]
    nseg = len(rows); T = sum(r['T'] for r in rows)
    P(f'\n## part 1 ({label}): unmatched truth segments {nseg}, segment time (t>0.5 s) {T:.2f} s')
    P('class | time s | time share % | segments with majority(>50% of its time) in class')
    for nm, f in (('(i) kept voice linked to another note', 'i'), ('(ii-a) unkept voice, failed pitch filter', 'ii_inc'), ('(ii-b) unkept voice, silence won', 'ii_sil'), ('(iii) no ON/REL voice', 'iii')):
        s = sum(r[f] for r in rows); n = sum(1 for r in rows if r['T'] > 0 and r[f] > 0.5 * r['T'])
        P(f'{nm} | {s:.2f} | {100 * s / T:.1f} | {n}')
    P('segments with T=0 (entirely before 0.5 s): %d' % sum(1 for r in rows if r['T'] == 0))
P(f'\n## part 2: S2-core wrong energy (v6b, fixed gain F), pooled 10 songs')
P(f'total wrong layer energy (own render) {Etot:.4f}; S2-core from s_raw {Etot_s:.4f}; /R3right = {Etot / ER3:.4f}')
P('category | energy | share of total % | ratio to R3 right energy')
names = dict(a='(a) other-note portion inside a multi-note voice', b='(b) after matched note end, silence (tail)', c='(c) before matched note start, silence', d='(d) other')
for c in 'abcd':
    P(f'{names[c]} | {E[c]:.4f} | {100 * E[c] / Etot:.1f} | {E[c] / ER3:.4f}')
P(f'sum of categories {sum(E.values()):.4f} ({100 * sum(E.values()) / Etot:.1f} % of total; difference = cross terms)')
open('/home/ksysh/r3a-dev/plan16/S/followup/followup_report.txt', 'w').write('\n'.join(lines))
print('\n'.join(lines))
