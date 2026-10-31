"""16.7 rows S1, S2-LA, S2-core (+ info S2b-LA / S2b-core).  Readings: CHOICES.md (written before this was run).
usage: cd ~/r3-work/tools/pvb-harness; PYTHONPATH=.:study:$HOME/r3a-dev/diag16:$HOME/r3a-dev/verify_core ~/venv-rootnote/bin/python ~/r3a-dev/plan16/S/s_run.py
-> plan16/S/s_raw.json"""
import sys, time, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
import ladder as LD
from data import *
import la, labels, rows as R, pipeline as P
from stems import stem_streams

OUTD = HOME / 'r3a-dev/plan16/S'
KEYS = LD.KEYS
SONGS = LD.SONGS
L_RS = LD.L_RS
TOL = 50.0
RAW_A = json.load(open(HOME / 'r3a-dev/plan16/A/ladder_raw.json'))
LAGS = LD.LAGS


def cents(f, f0):
    return 1200 * np.log2(np.maximum(f, 1e-9) / f0)


# ------------------------------------------------------------------------------------------ voice builder (A's oracle_voices, generalised)
def build_voices(sig, x, items):
    """items: dict(tc, f, j_on, j_off).  LS N_p 320 / N_f 191 on stream x, window clipped to [j_on, j_off) (A's machinery)"""
    nx = len(x); chunks, ivs = [], []
    for it in items:
        if it['j_off'] - it['j_on'] < la.GRID_A // 2:
            continue
        ch = la.Chunk(); ch.cid = len(chunks); ch.id = len(chunks)
        ch.tc = np.asarray(it['tc'], float); ch.f = np.asarray(it['f'], float)
        la.prepare_chunk(ch, nx, L_RS, 191)
        chunks.append(ch)
        ivs.append(dict(ch=ch, cid=ch.cid, j_on=int(it['j_on']), j_off=int(it['j_off']), ivid=len(ivs)))
    if not ivs:
        return []
    la.solve_amplitudes(sig, x, chunks, ivs, L_RS, 191)
    for iv in ivs:
        la.smooth(iv, L_RS)
    return R.voices_la(dict(ivs=ivs, L_ms=L_RS), None)


def const_item(f, t_on, t_off):
    return dict(tc=[t_on - 0.2, t_off + 0.2], f=[f, f], j_on=int(round(float(stream_index(t_on)))), j_off=int(round(float(stream_index(t_off)))))


# ------------------------------------------------------------------------------------------ S1
def s1_items(segs, chunks, ts_tc, dur):
    """per segment: chosen candidate, in-tolerance runs.  returns items, info per segment"""
    # all real hops of all chunks
    cid = np.concatenate([np.full(len(c.hs), i) for i, c in enumerate(chunks)]) if chunks else np.zeros(0, int)
    hh = np.concatenate([c.hs for c in chunks]); tcs = ts_tc[hh]
    ff = np.concatenate([c.f[c.hs - c.h0] for c in chunks])
    o = np.argsort(tcs, kind='stable'); cid, hh, tcs, ff = cid[o], hh[o], tcs[o], ff[o]
    items, info = [], []
    for k, sg in enumerate(segs):
        lo = np.searchsorted(tcs, sg['s'], 'left'); hi = np.searchsorted(tcs, sg['e'], 'left')
        c_, h_, t_, f_ = cid[lo:hi], hh[lo:hi], tcs[lo:hi], ff[lo:hi]
        ce = np.abs(cents(f_, sg['f']))
        ok = ce <= TOL
        lenient = False
        for kk in (0.5, 2.0, 3.0):
            if np.any(np.abs(cents(f_, kk * sg['f'])) <= TOL):
                lenient = True
        if not ok.any():
            info.append(dict(missing=True, lenient=lenient, nhop=0, first_delay=None)); continue
        best, bcnt, bmed = None, -1, 1e9
        for ci in np.unique(c_[ok]):
            m = ok & (c_ == ci); n = int(m.sum()); med = float(np.median(ce[m]))
            if n > bcnt or (n == bcnt and med < bmed):
                best, bcnt, bmed = ci, n, med
        m = ok & (c_ == best)
        hs_, ts_, fs_ = h_[m], t_[m], f_[m]
        o = np.argsort(hs_); hs_, ts_, fs_ = hs_[o], ts_[o], fs_[o]
        cut = np.flatnonzero(np.diff(hs_) != 1) + 1
        for a, b in zip(np.r_[0, cut], np.r_[cut, len(hs_)]):
            tc_r, f_r = ts_[a:b], fs_[a:b]
            t_on = max(sg['s'], tc_r[0]); t_off = min(sg['e'], tc_r[-1] + HOP_S)
            if t_off <= t_on:
                continue
            items.append(dict(tc=tc_r, f=f_r, j_on=int(round(float(stream_index(t_on)))), j_off=int(round(float(stream_index(t_off)))), seg=k, t_on=t_on, t_off=t_off))
        info.append(dict(missing=False, lenient=lenient, nhop=int(bcnt), first_delay=float(ts_[0] - sg['s']),
                         cov_time=float(sum(min(sg['e'], r['t_off']) - max(sg['s'], r['t_on']) for r in items if r['seg'] == k))))
    return items, info


