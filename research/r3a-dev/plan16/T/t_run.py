"""Plan16 T: 16.14 attribution of the silent (V cause-1) wrong energy of T26 / T24.  usage: runpy.sh t_run.py [Track00026 Track00024]
writes t_raw_<key>.pkl, prints the reproduction line first."""
import sys, time, json, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/T')
from tlib import *
from scipy.signal import sosfilt

T_DIR = HOME / 'r3a-dev/plan16/T'
BASE = dict(slack=0.0, tailwin=1.0, tailref='f', mixthr=6.0, eng=True)


def iter_voices(voices, dur_s):
    n = int(np.ceil(dur_s * FSC)) + 8
    for vi, v in enumerate(voices):
        t = v['t']
        i0 = max(0, int(np.floor(t[0] * FSC))); i1 = min(n, int(np.ceil(t[-1] * FSC)) + 1)
        if i1 <= i0 + 1:
            continue
        tt = np.arange(i0, i1) / FSC
        f = np.interp(tt, t, v['f']); a = np.interp(tt, t, v['amp'], left=0.0, right=0.0)
        yield vi, v, tt, f, a, i0, i1, n


def gather(voices, truth, tc, dur_s):
    """silent-wrong (voice, hop) records: same ws rule as D/V fn"""
    recs = []
    for vi, v, tt, f, a, i0, i1, n in iter_voices(voices, dur_s):
        t0_ = tt - LAG
        h = np.clip(np.rint((t0_ - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
        uh, inv = np.unique(h, return_inverse=True)
        fh = np.interp(tc[uh], v['t'], v['f'])
        wb, ws = truth.wrong2(uh, fh)
        for k, hh in enumerate(uh):
            if ws[k]:
                msk = (inv == k) & (np.arange(len(tt)) >= I_MIN - i0)   # samples of this hop that count (t > 0.5 s)
                recs.append(dict(vi=vi, h=int(hh), f=float(fh[k]), w=float((a[inv == k] ** 2).sum()), wc=float((a[msk] ** 2).sum())))
    return recs


def render_w(voices, truth, tc, dur_s, rowmap, nrow):
    """rowmap[(vi,h)] -> list of (row, weight); row nrow-1 = all silent-wrong samples"""
    n = int(np.ceil(dur_s * FSC)) + 8
    Y = np.zeros((nrow, n))
    for vi, v, tt, f, a, i0, i1, n_ in iter_voices(voices, dur_s):
        t0_ = tt - LAG
        h = np.clip(np.rint((t0_ - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
        uh, inv = np.unique(h, return_inverse=True)
        fh = np.interp(tc[uh], v['t'], v['f'])
        wb, ws = truth.wrong2(uh, fh)
        ws = ws[inv]
        if not ws.any():
            continue
        ph = 2 * np.pi * np.cumsum(f) / FSC
        G = SY.engine_gains(f, 8)
        s = np.zeros(len(tt))
        for k in range(2, 9):
            s += G[k - 2] * np.cos(k * ph)
        x = a * s
        W = np.zeros((nrow, len(tt)))
        for hh in np.unique(h[ws]):
            sel = ws & (h == hh)
            for row, w in rowmap[(vi, int(hh))]:
                W[row, sel] += w
        for r in np.flatnonzero(W.any(1)):
            Y[r, i0:i1] += W[r] * x
    return sosfilt(DC.T.OUT_SOS, Y, axis=1)


def rows_for(ctx):
    ns = len(ctx.nd)
    R_ = {}
    for ci, c in enumerate('abc'):
        for si in range(ns):
            R_[(c, si)] = ci * ns + si
    base = 3 * ns
    R_['d'] = base; R_['e'] = base + 1
    for ki, kk in enumerate(M_RULE_B):
        R_[('k', kk)] = base + 2 + ki
    nrow = base + 2 + len(M_RULE_B) + 1
    return R_, nrow


def one(key):
    t00 = time.time()
    sig = Sig(key); dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    assert len(segs) == 0, 'T script is written for no-bass-excerpt songs'
    act = act15(segs, rf['bz'], dur)
    truth = SATruth(key, sig.tc1, segs, act)
    cv = R.voices_core(sig); annotate(cv, segs)
    assert all(v['cls'] == 2 for v in cv)
    voices = E.shift(cv, LAG)
    tc = sig.tc1
    ctx = Ctx(key, tc)
    print(key, 'ctx ready', round(time.time() - t00, 1), 'stems', ctx.sids, flush=True)
    recs = gather(voices, truth, tc, dur + 0.3)
    print(key, 'silent-wrong voice-hops', len(recs), flush=True)
    # alignment sanity: stem STFT peak at the MIDI f0 inside notes
    chk = []
    for s in ctx.nd:
        n = ctx.notes[s]
        for j in range(len(n['s'])):
            if n['s'][j] > 28 or n['e'][j] - n['s'][j] < 0.4:
                continue
            tm = n['s'][j] + 0.25
            row = ctx.S[s][int(round(tm / FRAME_S))]
            lo, hi = bins_of(n['f0'][j], 300.0)
            b = lo + int(np.argmax(row[lo:hi + 1]))
            chk.append((s, float(1200 * np.log2(max(b * DF, 1e-9) / n['f0'][j]))))
    snd, tail = ctx.build_lists(BASE['slack'], BASE['tailwin'])
    cls_ = {}
    for r in recs:
        c = ctx.classify(r['h'], float(tc[r['h']]), r['f'], snd, tail, BASE)
        cls_[(r['vi'], r['h'])] = c
        r['c'] = c
        r['t'] = float(tc[r['h']])
        r['snd_f0'] = [float(x[1]) for x in snd[r['h']]]
        r['np_null'] = [ctx.mix_nearest(r['t'], r['f'] * 2 ** sh_) for sh_ in (0.25, -0.25)]
        tg = truth.tg(r['h'])
        if len(tg):
            r['c2t'] = float(np.min(np.abs(np.log2(max(r['f'], 1e-9)) - tg)) * 1200)
            j = np.argmin(np.abs(np.log2(max(r['f'], 1e-9)) - tg)); r['c2t_signed'] = float((np.log2(max(r['f'], 1e-9)) - tg[j]) * 1200)
            for nm, sh_ in (('null_up', 0.25), ('null_dn', -0.25)):
                r[nm] = float(np.min(np.abs(np.log2(max(r['f'], 1e-9)) + sh_ - tg)) * 1200)
        else:
            r['c2t'] = np.nan; r['c2t_signed'] = np.nan; r['null_up'] = np.nan; r['null_dn'] = np.nan
        dh = rf['drum_on']; kk = rf['kick_on']
        r['drum'] = bool(len(dh) and np.any((dh >= r['t'] - 0.15) & (dh <= r['t'] + 0.02)))
        r['kick'] = bool(len(kk) and np.any((kk >= r['t'] - 0.15) & (kk <= r['t'] + 0.02)))
    print(key, 'classified', round(time.time() - t00, 1), flush=True)
    # stable voice flags (16.13)
    sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/G')
    import gcommon as GC
    st = {ds: GC.stable_scan(sig.core_d, ds) for ds in (0.100, 0.150)}
    for r in recs:
        r['st100'] = bool(st[0.100]['stable'][r['h']]); r['st150'] = bool(st[0.150]['stable'][r['h']])
    # exact render
    R_, nrow = rows_for(ctx)
    rowmap = {}
    for (vi, h), c in cls_.items():
        if c['cat'] in 'abc':
            L = c['stems']; w = 1.0 / len(L)
            lst = [(R_[(c['cat'], si)], w) for si in L]
            if c['cat'] == 'b':
                lst.append((R_[('k', c['k'])], 1.0))
        else:
            lst = [(R_[c['cat']], 1.0)]
        lst.append((nrow - 1, 1.0))
        rowmap[(vi, h)] = lst
    Y = render_w(voices, truth, tc, dur + 0.3, rowmap, nrow)
    y = Y[:, I_MIN:]
    en = [float(np.sum(y[r] ** 2)) for r in range(nrow)]
    R3R = r3_right(SONGS)
    base_rows = list(range(3 * len(ctx.nd) + 2))
    out = dict(key=key, recs=recs, energy=en, R_=R_, nrow=nrow, nd=ctx.nd, sids=ctx.sids, meta=ctx.meta, E_sil_mine=en[-1], R3R=R3R,
               layer_sum=float(sum(en[r] for r in base_rows)), sum_layers_energy_of_sum=float(np.sum(y[base_rows].sum(0) ** 2)),
               align=chk, nhops=len(tc), tc0=float(tc[0]),
               stable_frac=dict(s100=float(st[0.100]['stable'].mean()), s150=float(st[0.150]['stable'].mean())),
               maxread_ok=bool(all(((st[d]['maxread'] - np.arange(len(tc))) <= 0).all() for d in st)))
    # variants (proxy only)
    pickle.dump(out, open(T_DIR / f't_raw_{key}.pkl', 'wb'))
    print(key, 'E_sil mine / R3R =', out['E_sil_mine'] / R3R, 'layer-sum / R3R =', out['layer_sum'] / R3R, 'secs', round(time.time() - t00, 1), flush=True)
    return out


if __name__ == '__main__':
    keys = sys.argv[1:] or ['Track00026', 'Track00024']
    v = json.load(open(HOME / 'r3a-dev/plan16/V/v_raw.json'))
    for k in keys:
        o = one(k)
        ref = v[k]['E_sil'] / o['R3R']
        print(f'REPRO {k}: mine {o["E_sil_mine"] / o["R3R"]:.5f} vs V v_raw {ref:.5f} (rel diff {abs(o["E_sil_mine"] / o["R3R"] - ref) / ref:.2e})', flush=True)
