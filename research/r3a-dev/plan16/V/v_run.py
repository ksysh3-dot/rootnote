"""Plan16 V: split the core v1.5 'silence' stem-aware wrong energy by cause (CHOICES.md).
usage: ../D/runpy.sh ../V/v_run.py  -> v_raw.json, v_arrays.npz, v_report.txt   (add arg 'report' to only redo the report)"""
import sys, time, json, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import multiprocessing as mp
import dcommon as DC
from dcommon import *

V_DIR = HOME / 'r3a-dev/plan16/V'
CAUSES = ['1 no-bass song', '2 drum', '3 bass reverb/late', '4 other instrument (MIDI)', '5 other']
NC = 8                                    # 0 right, 1 excused, 2 non-silence sa-wrong, 3..7 = causes 1..5 of silence-voice sa-wrong
FSR = 3000.0


def compat_any(f, f0, mult=(0.5, 1.0, 2.0, 3.0), tol=50.0):
    ok = np.zeros(len(f), bool)
    for k in mult:
        ok |= np.abs(cents(f, k * f0)) <= tol
    return ok


def one_song(key):
    t0 = time.time()
    sig = Sig(key); dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    act = act15(segs, rf['bz'], dur)
    truth = SATruth(key, sig.tc1, segs, act)
    cv = R.voices_core(sig)
    annotate(cv, segs)
    voices = E.shift(cv, LAG)
    tc = sig.tc1
    nobass = len(segs) == 0
    S_ = np.array([s['s'] for s in segs]); E_ = np.array([s['e'] for s in segs])
    # bass notes (all, with tp), stem envelope
    ss, es, ps = rf['ss'], rf['es'], rf['ps']
    bn = np.flatnonzero((es > 0) & (ss < dur)) if len(ss) else np.zeros(0, int)
    bs, be, bf = ss[bn], es[bn], 440 * 2 ** ((ps[bn] + rf['tp'] - 69) / 12)
    env = None
    if len(bn):
        band = X.band_fft(np.asarray(rf['bz'][:int((dur + 1.0) * FS)], float), 40, 220)
        env = np.sqrt(np.convolve(band ** 2, np.ones(480) / 480, 'same'))[::16]
    bpk = np.zeros(len(bn))
    for i in range(len(bn)):
        a_, b_ = max(0, int(round(bs[i] * FSR))), min(len(env) - 1, int(round(be[i] * FSR)))
        bpk[i] = env[a_:b_ + 1].max() if b_ >= a_ else 0.0
    # other instruments (non-drum, non-bass)
    bkeys = set(zip(np.round(rf['ss'], 3), np.round(rf['es'], 3), np.round(rf['ps'], 3)))
    ns_, ne_, npch = rf['nd_s'], rf['nd_e'], rf['nd_p']
    isb = np.array([(round(a, 3), round(b, 3), round(c, 3)) in bkeys for a, b, c in zip(ns_, ne_, npch)], bool) if len(ns_) else np.zeros(0, bool)
    os_, oe_, of0 = ns_[~isb], ne_[~isb], 440 * 2 ** ((npch[~isb] - 69) / 12)
    dh = np.asarray(rf['drum_on'], float)
    vidx = {id(w): i for i, w in enumerate(voices)}
    vstat = {}                               # voice idx -> dict
    store = dict(f=[], w=[], c=[], v=[])     # silence sa-wrong samples
    info = dict(late_pitch_only=0.0, late_total=0.0)
    comp_base = comp_fn_factory(truth, tc, LAG, segs)

    def fn(v, tt, f, a):
        t0_ = tt - LAG
        h = np.clip(np.rint((t0_ - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
        uh, inv = np.unique(h, return_inverse=True)
        fh = np.interp(tc[uh], v['t'], v['f'])
        wb, ws = truth.wrong2(uh, fh)
        wb, ws = wb[inv], ws[inv]
        comp = np.zeros(len(tt), int)
        comp[wb & ~ws] = 1
        cls = v.get('cls', 2)
        comp[ws & (cls != 2)] = 2
        if cls != 2:
            return comp
        # silence voice: lifetime in silence
        alive = a > 0
        if alive.any():
            idx = np.searchsorted(S_, tt, 'right') - 1
            cov = (idx >= 0) & (tt < E_[np.clip(idx, 0, None)]) if len(S_) else np.zeros(len(tt), bool)
            vstat[vidx[id(v)]] = dict(life=float(alive.sum() / FSR), nobass_share=float((alive & ~cov).sum() / alive.sum()))
        m = ws
        if not m.any():
            return comp
        cause = np.full(len(tt), 5, int)
        remaining = m.copy()
        if nobass:
            cause[remaining] = 1; remaining[:] = False
        # 2 drum
        if remaining.any() and len(dh):
            t_, amp_ = v['t'], v['amp']
            nz = np.flatnonzero(amp_ > 0)
            if len(nz):
                birth = float(t_[nz[0]]); t_off = float(t_[nz[-1]])
                cand = dh[(dh >= birth - 0.3) & (dh <= t_off + 0.3)]
                Q = []
                for d in cand:
                    ad = float(np.interp(d, t_, amp_, left=0.0, right=0.0))
                    g = d + np.arange(1, 61) * 1e-3
                    am = float(np.max(np.interp(g, t_, amp_, left=0.0, right=0.0)))
                    if (d <= birth <= d + 0.06) or (ad > 0 and am > 2 * ad) or (ad <= 0 and am > 0):
                        Q.append(d)
                if Q:
                    Q = np.array(Q)
                    i0 = np.searchsorted(Q, tt - 0.15, 'left'); j0 = np.searchsorted(Q, tt + 0.02, 'right')
                    md = (j0 > i0) & remaining
                    cause[md] = 2; remaining &= ~md
        # 3 bass reverb/late
        if remaining.any() and len(bn):
            ie = np.clip(np.rint(tt * FSR).astype(int), 0, len(env) - 1)
            ie2 = np.clip(ie - 90, 0, len(env) - 1)
            for i in np.flatnonzero((be > tt.min() - 0.0) & (be <= tt.max())):
                win = remaining & (tt >= be[i]) & (tt < be[i] + 0.4)
                if not win.any():
                    continue
                pm = np.zeros(len(tt), bool); pm[win] = compat_any(f[win], bf[i])
                ok = pm & (env[ie] < bpk[i] * 10 ** (-15 / 20)) & (env[ie] >= bpk[i] * 10 ** (-50 / 20)) & (env[ie] <= env[ie2])
                info['late_pitch_only'] += float((a[pm & ~ok] ** 2).sum()); info['late_total'] += float((a[pm] ** 2).sum())
                cause[ok & remaining] = 3; remaining &= ~ok
        # 4 other instrument (MIDI)
        if remaining.any() and len(os_):
            for i in np.flatnonzero((os_ <= tt.max()) & (oe_ > tt.min())):
                win = remaining & (tt >= os_[i]) & (tt < oe_[i])
                if not win.any():
                    continue
                ok = np.zeros(len(tt), bool)
                for k in (1, 2, 3):
                    fk = f[win] / k
                    ok[win] |= (np.abs(cents(fk, of0[i])) <= 100) | (np.abs(cents(fk, 2 * of0[i])) <= 100)
                cause[ok] = 4; remaining &= ~ok
        cause[remaining & m] = 5
        comp[m] = 2 + cause[m]
        w2 = a[m] ** 2
        i = vidx[id(v)]
        st = vstat.setdefault(i, {})
        st['E'] = [float(w2[cause[m] == c].sum()) for c in range(1, 6)]
        store['f'].append(f[m]); store['w'].append(w2); store['c'].append(cause[m]); store['v'].append(np.full(int(m.sum()), i))
        return comp

    Y = render_multi(voices, dur + 0.3, fn, NC)
    y = Y[:, I_MIN:]
    e = lambda x: float(np.sum(x ** 2))
    out = dict(E_right_sa=e(y[0] + y[1]), E_wrong_sa=e(y[2:].sum(0)), E_nonsil=e(y[2]), E_sil=e(y[3:].sum(0)),
               E_cause=[e(y[3 + c]) for c in range(5)], nobass=nobass, n_voices=len(voices),
               n_sil_voices=int(sum(1 for v in voices if v.get('cls', 2) == 2)), info=info,
               vstat={str(k): v for k, v in vstat.items()}, secs=time.time() - t0)
    arr = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in store.items()}
    print('song', key, round(time.time() - t0, 1), flush=True)
    return key, out, arr


def wq(x, w, qs):
    o = np.argsort(x); x, w = x[o], w[o]; cw = np.cumsum(w) / w.sum()
    return [float(x[min(np.searchsorted(cw, q), len(x) - 1)]) for q in qs]


def report(res, arr):
    L = []
    P = lambda s='': L.append(s)
    R3R = r3_right(SONGS)
    nb = [k for k in SONGS if res[k]['nobass']]
    P(f'# plan16 V: core v1.5 silence wrong energy by cause -- {time.strftime("%Y-%m-%dT%H:%M:%S")}')
    P(f'units = wrong energy / R3 right energy (F), R3R pooled = {R3R:.4f}; no-bass songs = {nb}')
    for label, keys in (('all 10 songs', SONGS), ('without the 3 no-bass songs', [k for k in SONGS if k not in nb]), ('without Track00040', [k for k in SONGS if k != 'Track00040'])):
        tot_w = sum(res[k]['E_wrong_sa'] for k in keys) / R3R; sil = sum(res[k]['E_sil'] for k in keys) / R3R
        ca = [sum(res[k]['E_cause'][c] for k in keys) / R3R for c in range(5)]
        P(f'\n## {label}: total wrong_sa = {tot_w:.4f}; non-silence = {sum(res[k]["E_nonsil"] for k in keys) / R3R:.4f}; silence (rendered together) = {sil:.4f}; sum of 5 causes = {sum(ca):.4f}')
        P('cause | units | share of cause-sum % | share of total wrong %')
        for c in range(5):
            P(f'{CAUSES[c]} | {ca[c]:.4f} | {100 * ca[c] / max(sum(ca), 1e-12):.1f} | {100 * ca[c] / max(tot_w, 1e-12):.1f}')
    P('\n## per song (units = song energy / pooled R3R): silence total | causes 1..5')
    for k in SONGS:
        r = res[k]
        P(f'{k}{" (no bass)" if r["nobass"] else ""} | sil {r["E_sil"] / R3R:.4f} | ' + ' | '.join(f'{x / R3R:.4f}' for x in r['E_cause']) + f' | silence voices {r["n_sil_voices"]}/{r["n_voices"]}')
    P('\n## share of the voice lifetime in silence (no bass MIDI note sounding), silence voices carrying silence wrong energy; median per song')
    for k in SONGS:
        sh = [v['nobass_share'] for v in res[k]['vstat'].values() if 'E' in v and 'nobass_share' in v]
        P(f'{k} | n voices {len(sh)} | median share {np.median(sh):.3f}' if sh else f'{k} | none')
    allsh = [v['nobass_share'] for k in SONGS if not res[k]['nobass'] for v in res[k]['vstat'].values() if 'E' in v and 'nobass_share' in v]
    P(f'pooled (bass songs): n {len(allsh)}, median {np.median(allsh):.3f}, p10..p90 {np.percentile(allsh, 10):.3f}..{np.percentile(allsh, 90):.3f}')
    qs = [.1, .2, .3, .4, .5, .6, .7, .8, .9]
    for label, keys in (('all 10 songs', SONGS), ('bass songs only', [k for k in SONGS if k not in nb])):
        f = np.concatenate([arr[k]['f'] for k in keys]); w = np.concatenate([arr[k]['w'] for k in keys])
        c = np.concatenate([arr[k]['c'] for k in keys])
        P(f'\n## voice f deciles (Hz), silence sa-wrong samples, weight a^2 -- {label}')
        P('all causes: ' + ' '.join(f'{x:.1f}' for x in wq(f, w, qs)) + f'  (min {f.min():.1f}, max {f.max():.1f})')
        for cc in range(1, 6):
            mk = c == cc
            if mk.sum() > 20:
                P(f'cause {CAUSES[cc - 1]} (weight share {100 * w[mk].sum() / w.sum():.1f} %): ' + ' '.join(f'{x:.1f}' for x in wq(f[mk], w[mk], qs)))
        # distinct voices carrying 80 %
        vv = {}
        for k in keys:
            for a_, b_ in zip(arr[k]['v'], arr[k]['w']):
                pass
        per = []
        for k in keys:
            v_ = arr[k]['v'].astype(int); w_ = arr[k]['w']
            if len(v_):
                s = np.bincount(v_, weights=w_)
                per += list(s[s > 0])
        per = np.sort(np.array(per))[::-1]; cs = np.cumsum(per) / per.sum()
        n80 = int(np.searchsorted(cs, 0.8) + 1)
        nsil = sum(res[k]['n_sil_voices'] for k in keys)
        P(f'distinct voices carrying 80 % of silence wrong energy (a^2 proxy): {n80} of {len(per)} voices with wrong samples (silence-class voices total {nsil}); top-10 share {100 * cs[min(9, len(cs) - 1)]:.1f} %')
    P('\n## proxy (a^2) shares by cause, bass songs only')
    wsum = np.zeros(5)
    for k in SONGS:
        if res[k]['nobass']:
            continue
        for v in res[k]['vstat'].values():
            if 'E' in v:
                wsum += np.array(v['E'])
    P(' | '.join(f'{CAUSES[c]} {100 * wsum[c] / wsum.sum():.1f} %' for c in range(5)))
    li = sum(res[k]['info']['late_pitch_only'] for k in SONGS); lt = sum(res[k]['info']['late_total'] for k in SONGS)
    P(f'\n## info: cause-3 candidates (pitch-compatible within 400 ms after a bass note end, remaining after tests 1-2): a^2 weight failing the stem condition = {li:.3f} of {lt:.3f}')
    open(V_DIR / 'v_report.txt', 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        res = json.load(open(V_DIR / 'v_raw.json')); z = np.load(V_DIR / 'v_arrays.npz')
        arr = {k: dict(f=z[k + '_f'], w=z[k + '_w'], c=z[k + '_c'], v=z[k + '_v']) for k in SONGS}
        report(res, arr)
    else:
        t0 = time.time()
        with mp.get_context('fork').Pool(10) as pool:
            out = pool.map(one_song, SONGS)
        res = {k: o for k, o, _ in out}; arr = {k: a for k, _, a in out}
        json.dump(res, open(V_DIR / 'v_raw.json', 'w'), default=float)
        np.savez_compressed(V_DIR / 'v_arrays.npz', **{f'{k}_{n}': arr[k][n] for k in SONGS for n in ('f', 'w', 'c', 'v')})
        report(res, arr)
        print('done', round(time.time() - t0, 1))