# ------------------------------------------------------------------------------------------ S2
def occupancy(t_on, t_off, segs):
    """winner segment index (or -1 if silence wins), its occupancy fraction, overlap seconds list"""
    best, bo = -1, 0.0; tot = 0.0
    for k, sg in enumerate(segs):
        ov = min(t_off, sg['e']) - max(t_on, sg['s'])
        if ov > 0:
            tot += ov
            if ov > bo:
                best, bo = k, ov
    L = t_off - t_on
    if L <= 0 or bo <= (L - tot) or best < 0:
        return -1, 0.0, bo
    return best, bo / L, bo


def compat(fm, f_w):
    return any(abs(cents(fm, k * f_w)) <= TOL for k in (0.5, 1.0, 2.0, 3.0))


def real_intervals_la(key):
    d = P.load_la(key, 'bh', 64, 191)
    out = []
    for iv in d['res']['ivs']:
        ch = iv['ch']
        t_on = float(stream_time(iv['j_on'])); t_off = float(stream_time(iv['j_off']))
        m = (ch.tc >= t_on) & (ch.tc <= t_off)
        fm = float(np.median(ch.f[m])) if m.any() else float(np.interp(0.5 * (t_on + t_off), ch.tc, ch.f))
        out.append(dict(t_on=t_on, t_off=t_off, fm=fm))
    return out


def real_intervals_core(sig, lag):
    d = sig.core_d; tc = sig.core_tc
    out = []
    for v in np.unique(d['voice'][d['state'] > 0]):
        hs, js = np.nonzero((d['voice'] == v) & (d['state'] >= 2))
        if not len(hs):
            continue
        o = np.argsort(hs); hs, js = hs[o], js[o]
        stt = d['state'][hs, js]
        cut = np.flatnonzero((np.diff(hs) != 1) | ((stt[:-1] == 3) & (stt[1:] == 2))) + 1
        for a, b in zip(np.r_[0, cut], np.r_[cut, len(hs)]):
            h, j = hs[a:b], js[a:b]
            out.append(dict(t_on=float(tc[h[0]]) + lag, t_off=float(tc[h[-1]]) + HOP_S + lag, fm=float(np.median(d['fosc'][h, j]))))
    return out


def s2_select(real, segs, dedup=False):
    """real intervals -> kept list with winner; counts"""
    kept, n_sil, n_inc = [], 0, 0
    for r in real:
        w, occ, bo = occupancy(r['t_on'], r['t_off'], segs)
        if w < 0:
            n_sil += 1; continue
        if not compat(r['fm'], segs[w]['f']):
            n_inc += 1; continue
        kept.append(dict(r, w=w, occ=occ, ov=bo))
    if dedup:
        best = {}
        for q in kept:
            if q['w'] not in best or q['ov'] > best[q['w']]['ov']:
                best[q['w']] = q
        kept = list(best.values())
    return kept, n_sil, n_inc


def s2_items(kept, segs):
    return [const_item(segs[q['w']]['f'], q['t_on'], q['t_off']) for q in kept]


def boundary_stats(kept, segs, act, dur):
    """signed errors (ms): kept intervals vs winner MIDI / stem boundaries; nearest-onset per attack segment"""
    out = dict(d_on_midi=[], d_off_midi=[], d_on_stem=[], d_off_stem=[], single=[], d_on_nearest=[], d_on_nearest_stem=[], d_off_nearest=[], d_off_nearest_stem=[],
               n_att=0, n_att_noonset=0, n_seg=0, n_seg_nooff=0)
    for q in kept:
        sg = segs[q['w']]
        out['d_on_midi'].append((q['t_on'] - sg['s']) * 1e3); out['d_off_midi'].append((q['t_off'] - sg['e']) * 1e3)
        a = act[q['w']]
        out['d_on_stem'].append((q['t_on'] - a['on']) * 1e3 if a['active'] else None); out['d_off_stem'].append((q['t_off'] - a['off']) * 1e3 if a['active'] else None)
        out['single'].append(bool(q['occ'] >= 0.8))
    ons = np.array([q['t_on'] for q in kept]); offs = np.array([q['t_off'] for q in kept])
    for k, sg in enumerate(segs):
        a = act[k]
        out['n_seg'] += 1
        if sg['attack'] and 0.6 <= sg['s'] <= dur - 0.3:
            out['n_att'] += 1
            if len(ons) and np.abs(ons - sg['s']).min() <= 0.3:
                i = np.argmin(np.abs(ons - sg['s'])); out['d_on_nearest'].append((ons[i] - sg['s']) * 1e3)
                out['d_on_nearest_stem'].append((ons[i] - a['on']) * 1e3 if a['active'] else None)
            else:
                out['n_att_noonset'] += 1
        if len(offs) and np.abs(offs - sg['e']).min() <= 0.3:
            i = np.argmin(np.abs(offs - sg['e'])); out['d_off_nearest'].append((offs[i] - sg['e']) * 1e3)
            out['d_off_nearest_stem'].append((offs[i] - a['off']) * 1e3 if a['active'] else None)
        else:
            out['n_seg_nooff'] += 1
    return out


