"""Q10: joint-LS conditioning. How often are two LS voices within 1.5*3000/N_J Hz, how often is one coasting, what share of wrong/right weight sits in such
pairs, and A_joint / A_single of the weaker voice (offline stage-1 LS emulation on the engine's bh stream).  N_J is recomputed from the spec (5.3) because the
trace exposes only N_v / N_J mixed in the np field; it is checked against np for voices with SNR < 18 dB (np = N_J there)."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S
import q7

FS = 3000.0
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def nj_spec(fb, snr_on_min, snr_all_min, nv):
    flow = fb.min()
    nlo = int(np.clip(np.ceil(FS / flow), 30, 320))
    nsep = 0
    if nv >= 2:
        s = np.sort(fb); dfm = np.min(np.diff(s)); nsep = int(np.ceil(2 * FS / max(dfm, 1e-3))) - 24
    s_ = snr_on_min if snr_on_min < 1e8 else snr_all_min
    if s_ >= 30: nsnr = nlo
    elif s_ <= 12: nsnr = 320
    else:
        nsnr = int(np.exp(np.interp(s_, [12, 30], [np.log(320), np.log(nlo)])))
    return int(np.clip(max(nlo, nsep, nsnr), nlo, 320))


def analyse(name, trace_d, raw, tc, st, bh, labels=None):
    d = trace_d; H = len(tc)
    hop_i = raw[:, 0, X.F_HOP].astype(np.int64)
    pairs = []            # rows
    inpair = {k: np.zeros((H, 8), bool) for k in ('A', 'B', 'C')}
    nj_chk = []
    hop_stats = {k: dict(n=0, coast=0) for k in ('A', 'B', 'C')}
    nh = 0
    prev_f = {}
    for h in range(H):
        cur_f = {int(d['voice'][h][j]): d['fosc'][h][j] for j in range(8) if st[h][j] > 0}
        if tc[h] > 0.5 and hop_i[h] - 191 + 30 < len(bh):
            L =[j for j in range(8) if st[h][j] in (1, 2) or (st[h][j] == 3 and d['c'][h][j] > .1)]
            nh += 1
            if len(L) >= 2:
                fb = np.array([prev_f.get(int(d['voice'][h][j]), d['fosc'][h][j]) for j in L])
                snr = d['snr'][h][L]; on = np.array([st[h][j] == 2 for j in L])
                NJ = nj_spec(fb, snr[on].min() if on.any() else 1e9, snr.min(), len(L))
                for q, j in enumerate(L):
                    if snr[q] < 18 and raw[h, j, X.F_NP] > 0:
                        nj_chk.append((NJ, raw[h, j, X.F_NP]))
                fd = np.clip(raw[h, L, X.F_DFDT], -400, 400)
                n0 = hop_i[h] - 191
                Aj = S.ls_multi(bh, n0, fb, fd, NJ)
                As = np.array([S.ls_multi(bh, n0, fb[q:q + 1], fd[q:q + 1], NJ)[0] for q in range(len(L))])
                got = {'A': False, 'B': False, 'C': False}; gotc = {'A': False, 'B': False, 'C': False}
                for a in range(len(L)):
                    for b in range(a + 1, len(L)):
                        df = abs(fb[a] - fb[b])
                        flags = {'A': df < 1.5 * FS / NJ, 'B': df < 14.1, 'C': df < 6.0}
                        if not any(flags.values()):
                            continue
                        wk = a if As[a] <= As[b] else b
                        co = bool(d['coast'][h][L[a]] > 0 or d['coast'][h][L[b]] > 0)
                        pairs.append((flags['A'], flags['B'], flags['C'], co, df, NJ, Aj[wk] / max(As[wk], 1e-12), d['A'][h][L[wk]] / max(As[wk], 1e-12), h, L[wk], d['c'][h][L[wk]], st[h][L[wk]]))
                        for k in flags:
                            if flags[k]:
                                inpair[k][h, L[a]] = inpair[k][h, L[b]] = True; got[k] = True; gotc[k] |= co
                for k in got:
                    if got[k]:
                        hop_stats[k]['n'] += 1; hop_stats[k]['coast'] += int(gotc[k])
        prev_f = cur_f
    return pairs, inpair, hop_stats, nh, nj_chk


def main():
    allrows = []; tot = {k: dict(n=0, coast=0, nh=0, wr=0., rt=0., Wr=0., Rt=0.) for k in ('A', 'B', 'C')}
    chk = []
    per = {}
    names = C.TRACKS + ['LOGOFF']
    for name in names:
        if name == 'LOGOFF':
            x = X.read_excerpt(X.LOGOFF, 20.0, 30.0)
            tr = None
        else:
            x = X.read_excerpt(X.SLAKH / name / 'mix.flac', 0.0, 30.0)
        s = S.get(name, x)
        if name == 'LOGOFF':
            tr_ = s['trace']; d, hop, tc = X.hops_of(tr_); raw = tr_.reshape(-1, 8, 22); st = d['state']
            w = np.where(st > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0); lab = np.zeros(w.shape, bool); wrong = lab.copy()
        else:
            D = q7.build(name); d, raw, tc, st, w, lab, wrong = D['d'], D['raw'], D['tc'], D['st'], D['w'], D['lab'], D['wrong']
            # the stream render (0.3 s silence tail) must have given the same trace
            n_ = min(len(s['trace']), len(raw) * 8)
            assert np.allclose(s['trace'][:n_ - 8 * 100, 8], raw.reshape(-1, 22)[:n_ - 8 * 100, 8]), 'trace mismatch'
        pairs, inpair, hs, nh, njc = analyse(name, d, raw, tc, st, s['bh'], None)
        chk += njc
        dur = nh * 16 / 3000.0
        per[name] = dict(dur=dur)
        P(f'{name}: {nh} analysed hops ({dur:.1f} s), pair rows {len(pairs)}')
        for k in ('A', 'B', 'C'):
            per[name][k] = (hs[k]['n'], hs[k]['coast'])
            tot[k]['n'] += hs[k]['n']; tot[k]['coast'] += hs[k]['coast']; tot[k]['nh'] += nh
            tot[k].setdefault('dur', 0.0); tot[k]['dur'] += dur
            if name != 'LOGOFF':
                m = inpair[k]
                tot[k]['wr'] += w[m & lab & wrong].sum(); tot[k]['rt'] += w[m & lab & ~wrong].sum()
                tot[k]['Wr'] += w[lab & wrong].sum(); tot[k]['Rt'] += w[lab & ~wrong].sum()
        allrows += [(name,) + p for p in pairs]
    chk = np.array(chk)
    P(f'\nN_J spec formula vs np of voices with SNR<18 (np = N_J there): {len(chk)} voice-hops; exact {np.mean(chk[:,0]==chk[:,1])*100:.1f} %, within 25 % {np.mean(np.abs(chk[:,0]-chk[:,1])<=.25*chk[:,1])*100:.1f} %, spec N_J >= np {np.mean(chk[:,0]>=chk[:,1])*100:.1f} % (hysteresis/3-hop persistence not emulated)')
    P('\n### Q10 pair statistics (def A: dF < 1.5*3000/N_J [spec N_J]; def B: dF < 14.1 Hz; def C: dF < 6 Hz). Rates over analysed hops (tc>0.5 s), 10 tracks + LOGOFF (LOGOFF: no MIDI labels, excluded from the weight shares).')
    P('| definition | hops with >=1 pair | per second | fraction of hops | of those, a member is coasting | wrong weight in pairs | right weight in pairs | wrong share inside pairs |')
    P('|---|---|---|---|---|---|---|---|')
    for k, lab_ in (('A', 'A: 1.5*3000/N_J'), ('B', 'B: < 14.1 Hz'), ('C', 'C: < 6 Hz')):
        t = tot[k]
        P(f'| {lab_} | {t["n"]} | {t["n"]/t["dur"]:.1f} | {100*t["n"]/t["nh"]:.1f} % | {100*t["coast"]/max(t["n"],1):.1f} % | {100*t["wr"]/t["Wr"]:.1f} % | {100*t["rt"]/t["Rt"]:.1f} % | {100*t["wr"]/max(t["wr"]+t["rt"],1e-30):.1f} % |')
    P('\nper track hops-with-pair per second (def B | def C), coasting share of B hops:')
    for n in names:
        a = per[n]; P(f'  {n}: {a["B"][0]/a["dur"]:.1f} | {a["C"][0]/a["dur"]:.1f}; coasting share {100*a["B"][1]/max(a["B"][0],1):.0f} %')
    R = np.array([r[1:] for r in allrows], dtype=float)         # fA fB fC co df NJ ratio_emul ratio_trace h j
    P('\nA_joint / A_single of the weaker voice of each pair (emulated stage-1 joint LS over the whole LS set at N_J, single = that voice alone at the same window), and the trace A (realised, stage 1 or 2) / A_single:')
    P('| subset | pairs | emul p50 | p95 | max | trace p50 | p95 | max | fraction with emul ratio > 2 (+6 dB) |')
    P('|---|---|---|---|---|---|---|---|---|')
    for lab_, m in (('A all', R[:, 0] > 0), ('A, coasting member', (R[:, 0] > 0) & (R[:, 3] > 0)), ('A, both tracked', (R[:, 0] > 0) & (R[:, 3] == 0)),
                    ('B all', R[:, 1] > 0), ('B, coasting member', (R[:, 1] > 0) & (R[:, 3] > 0)), ('B, both tracked', (R[:, 1] > 0) & (R[:, 3] == 0)),
                    ('C all', R[:, 2] > 0), ('C, coasting member', (R[:, 2] > 0) & (R[:, 3] > 0)), ('C, both tracked', (R[:, 2] > 0) & (R[:, 3] == 0)),
                    ('B and N_J = 320', (R[:, 1] > 0) & (R[:, 5] >= 319)),
                    ('B, weaker voice ON with c>0.5', (R[:, 1] > 0) & (R[:, 10] > .5) & (R[:, 11] == 2)),
                    ('B, weaker ON c>0.5, both tracked', (R[:, 1] > 0) & (R[:, 10] > .5) & (R[:, 11] == 2) & (R[:, 3] == 0)),
                    ('C, weaker voice ON with c>0.5', (R[:, 2] > 0) & (R[:, 10] > .5) & (R[:, 11] == 2)),
                    ('B, weaker voice REL or c<=0.5', (R[:, 1] > 0) & ~((R[:, 10] > .5) & (R[:, 11] == 2)))):
        if m.sum() == 0:
            P(f'| {lab_} | 0 |'); continue
        e, t_ = R[m, 6], R[m, 7]
        P(f'| {lab_} | {m.sum()} | {np.percentile(e,50):.2f} | {np.percentile(e,95):.2f} | {e.max():.1f} | {np.percentile(t_,50):.2f} | {np.percentile(t_,95):.2f} | {t_.max():.1f} | {100*np.mean(e>2):.1f} % |')
    open(C.D16 / 'q10_report.txt', 'w').write('\n'.join(out))


if __name__ == '__main__':
    main()
