"""Q1: wrong-note energy (V6b) resolved in time against drum MIDI onsets, by voice episode, runtime-feature separation, and P1.
Definitions identical to research_core_xcheck.part_v6both (weight (A c sigma)^2 over state>0 voices, hops with tc>0.5, 'right' = within 50 cent of
0.5/1/2/3 x any sounding MIDI note of the track (drums included, bass MIDI also shifted by tp)). Variant 'c' excludes drum MIDI as notes."""
import json, sys, time
import numpy as np
import common16 as C
import research_core_xcheck as X

TW = [(0, 50), (50, 100), (100, 200)]      # ms after an onset
WINS = ['0-50', '50-100', '100-200', 'else']
out_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True); out_lines.append(s)


def since(on, t):
    if len(on) == 0:
        return np.full(len(t), np.inf)
    i = np.searchsorted(on, t, 'right') - 1
    return np.where(i >= 0, t - on[np.maximum(i, 0)], np.inf)


def win_idx(dtms):
    w = np.full(len(dtms), 3)
    w[dtms < 200] = 2; w[dtms < 100] = 1; w[dtms < 50] = 0
    return w


# ---------------------------------------------------------------------------------------------- build voice-hop records, core
def core_records(name, rf):
    tr = C.get_core(name)
    d, hop, tc = X.hops_of(tr)
    raw = tr.reshape(-1, 8, 22)
    H = len(tc)
    rec = []
    # per-hop target sets and lowest sounding note (variants a and c)
    fnA = [None] * H; fnC = [None] * H
    for h in range(H):
        if tc[h] > 0.5:
            fnA[h] = C.targets_at(rf, tc[h], 'a'); fnC[h] = C.targets_at(rf, tc[h], 'c')
    stt = d['state']; w_all = np.where(stt > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
    # episodes: ON runs per voice id
    ep_id = np.full((H, 8), -1); age = np.full((H, 8), np.nan); slope8 = np.full((H, 8), np.nan); adrop = np.full((H, 8), np.nan)
    voices = np.unique(d['voice'][stt > 0])
    eps = []
    for v in voices:
        hs, js = np.nonzero((d['voice'] == v) & (stt > 0))
        o = np.argsort(hs); hs, js = hs[o], js[o]
        # ON hops of this voice
        on = stt[hs, js] == X.ON
        run = []
        def close(run):
            if run:
                eps.append((int(v), run))
        for k in range(len(hs)):
            if on[k] and (not run or hs[k] == run[-1][0] + 1):
                run.append((hs[k], js[k]))
            else:
                close(run); run = [(hs[k], js[k])] if on[k] else []
        close(run)
    for e, (v, run) in enumerate(eps):
        hh = np.array([r[0] for r in run]); jj = np.array([r[1] for r in run])
        A = d['A'][hh, jj]; t = tc[hh]
        la = 20 * np.log10(np.maximum(A, 1e-12))
        for q in range(len(run)):
            ep_id[hh[q], jj[q]] = e; age[hh[q], jj[q]] = q * C.HOPMS
            lo = max(0, q - 7)
            if q - lo >= 2:
                slope8[hh[q], jj[q]] = np.polyfit(t[lo:q + 1], la[lo:q + 1], 1)[0]
            adrop[hh[q], jj[q]] = la[q] - la[:q + 1].max()
    # records
    for h in range(H):
        if tc[h] <= 0.5:
            continue
        sel = np.flatnonzero((w_all[h] > 0) & (stt[h] > 0))
        if not len(sel):
            continue
        on_sel = np.flatnonzero(stt[h] == X.ON)
        amax = d['A'][h][on_sel].max() if len(on_sel) else np.nan
        for j in sel:
            f = d['fosc'][h][j]
            r = {}
            for var, fn in (('a', fnA[h]), ('c', fnC[h])):
                tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
                r['wrong_' + var] = bool((not len(tgt)) or np.min(C.cents(f, tgt)) > 50)
            fn = fnA[h]
            r['below_lowest'] = bool(len(fn) and f < fn.min() * 2 ** (-50 / 1200)); r['no_note'] = not len(fn)
            r['below_half_lowest'] = bool(len(fn) and f < 0.5 * fn.min() * 2 ** (-50 / 1200))
            row = raw[h, j]
            others = [d['fosc'][h][q] for q in on_sel if q != j]
            rec.append((h, j, tc[h], int(d['voice'][h][j]), int(stt[h][j]), d['coast'][h][j], f, d['ftr'][h][j], row[X.F_DFDT], d['A'][h][j], d['c'][h][j],
                        d['sig'][h][j], d['snr'][h][j], row[X.F_NP], row[X.F_PROM], row[X.F_RAW], row[X.F_RES], d['sub'][h][j], w_all[h][j],
                        r['wrong_a'], r['wrong_c'], r['below_lowest'], r['no_note'], r['below_half_lowest'], ep_id[h][j], age[h][j], slope8[h][j], adrop[h][j],
                        20 * np.log10(max(d['A'][h][j], 1e-12) / max(amax, 1e-12)) if np.isfinite(amax) else np.nan,
                        (f / min(others)) if others else np.nan, float(f <= min(others + [f + 1])), d['track'][h][j]))
    names = ['h', 'j', 'tc', 'vid', 'state', 'coast', 'f', 'ftr', 'dfdt', 'A', 'c', 'sig', 'snr', 'np', 'prom', 'raw', 'res', 'sub', 'w', 'wrong_a', 'wrong_c',
             'below', 'no_note', 'below_half', 'ep', 'age', 'slope8', 'adrop', 'A_rel_db', 'f_over_minother', 'is_lowest', 'trk']
    arr = {n: np.array([r[i] for r in rec], float) for i, n in enumerate(names)}
    for k in list(arr):
        if k in ('wrong_a', 'wrong_c', 'below', 'no_note', 'below_half'):
            arr[k] = arr[k] > 0.5
    arr['absdfdt_rel'] = np.abs(arr['dfdt']) / arr['f']
    arr['foff_rel'] = np.abs(arr['f'] - arr['ftr']) / np.maximum(arr['ftr'], 1)
    arr['dt_kick'] = since(rf['kick_on'], arr['tc']) * 1000; arr['dt_drum'] = since(rf['drum_on'], arr['tc']) * 1000
    # episode table
    E = []
    for e, (v, run) in enumerate(eps):
        hh = np.array([r[0] for r in run]); jj = np.array([r[1] for r in run])
        t = tc[hh]
        if t[-1] <= 0.5:
            continue
        f = d['fosc'][hh, jj]; A = d['A'][hh, jj]; df = np.abs(raw[hh, jj, X.F_DFDT]) / f
        n50 = max(1, int(round(50 / C.HOPMS)))
        la = 20 * np.log10(np.maximum(A, 1e-12))
        sl = np.polyfit(t, la, 1)[0] if len(t) >= 3 else np.nan
        E.append(dict(e=e, vid=v, n=len(run), life_ms=len(run) * C.HOPMS, t0=t[0], f_med=float(np.median(f)), df_med50=float(np.median(df[:n50])), df_max50=float(df[:n50].max()),
                      slope=float(sl), sub_frac=float(np.mean(d['sub'][hh, jj] > .5)), A_first_db=float(la[0]), A_max_db=float(la.max()),
                      dt_birth_drum=float(since(rf['drum_on'], t[:1])[0] * 1000), dt_birth_kick=float(since(rf['kick_on'], t[:1])[0] * 1000)))
    return arr, E


def weights_split(arr, var='a'):
    wr = arr['wrong_' + var]; w = arr['w']
    return w[wr].sum(), w[~wr].sum()


def window_table(arr, on_key, var='a'):
    """fractions of wrong / right weight (and of hop count) per window after the onset"""
    wi = win_idx(arr[on_key])
    wr = arr['wrong_' + var]; w = arr['w']
    res = {}
    for k, nm in enumerate(WINS):
        m = wi == k
        res[nm] = dict(wrong=float(w[m & wr].sum()), right=float(w[m & ~wr].sum()), n_voice_hops=int(m.sum()))
    return res


# ---------------------------------------------------------------------------------------------- P1 records
def p1_records(name, rf):
    tc1, ts = C.get_p1(name)
    H, T_, _ = ts.shape
    valid = ts[:, :, 1] > 0
    fade = np.where(valid, ts[:, :, 7], 0.0); a = np.where(valid, ts[:, :, 4], 0.0); f = np.where(valid, ts[:, :, 2], 0.0)
    w = (a * fade) ** 2
    ident = ts[:, :, 0] + 65536 * ts[:, :, 13]
    rec = []
    for h in range(H):
        if tc1[h] <= 0.5:
            continue
        sel = np.flatnonzero(valid[h] & (w[h] > 0))
        if not len(sel):
            continue
        fnA = C.targets_at(rf, tc1[h], 'a'); fnC = C.targets_at(rf, tc1[h], 'c')
        for j in sel:
            wa = (not len(fnA)) or np.min(C.cents(f[h][j], np.outer(fnA, [.5, 1, 2, 3]).ravel())) > 50
            wc = (not len(fnC)) or np.min(C.cents(f[h][j], np.outer(fnC, [.5, 1, 2, 3]).ravel())) > 50
            rec.append((h, j, tc1[h], ident[h][j], f[h][j], ts[h][j][3], a[h][j], fade[h][j], ts[h][j][6], ts[h][j][12], ts[h][j][8], ts[h][j][9], w[h][j], wa, wc,
                        len(fnA) > 0 and f[h][j] < fnA.min() * 2 ** (-50 / 1200)))
    names = ['h', 'j', 'tc', 'tid', 'f', 'dfdt', 'a', 'fade', 'res', 'raw', 'age', 'missing', 'w', 'wrong_a', 'wrong_c', 'below']
    arr = {n: np.array([r[i] for r in rec], float) for i, n in enumerate(names)}
    for k in ('wrong_a', 'wrong_c', 'below'):
        arr[k] = arr[k] > .5
    arr['dt_kick'] = since(rf['kick_on'], arr['tc']) * 1000; arr['dt_drum'] = since(rf['drum_on'], arr['tc']) * 1000
    # P1 episodes = contiguous presence of one track id (state>0)
    E = []
    tid = ident
    for t_ in np.unique(tid[valid]):
        hs, js = np.nonzero(valid & (tid == t_)); o = np.argsort(hs); hs, js = hs[o], js[o]
        starts = np.r_[0, np.flatnonzero(np.diff(hs) != 1) + 1, len(hs)]
        for s0, s1 in zip(starts[:-1], starts[1:]):
            hh, jj = hs[s0:s1], js[s0:s1]; t = tc1[hh]
            if t[-1] <= .5:
                continue
            ff = f[hh, jj]; la = 20 * np.log10(np.maximum(a[hh, jj], 1e-12)); fd = fade[hh, jj]
            n50 = max(1, int(round(50 / C.HOPMS)))
            wgt = (a[hh, jj] * fd) ** 2
            E.append(dict(tid=float(t_), n=len(hh), life_ms=len(hh) * C.HOPMS, t0=float(t[0]), f_med=float(np.median(ff)), df_med50=float(np.median(np.abs(ts[hh, jj, 3][:n50]) / ff[:n50])),
                          slope=float(np.polyfit(t, la, 1)[0]) if len(t) >= 3 else np.nan, fade_max=float(fd.max()), fade_mean=float(fd.mean()),
                          w_sum=float(wgt.sum()), dt_birth_drum=float(since(rf['drum_on'], t[:1])[0] * 1000), dt_birth_kick=float(since(rf['kick_on'], t[:1])[0] * 1000)))
    return arr, E, (tc1, ts, valid, fade, a, f, ident)


# ---------------------------------------------------------------------------------------------- separation by threshold
def best_thresholds(v, w, wrong, label_min_right=(0.05, 0.10, 0.20)):
    m = np.isfinite(v) & (w > 0)
    W_w = w[wrong].sum(); W_r = w[~wrong].sum()
    out = []
    for sign in (+1, -1):                      # remove records with sign*v >= thr
        s = sign * v[m]; ww = w[m]; wr = wrong[m]
        o = np.argsort(-s, kind='stable'); s = s[o]; ww = ww[o]; wr = wr[o]
        cw = np.cumsum(np.where(wr, ww, 0.0)); cr = np.cumsum(np.where(~wr, ww, 0.0))
        # thresholds only between distinct values
        last = np.r_[s[1:] != s[:-1], True]
        cw, cr, ss = cw[last], cr[last], s[last]
        J = cw / W_w - cr / W_r
        k = int(np.argmax(J))
        best = dict(sign=sign, thr=float(sign * ss[k]), J=float(J[k]), wrong_removed=float(cw[k] / W_w), right_removed=float(cr[k] / W_r))
        fixed = {}
        for lim in label_min_right:
            ok = np.flatnonzero(cr / W_r <= lim)
            if len(ok):
                q = ok[np.argmax(cw[ok])]; fixed[f'{lim:.2f}'] = dict(thr=float(sign * ss[q]), wrong_removed=float(cw[q] / W_w), right_removed=float(cr[q] / W_r))
        best['at_right_removed_le'] = fixed
        out.append(best)
    return max(out, key=lambda b: b['J'])


def wmed(v, w):
    q = C.wquant(v, w, (.1, .5, .9)); return [round(x, 3) for x in q]


def main():
    A = {}; EP = {}; PA = {}; PE = {}; PX = {}
    for name in C.TRACKS:
        t0 = time.time()
        rf = C.ref(name)
        P(f'== {name}: drum onsets {len(rf["drum_on"])}, kick onsets {len(rf["kick_on"])}, drum stems {rf["drum_ids"]}, drum pitches {dict(list(rf["drum_pitch_counts"].items())[:8])}')
        A[name], EP[name] = core_records(name, rf)
        PA[name], PE[name], PX[name] = p1_records(name, rf)
        P(f'   core voice-hops {len(A[name]["w"])}, episodes {len(EP[name])}; P1 voice-hops {len(PA[name]["w"])}, episodes {len(PE[name])}  ({time.time()-t0:.0f}s)')
    cat = lambda D, k: np.concatenate([D[n][k] for n in C.TRACKS])
    res = {}

    # ------------------------------------------------------------------ baseline reproduction
    P('\n### Baseline: wrong-note share (V6b weight), tc>0.5 s, variant a (spec/suite definition) and c (drum MIDI excluded as notes)')
    P('| track | core wrong% (a) | P1 wrong% (a) | core wrong% (c) | P1 wrong% (c) | core W_tot | P1 W_tot |')
    P('|---|---|---|---|---|---|---|')
    tot = dict(ca=[0, 0], pa=[0, 0], cc=[0, 0], pc=[0, 0])
    for n in C.TRACKS:
        a, p = A[n], PA[n]
        w_a = a['w'][a['wrong_a']].sum(), a['w'].sum(); w_c = a['w'][a['wrong_c']].sum(), a['w'].sum()
        p_a = p['w'][p['wrong_a']].sum(), p['w'].sum(); p_c = p['w'][p['wrong_c']].sum(), p['w'].sum()
        for k, v in (('ca', w_a), ('cc', w_c), ('pa', p_a), ('pc', p_c)):
            tot[k][0] += v[0]; tot[k][1] += v[1]
        P(f'| {n} | {100*w_a[0]/max(w_a[1],1e-30):.1f} | {100*p_a[0]/max(p_a[1],1e-30):.1f} | {100*w_c[0]/max(w_c[1],1e-30):.1f} | {100*p_c[0]/max(p_c[1],1e-30):.1f} | {w_a[1]:.3g} | {p_a[1]:.3g} |')
    P(f'| POOLED | {100*tot["ca"][0]/tot["ca"][1]:.2f} | {100*tot["pa"][0]/tot["pa"][1]:.2f} | {100*tot["cc"][0]/tot["cc"][1]:.2f} | {100*tot["pc"][0]/tot["pc"][1]:.2f} | | |')
    res['baseline'] = {k: v[0] / v[1] for k, v in tot.items()}
    P('(reference: acceptance report core 34.5 %, P1 17.8 %)')
    # state / sub / below breakdown of core wrong weight
    a = {k: cat(A, k) for k in A[C.TRACKS[0]]}
    ww = a['w'][a['wrong_a']].sum()
    P('\ncore wrong weight by state: ' + ', '.join(f'{nm} {100*a["w"][a["wrong_a"] & (a["state"]==s)].sum()/ww:.1f}%' for nm, s in (('CAND', 1), ('ON', 2), ('REL', 3))))
    P(f'core wrong weight: subordinate {100*a["w"][a["wrong_a"] & (a["sub"]>.5)].sum()/ww:.1f}%, coasting {100*a["w"][a["wrong_a"] & (a["coast"]>.5)].sum()/ww:.1f}%, '
      f'below (lowest sounding note -50c) {100*a["w"][a["wrong_a"] & a["below"]].sum()/ww:.1f}%, below half-lowest {100*a["w"][a["wrong_a"] & a["below_half"]].sum()/ww:.1f}%, no sounding note {100*a["w"][a["wrong_a"] & a["no_note"]].sum()/ww:.1f}%')

    # ------------------------------------------------------------------ (a) windows
    for var in ('a', 'c'):
        for key, lab in (('dt_kick', 'kick (GM 35/36)'), ('dt_drum', 'any drum onset')):
            P(f'\n### Q1a [{var}] fraction of WRONG and RIGHT weight in hops 0-50 / 50-100 / 100-200 ms after the latest {lab} onset, else  (core vs P1)')
            P('| scope | system | wrong 0-50 | 50-100 | 100-200 | else | right 0-50 | 50-100 | 100-200 | else | wrong share inside 0-200 | wrong share else |')
            P('|---|---|---|---|---|---|---|---|---|---|---|---|')
            for scope in C.TRACKS + ['POOLED']:
                for sysn, D in (('core', A), ('P1', PA)):
                    if scope == 'POOLED':
                        arr = {k: np.concatenate([D[n][k] for n in C.TRACKS]) for k in D[C.TRACKS[0]]}
                    else:
                        arr = D[scope]
                    t = window_table(arr, key, var)
                    W = sum(v['wrong'] for v in t.values()); R = sum(v['right'] for v in t.values())
                    ins_w = sum(t[k]['wrong'] for k in WINS[:3]); ins_r = sum(t[k]['right'] for k in WINS[:3])
                    P(f'| {scope} | {sysn} | ' + ' | '.join(f'{100*t[k]["wrong"]/max(W,1e-30):.1f}%' for k in WINS) + ' | ' + ' | '.join(f'{100*t[k]["right"]/max(R,1e-30):.1f}%' for k in WINS) +
                      f' | {100*ins_w/max(ins_w+ins_r,1e-30):.1f}% | {100*t["else"]["wrong"]/max(t["else"]["wrong"]+t["else"]["right"],1e-30):.1f}% |')
                    if scope == 'POOLED':
                        res[f'windows_{var}_{key}_{sysn}'] = t
    # pooled without the outlier Track00024 (97 % wrong in both systems)
    P('\n### pooled WITHOUT Track00024 (kick windows, variant a): wrong 0-50 / 50-100 / 100-200 / else | right 0-50 / 50-100 / 100-200 / else | overall wrong share')
    for sysn, D in (('core', A), ('P1', PA)):
        arr = {k: np.concatenate([D[n][k] for n in C.TRACKS if n != 'Track00024']) for k in D[C.TRACKS[0]]}
        t = window_table(arr, 'dt_kick', 'a')
        W = sum(v['wrong'] for v in t.values()); R = sum(v['right'] for v in t.values())
        P(f'  {sysn}: ' + ' / '.join(f'{100*t[k]["wrong"]/W:.1f}%' for k in WINS) + ' | ' + ' / '.join(f'{100*t[k]["right"]/R:.1f}%' for k in WINS) + f' | wrong share {100*W/(W+R):.1f}%')
    # time baseline: fraction of all hops (tc>0.5) in each window
    P('\n### time baseline: fraction of hop-time (tc>0.5 s, all 10 tracks) within 0-50/50-100/100-200 ms after a kick / any drum onset')
    fr = {}
    for key, lab in (('kick_on', 'kick'), ('drum_on', 'drum')):
        cnt = np.zeros(4); n_all = 0
        for n in C.TRACKS:
            rf = C.ref(n); tcg = 0.5 + np.arange(0, 29.5, 16 / 3000)
            wi = win_idx(since(rf[key], tcg) * 1000)
            for k in range(4):
                cnt[k] += (wi == k).sum()
            n_all += len(tcg)
        fr[lab] = (cnt / n_all).tolist(); P(f'{lab}: ' + ', '.join(f'{WINS[k]} {100*cnt[k]/n_all:.1f}%' for k in range(4)))
    res['time_baseline'] = fr

    # ------------------------------------------------------------------ (b) episodes
    P('\n### Q1b voice episodes (core, continuous ON run of one voice id; non-ON weight reported separately)')
    on = a['state'] == 2
    P(f'wrong weight in ON hops {100*a["w"][a["wrong_a"] & on].sum()/ww:.1f}% (rest CAND/REL); episode id missing for ON hops: {int((a["ep"][on]<0).sum())}')
    epl = []
    for n in C.TRACKS:
        for e in EP[n]:
            e = dict(e); e['track'] = n
            epl.append(e)
    # episode weights from hop records
    ew = {}
    for n in C.TRACKS:
        r = A[n]; m = (r['ep'] >= 0)
        for e_ in np.unique(r['ep'][m]):
            mm = m & (r['ep'] == e_)
            ew[(n, int(e_))] = (r['w'][mm & r['wrong_a']].sum(), r['w'][mm & ~r['wrong_a']].sum())
    Ww = np.array([ew.get((e['track'], e['e']), (0, 0))[0] for e in epl]); Wr = np.array([ew.get((e['track'], e['e']), (0, 0))[1] for e in epl])
    P(f'episodes (ON, ending after 0.5 s): {len(epl)}; with wrong weight: {(Ww>0).sum()}; total ON wrong weight {Ww.sum():.4g}, right {Wr.sum():.4g}')
    feats = [('life_ms', 'lifetime ms'), ('f_med', 'median f_osc Hz'), ('df_med50', 'median |df/dt|/f (1/s) first 50 ms'), ('df_max50', 'max |df/dt|/f (1/s) first 50 ms'),
             ('slope', 'A slope dB/s over episode'), ('dt_birth_drum', 'ms from preceding drum onset to birth'), ('dt_birth_kick', 'ms from preceding kick onset to birth'),
             ('sub_frac', 'subordinate fraction of hops')]
    P('\nweighted quantiles (10/50/90 %) of episode features, weights = episode wrong weight vs episode right weight (pooled over 10 tracks)')
    P('| feature | WRONG-weighted p10 / median / p90 | RIGHT-weighted p10 / median / p90 |')
    P('|---|---|---|')
    for k, lab in feats:
        v = np.array([e[k] for e in epl], float)
        P(f'| {lab} | {wmed(v, Ww)} | {wmed(v, Wr)} |')
        res[f'ep_{k}'] = dict(wrong=wmed(v, Ww), right=wmed(v, Wr))
    P('\nhop-level: weight by ON-episode age (ms since the voice became ON; non-ON hops separate): wrong share of weight | share of all wrong | share of all right')
    ag = a['age']; tw_, tr_ = a['w'][a['wrong_a']].sum(), a['w'][~a['wrong_a']].sum()
    for lo, hi in ((0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 1e9)):
        m = (a['state'] == 2) & (ag >= lo) & (ag < hi)
        P(f'  age {lo}-{hi if hi<1e8 else "inf"} ms: local wrong share {100*a["w"][m & a["wrong_a"]].sum()/max(a["w"][m].sum(),1e-30):.1f}% | {100*a["w"][m & a["wrong_a"]].sum()/tw_:.1f}% of wrong | {100*a["w"][m & ~a["wrong_a"]].sum()/tr_:.1f}% of right')
    m = a['state'] != 2
    P(f'  non-ON (CAND/REL): local wrong share {100*a["w"][m & a["wrong_a"]].sum()/max(a["w"][m].sum(),1e-30):.1f}% | {100*a["w"][m & a["wrong_a"]].sum()/tw_:.1f}% of wrong | {100*a["w"][m & ~a["wrong_a"]].sum()/tr_:.1f}% of right')
    P(f'  coasting ON/REL voices (track lost, coast>0): local wrong share {100*a["w"][(a["coast"]>.5) & a["wrong_a"]].sum()/max(a["w"][a["coast"]>.5].sum(),1e-30):.1f}% | {100*a["w"][(a["coast"]>.5) & a["wrong_a"]].sum()/tw_:.1f}% of wrong | {100*a["w"][(a["coast"]>.5) & ~a["wrong_a"]].sum()/tr_:.1f}% of right')
    # weight shares by life and by subordinate and by below-lowest (hop-level)
    life = np.array([e['life_ms'] for e in epl])
    P('\nshare of ON weight by episode lifetime class (wrong-weight share | right-weight share):')
    for lo, hi in ((0, 50), (50, 100), (100, 250), (250, 1000), (1000, 1e9)):
        m = (life >= lo) & (life < hi)
        P(f'  life {lo}-{hi if hi<1e8 else "inf"} ms: wrong {100*Ww[m].sum()/Ww.sum():.1f}% | right {100*Wr[m].sum()/Wr.sum():.1f}%   (episodes {m.sum()}, local wrong share {100*Ww[m].sum()/max(Ww[m].sum()+Wr[m].sum(),1e-30):.1f}%)')
    sub = np.array([e['sub_frac'] for e in epl])
    P(f'  subordinate episodes (>=50% hops): wrong {100*Ww[sub>=.5].sum()/Ww.sum():.1f}% | right {100*Wr[sub>=.5].sum()/Wr.sum():.1f}%')
    # below lowest note (hop weighted)
    for lab, key in (('f_osc below lowest sounding MIDI note -50c', 'below'), ('f_osc below HALF the lowest note -50c', 'below_half'), ('no MIDI note sounding at all', 'no_note')):
        P(f'  {lab}: wrong weight {100*a["w"][a["wrong_a"] & a[key]].sum()/ww:.1f}% | right weight {100*a["w"][~a["wrong_a"] & a[key]].sum()/a["w"][~a["wrong_a"]].sum():.1f}%  (local wrong share {100*a["w"][a["wrong_a"] & a[key]].sum()/max(a["w"][a[key]].sum(),1e-30):.1f}%)')
    # episode-level decay vs attack lag
    dtb = np.array([e['dt_birth_drum'] for e in epl])
    P('\nshare of ON weight by time from the preceding drum onset to episode BIRTH (wrong | right | local wrong share):')
    for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 250), (250, 1e9)):
        m = (dtb >= lo) & (dtb < hi)
        P(f'  {lo}-{hi if hi<1e8 else "inf"} ms: wrong {100*Ww[m].sum()/Ww.sum():.1f}% | right {100*Wr[m].sum()/Wr.sum():.1f}% | local {100*Ww[m].sum()/max(Ww[m].sum()+Wr[m].sum(),1e-30):.1f}%  (episodes {m.sum()})')
    # episode-level 'below the lowest sounding MIDI note' (majority of the episode's hops)
    below_ep = []
    for e in epl:
        r = A[e['track']]; mm = r['ep'] == e['e']
        below_ep.append(np.mean(r['below'][mm]) if mm.any() else np.nan)
    below_ep = np.array(below_ep)
    bm = below_ep >= .5
    P(f'\nepisode level: episodes whose f_osc is below the lowest sounding MIDI note (-50 c) for >=50% of their hops: {bm.sum()}/{len(bm)} episodes; wrong-weight share {100*Ww[bm].sum()/Ww.sum():.1f}%, right-weight share {100*Wr[bm].sum()/Wr.sum():.1f}%')
    # per-track summary of episodes
    P('\nper track: median lifetime (wrong-weighted | right-weighted) ms; wrong share of ON weight')
    for n in C.TRACKS:
        m = np.array([e['track'] == n for e in epl])
        v = life[m]
        P(f'  {n}: wrong-weighted median life {wmed(v, Ww[m])[1]} | right {wmed(v, Wr[m])[1]}; ON wrong share {100*Ww[m].sum()/max(Ww[m].sum()+Wr[m].sum(),1e-30):.1f}%')
    # top episodes by wrong weight
    P('\ntop 15 episodes by wrong weight (pooled):')
    for i in np.argsort(-Ww)[:15]:
        e = epl[i]
        P(f'  {e["track"]} t0={e["t0"]:.3f}s life={e["life_ms"]:.0f}ms f={e["f_med"]:.1f}Hz df50max={e["df_max50"]:.2f}/s slope={e["slope"]:.1f}dB/s dt_drum={e["dt_birth_drum"]:.0f}ms sub={e["sub_frac"]:.2f}  Wwrong={Ww[i]:.3g} ({100*Ww[i]/Ww.sum():.1f}%) Wright={Wr[i]:.3g}')

    # ------------------------------------------------------------------ separation by runtime features (hop level, causal)
    P('\n### Q1b runtime-observable separation (hop-level, weight w=(A c sigma)^2, all voice-hops, states CAND/ON/REL). "remove" = silence the voice-hop.')
    cand_feats = ['state', 'age', 'f', 'absdfdt_rel', 'foff_rel', 'snr', 'np', 'prom', 'raw', 'res', 'c', 'sig', 'sub', 'coast', 'slope8', 'adrop', 'A_rel_db', 'f_over_minother', 'is_lowest']
    sep = {}
    wr = a['wrong_a']; w = a['w']
    W_w, W_r = w[wr].sum(), w[~wr].sum()
    rows = []
    for k in cand_feats:
        v = a[k].astype(float).copy()
        if k == 'age':
            v = np.where(a['state'] == 2, v, np.nan)
        b = best_thresholds(v, w, wr)
        rows.append((k, b))
    rows.sort(key=lambda r: -r[1]['J'])
    P('| feature | rule (remove if) | wrong removed | right removed | J | best wrong removed with right removed <=5% / 10% / 20% |')
    P('|---|---|---|---|---|---|')
    for k, b in rows:
        rule = f'{k} {">=" if b["sign"]>0 else "<="} {b["thr"]:.4g}'
        fx = ' / '.join(f'{100*b["at_right_removed_le"][q]["wrong_removed"]:.0f}% (thr {b["at_right_removed_le"][q]["thr"]:.3g})' if q in b['at_right_removed_le'] else 'n/a' for q in ('0.05', '0.10', '0.20'))
        P(f'| {k} | {rule} | {100*b["wrong_removed"]:.1f}% | {100*b["right_removed"]:.1f}% | {b["J"]:.3f} | {fx} |')
    sep['hop_level'] = {k: b for k, b in rows}
    top3 = [k for k, _ in rows[:3]]
    P('top-3 by J: ' + ', '.join(top3))
    # resulting wrong share after removing at the best thresholds (each alone)
    for k, b in rows[:5]:
        v = a[k].astype(float).copy()
        if k == 'age':
            v = np.where(a['state'] == 2, v, np.nan)
        rm = np.isfinite(v) & ((b['sign'] * v) >= b['sign'] * b['thr'] - 1e-12)
        newW = w[wr & ~rm].sum(); newT = w[~rm].sum()
        P(f'  {k}: wrong share after removal {100*newW/newT:.1f}% (from {100*W_w/(W_w+W_r):.1f}%), total weight kept {100*newT/(W_w+W_r):.1f}%')
    # episode-level (non causal) feature thresholds: lifetime
    for k, lab in (('life_ms', 'lifetime'), ('df_max50', 'max |df/dt|/f first 50 ms'), ('dt_birth_drum', 'dt from drum to birth')):
        v = np.array([e[k] for e in epl], float)
        b = best_thresholds(v, Ww + Wr, np.zeros(len(v), bool)) if False else None
    # same on episode level by weights: remove whole episodes
    P('\nepisode-level (whole-episode removal; lifetime is not observable at birth, so this is diagnostic only):')
    for k, lab in (('life_ms', 'lifetime ms'), ('df_max50', 'max |df/dt|/f first 50 ms'), ('df_med50', 'median |df/dt|/f first 50 ms'), ('slope', 'A slope dB/s'), ('dt_birth_drum', 'ms birth after drum'), ('f_med', 'median f')):
        v = np.array([e[k] for e in epl], float)
        m = np.isfinite(v)
        best = None
        for sign in (1, -1):
            s = sign * v[m]; o = np.argsort(-s); cw = np.cumsum(Ww[m][o]) / Ww.sum(); cr = np.cumsum(Wr[m][o]) / Wr.sum(); J = cw - cr; q = int(np.argmax(J))
            if best is None or J[q] > best[0]:
                best = (J[q], sign, sign * s[o][q], cw[q], cr[q])
        P(f'  {lab}: remove if {"<=" if best[1]<0 else ">="} {best[2]:.4g}: wrong removed {100*best[3]:.1f}%, right removed {100*best[4]:.1f}% (J {best[0]:.3f})')
        sep['episode_' + k] = dict(thr=float(best[2]), sign=int(best[1]), wrong_removed=float(best[3]), right_removed=float(best[4]))
    res['separation'] = sep

    # ------------------------------------------------------------------ (c) P1
    P('\n### Q1c P1 (algo 6): voices = tracks with state>0, weight (a*fade)^2, right/wrong as for the core')
    p = {k: cat(PA, k) for k in PA[C.TRACKS[0]]}
    pw = p['w'][p['wrong_a']].sum(); pt = p['w'].sum()
    P(f'P1 wrong share {100*pw/pt:.2f}%; wrong weight in tracks with fade>=0.5: {100*p["w"][p["wrong_a"] & (p["fade"]>=.5)].sum()/pw:.1f}%; fade<0.5: {100*p["w"][p["wrong_a"] & (p["fade"]<.5)].sum()/pw:.1f}%; below lowest note: {100*p["w"][p["wrong_a"] & p["below"]].sum()/pw:.1f}%')
    pe = []
    for n in C.TRACKS:
        for e in PE[n]:
            e = dict(e); e['track'] = n; pe.append(e)
    # P1 episode weights per (track,tid)
    pew = {}
    for n in C.TRACKS:
        r = PA[n]
        for t_ in np.unique(r['tid']):
            m = r['tid'] == t_
            pew[(n, float(t_))] = (r['w'][m & r['wrong_a']].sum(), r['w'][m & ~r['wrong_a']].sum())
    # note: tid runs may be split into several episodes (re-use unlikely): attribute to first by simple approach
    seen = set(); PWw = []; PWr = []
    for e in pe:
        key = (e['track'], e['tid'])
        if key in seen:
            PWw.append(0.0); PWr.append(0.0); continue
        seen.add(key); a_, b_ = pew.get(key, (0, 0)); PWw.append(a_); PWr.append(b_)
    PWw = np.array(PWw); PWr = np.array(PWr)
    P('| feature | P1 WRONG-weighted p10 / median / p90 | P1 RIGHT-weighted p10 / median / p90 |')
    P('|---|---|---|')
    for k, lab in (('life_ms', 'track lifetime ms'), ('f_med', 'median f Hz'), ('df_med50', 'median |dfdt|/f first 50 ms (dfdt units of the trace)'), ('slope', 'A slope dB/s'),
                   ('dt_birth_drum', 'ms birth after drum'), ('dt_birth_kick', 'ms birth after kick'), ('fade_max', 'max fade'), ('fade_mean', 'mean fade')):
        v = np.array([e[k] for e in pe], float)
        P(f'| {lab} | {wmed(v, PWw)} | {wmed(v, PWr)} |')
    # P1 windows already printed. P1 hop-level separation
    P('\nP1 hop-level separation (remove track-hops):')
    pw_, pr_ = p['w'][p['wrong_a']].sum(), p['w'][~p['wrong_a']].sum()
    prow = []
    for k in ('fade', 'res', 'raw', 'age', 'missing', 'f', 'dfdt'):
        b = best_thresholds(p[k].astype(float), p['w'], p['wrong_a'])
        prow.append((k, b))
    prow.sort(key=lambda r: -r[1]['J'])
    for k, b in prow:
        P(f'  {k} {">=" if b["sign"]>0 else "<="} {b["thr"]:.4g}: wrong removed {100*b["wrong_removed"]:.1f}%, right removed {100*b["right_removed"]:.1f}%, J {b["J"]:.3f}')
    res['p1_separation'] = {k: b for k, b in prow}

    # ------------------------------------------------------------------ what P1's fit gate removed: match core voice-hops to P1 tracks
    P('\n### Q1c-2 what P1\'s gate removed: each core voice-hop (state>0, w>0) matched to the P1 track nearest in time (same hop grid) within 3 % of f_osc')
    cats = ['no P1 track with that id (core voice coasting or track gone)', 'P1 track, fade<0.1', 'P1 track, 0.1<=fade<0.5', 'P1 track, fade>=0.5']
    tabW = {c: [0.0, 0.0] for c in cats}
    tabByRes = {'fade<0.5 & residual>-15 (fit failing)': [0.0, 0.0], 'fade<0.5 & residual<=-15': [0.0, 0.0]}
    keep_mask = []; chosen_fade = []
    n_noid_coast = [0.0, 0.0, 0.0, 0.0]   # [wrong, right] weight of 'no id' voices that are coasting / not coasting
    for n in C.TRACKS:
        tc1, ts, valid, fade, aa, ff, ident = PX[n]
        r = A[n]
        idx = np.clip(np.searchsorted(tc1, r['tc']), 1, len(tc1) - 1)
        idx = np.where(np.abs(tc1[idx - 1] - r['tc']) <= np.abs(tc1[idx] - r['tc']), idx - 1, idx)
        for i in range(len(r['tc'])):
            h1 = idx[i]
            cand_ = np.flatnonzero(valid[h1] & (ident[h1] == r['trk'][i]))      # exact tracker id (same tracker in both algorithms)
            if len(cand_):
                j1 = cand_[0]
                fd = fade[h1][j1]
                c_ = cats[1] if fd < .1 else cats[2] if fd < .5 else cats[3]
                if fd < .5:
                    k_ = 'fade<0.5 & residual>-15 (fit failing)' if ts[h1][j1][6] > -15 else 'fade<0.5 & residual<=-15'
                    tabByRes[k_][0 if r['wrong_a'][i] else 1] += r['w'][i]
                chosen_fade.append(fd)
            else:
                c_ = cats[0]; chosen_fade.append(np.nan)
                n_noid_coast[(0 if r['wrong_a'][i] else 1) + (2 if r['coast'][i] > .5 else 0)] += r['w'][i]
            tabW[c_][0 if r['wrong_a'][i] else 1] += r['w'][i]
    P('| P1 counterpart | share of core WRONG weight | share of core RIGHT weight | local wrong share |')
    P('|---|---|---|---|')
    TW_, TR_ = sum(v[0] for v in tabW.values()), sum(v[1] for v in tabW.values())
    for c_ in cats:
        P(f'| {c_} | {100*tabW[c_][0]/TW_:.1f}% | {100*tabW[c_][1]/TR_:.1f}% | {100*tabW[c_][0]/max(sum(tabW[c_]),1e-30):.1f}% |')
    P(f'   "no P1 track with that id": not coasting: wrong {100*n_noid_coast[0]/TW_:.1f}% of core wrong, right {100*n_noid_coast[1]/TR_:.1f}% of core right; '
      f'coasting (track lost): wrong {100*n_noid_coast[2]/TW_:.1f}%, right {100*n_noid_coast[3]/TR_:.1f}%')
    for k_, v in tabByRes.items():
        P(f'   among fade<0.5 counterparts: {k_}: wrong {100*v[0]/TW_:.1f}% of core wrong, right {100*v[1]/TR_:.1f}% of core right')
    # counterfactual: core weight x [P1 fade>=0.5 counterpart exists]
    kept = tabW[cats[3]]
    P(f'counterfactual (interpretation): if the core only kept voice-hops whose P1 counterpart has fade>=0.5: wrong share would be {100*kept[0]/sum(kept):.1f}% (from {100*TW_/(TW_+TR_):.1f}%), '
      f'removing {100*(1-kept[0]/TW_):.1f}% of the wrong and {100*(1-kept[1]/TR_):.1f}% of the right weight')
    res['p1_match'] = {c_: tabW[c_] for c_ in cats}
    json.dump(res, open(C.D16 / 'q1.json', 'w'), indent=1, default=float)
    open(C.D16 / 'q1_report.txt', 'w').write('\n'.join(out_lines))


if __name__ == '__main__':
    main()