def seg_time_cover(segs, voices, i_min_t=0.5):
    """fraction of segment time (t>0.5) with no layer presence (voice amp > 0)"""
    tot = miss = 0.0
    grid = np.arange(0, 40, 0.002)
    pres = np.zeros(len(grid), bool)
    for v in voices:
        pres |= (grid >= v['t'][0]) & (grid <= v['t'][-1]) & (np.interp(grid, v['t'], v['amp'], left=0, right=0) > 0)
    for sg in segs:
        m = (grid >= max(sg['s'], i_min_t)) & (grid < sg['e'])
        tot += m.sum(); miss += (m & ~pres).sum()
    return float(miss * 0.002), float(tot * 0.002)


def main():
    t0 = time.time()
    res = {k: {} for k in KEYS}; bnd = {k: {} for k in KEYS}; s1info = {}
    y3s = {}
    check = {}
    for key in KEYS:
        sig = Sig(key); dur = LD.dur_of(key)
        segs, rf = LD.segments(key); off = LD.song_off(key)
        tr_p = labels.Truth(key, sig.tc1); tr_s = LD.StrictTruth(sig.tc1, segs)
        truths = dict(v6b=tr_p, strict=tr_s)
        attacks = LD.attack_list(segs, rf, off, dur)
        stem_bh, _ = stem_streams(key)
        act = LD.stem_activity(segs, stem_bh)
        res[key]['n_segments'] = len(segs); res[key]['n_gap_attacks'] = int(len(attacks[0]))
        vo = {}
        # consistency: recompute R2 / R3 with A's code
        vo['R2c'] = LD.oracle_voices(sig, sig.bh, segs); vo['R3c'] = LD.oracle_voices(sig, stem_bh, segs)
        # S1
        d = P.load_la(key, 'bh', 64, 191)
        chunks = d['res']['chunks']
        if len(segs):
            items, info = s1_items(segs, chunks, sig.tc1, dur)
            vo['S1'] = build_voices(sig, sig.bh, items)
        else:
            items, info = [], []; vo['S1'] = []
        s1info[key] = info
        # S2
        real_la = real_intervals_la(key); real_core = real_intervals_core(sig, LAGS['core'])
        s2 = {}
        for nm, real in (('LA', real_la), ('core', real_core)):
            for dd_, tag in ((False, 'S2-' + nm), (True, 'S2b-' + nm)):
                if not len(segs):
                    kept, ns, ni = [], 0, 0
                else:
                    kept, ns, ni = s2_select(real, segs, dedup=dd_)
                s2[tag] = (kept, ns, ni, len(real))
                vo[tag] = build_voices(sig, sig.bh, s2_items(kept, segs)) if kept else []
                bnd[key][tag] = boundary_stats(kept, segs, act, dur) if len(segs) else None
                bnd[key][tag + '_cnt'] = dict(n_real=len(real), n_silence=ns, n_incompat=ni, n_kept=len(kept),
                                              seg_missing=int(len(segs) - len({q['w'] for q in kept})) if len(segs) else 0)
        for rn, v in vo.items():
            m = LD.measure(v, 0.0, sig, truths, dur, attacks)
            y3s[(key, rn)] = m.pop('y3')
            if key == 't60_36_48':
                m['v5a'] = LD.v5a_of(y3s[(key, rn)], dur)
            res[key][rn] = m
        miss_t, tot_t = seg_time_cover(segs, vo['S1']) if len(segs) else (0.0, 0.0)
        res[key]['s1_time'] = dict(miss=miss_t, tot=tot_t)
        # consistency vs A
        if len(segs):
            for a_, b_ in (('R2c', 'R2'), ('R3c', 'R3')):
                for tn in ('v6b', 'strict'):
                    for f in ('E_right', 'E_wrong'):
                        x1 = res[key][a_][tn][f]; x2 = RAW_A['res'][key][b_][tn][f]
                        check.setdefault(f'{b_}.{tn}.{f}', []).append(abs(x1 - x2) / max(abs(x2), 1e-12))
        print('song', key, 'segs', len(segs), 'S1 missing', sum(i['missing'] for i in info), round(time.time() - t0, 1), flush=True)
    chk = {k: float(np.max(v)) for k, v in check.items()}
    print('consistency (max rel diff vs A ladder_raw):', chk)
    for k in KEYS:
        for rn in ('R2c', 'R3c'):
            res[k].pop(rn, None)
    json.dump(dict(res=res, bnd=bnd, s1info=s1info, check=chk, lags=LAGS), open(OUTD / 's_raw.json', 'w'), default=float)
    print('done', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()
