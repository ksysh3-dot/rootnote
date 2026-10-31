"""HAUX user windows: Q3 (input support of >6 dB a_2 jumps) and Q2 jump counts f_h vs f_osc (CHOICES.md section 5).
usage: runpy.sh haux_user.py  -> user_report.txt, user_raw.pkl.  Audio read in place (never copied); trace from tmp/ (haux_render.py)."""
import os, sys, json, pickle, time
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
import numpy as np
from pathlib import Path
from multiprocessing import Pool
from b12common import read_song, SONG_IDX, MUSIC, FS
import haux_lib as H

HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')
LAG = -0.012
CORE_T0 = 1359.0 / 48000.0
HOP_S = 16 / 3000.0
WINDOWS = [('app', 52.0, 54.0), ('app', 88.5, 90.5), ('app', 123.5, 125.5), ('app', 201.0, 203.0), ('app', 203.0, 205.0), ('rem', 96.0, 98.0), ('rem', 113.0, 115.0)]


def cents(a, b):
    return 1200 * np.log2(np.maximum(a, 1e-9) / np.maximum(b, 1e-9))


_song = {}


def get_x(sk):
    if sk not in _song:
        assert 'slakh2100' not in str(MUSIC[SONG_IDX[sk]])
        _song[sk] = read_song(SONG_IDX[sk]).astype(np.float64).mean(1)
    return _song[sk]


def job(win):
    sk, t0, t1 = win
    tt0 = time.time()
    z = np.load(HX / 'tmp' / f'{sk}_v15_trace.npz')
    tr = {k: z[k].astype(np.float64) for k in z.files}
    hop = tr['hop'][:, 0]
    ts = (hop - 398) / 3000.0 + CORE_T0                     # A5 selection time (hop_time()[1])
    tin = (hop - 382) / 3000.0 + CORE_T0 + LAG               # input time of the hop, T = tc + LAG
    sel = np.where((ts >= t0) & (ts < t1))[0]
    sel = sel[sel >= 1]
    st, vid, a2, fo, ft = tr['state'], tr['voice'], tr['a_2'], tr['f_osc'], tr['f_track']
    x = get_x(sk)
    lo, hi = sel[0] - 3, sel[-1] + 3
    hs = np.arange(lo, hi + 1)
    # fit table
    A2 = {W: np.full((len(hs), 8), np.nan) for W in (40, 85)}
    H6 = {W: np.full((len(hs), 8), np.nan) for W in (40, 85)}
    FH = {W: np.full((len(hs), 8), np.nan) for W in (40, 85)}
    segs = {}
    for r, h in enumerate(hs):
        c = int(round(tin[h] * FS))
        for W in (40, 85):
            L = H.WINLEN[W]; w = H.hann(L)
            seg = H.segment(x, c, L)
            segs[(h, W)] = seg
            X = None
            for s in range(8):
                if st[h, s] >= 2 and fo[h, s] > 0:
                    E, Ei, a = H.comb_fit(seg, w, fo[h, s])
                    A2[W][r, s] = a[1]
                    H6[W][r, s] = H.hsal(E, Ei, 6)
                    if ft[h, s] > 0 and sel[0] - 1 <= h <= sel[-1]:
                        if X is None:
                            X = H.spec_amp(seg, w)
                        FH[W][r, s] = H.comb_f0(X, ft[h, s])[0]
    # jumps (A5 definition)
    s1 = sel
    ok = (vid[s1] == vid[s1 - 1]) & (st[s1] >= 2) & (st[s1 - 1] >= 2) & (a2[s1] > 1e-7) & (a2[s1 - 1] > 1e-7)
    d_ren = np.abs(20 * np.log10(np.where(ok, a2[s1], 1.0) / np.where(ok, a2[s1 - 1], 1.0)))
    out = dict(win=win, nsel=len(sel), nchk=int(ok.sum()), njump=int((ok & (d_ren > 6)).sum()))
    recs = []
    for ii, h in enumerate(s1):
        for s in range(8):
            if not ok[ii, s]:
                continue
            r = h - lo
            rec = dict(h=h, s=s, d_ren=d_ren[ii, s], sign=np.sign(np.log(a2[h, s] / a2[h - 1, s])), vid=vid[h, s], fo=fo[h, s])
            for W in (40, 85):
                a_n, a_p = A2[W][r, s], A2[W][r - 1, s]
                rec[f'din{W}'] = abs(20 * np.log10(a_n / a_p)) if (a_n > 0 and a_p > 0) else np.nan
                rec[f'sgn{W}'] = np.sign(np.log(a_n / a_p)) if (a_n > 0 and a_p > 0) else np.nan
                rec[f'h6{W}'] = H6[W][r, s]
                rec[f'a2in{W}'] = a_n
                # 3-hop variant: h+1 vs h-2 (same voice id, both sounding)
                if r + 1 < len(hs) and r - 2 >= 0 and vid[h + 1, s] == vid[h, s] and vid[h - 2, s] == vid[h, s]:
                    b_n, b_p = A2[W][r + 1, s], A2[W][r - 2, s]
                    rec[f'd3_{W}'] = abs(20 * np.log10(b_n / b_p)) if (b_n > 0 and b_p > 0) else np.nan
                else:
                    rec[f'd3_{W}'] = np.nan
                # fixed-frequency variant: fit at hop h-1 with f_osc(h)
                if d_ren[ii, s] > 6:
                    L = H.WINLEN[W]; w = H.hann(L)
                    E, Ei, a = H.comb_fit(segs[(h - 1, W)], w, fo[h, s])
                    rec[f'dfix{W}'] = abs(20 * np.log10(a_n / a[1])) if (a_n > 0 and a[1] > 0) else np.nan
            recs.append(rec)
    out['recs'] = recs
    # f_osc / f_h jumps on consecutive hops (same slot, same voice id, state >= 2 both)
    fj = dict(pairs=0)
    okf = (vid[s1] == vid[s1 - 1]) & (st[s1] >= 2) & (st[s1 - 1] >= 2) & (fo[s1] > 0) & (fo[s1 - 1] > 0)
    d_osc = np.abs(fo[s1] - fo[s1 - 1])
    d_trk = np.abs(ft[s1] - ft[s1 - 1])
    res = dict(osc=[], trk=[], h40=[], h85=[], cos=[], ch40=[], ch85=[])
    for ii, h in enumerate(s1):
        for s in range(8):
            if not okf[ii, s]:
                continue
            r = h - lo
            d40 = abs(FH[40][r, s] - FH[40][r - 1, s]); d85 = abs(FH[85][r, s] - FH[85][r - 1, s])
            if not (np.isfinite(d40) and np.isfinite(d85)):
                continue
            res['osc'].append(d_osc[ii, s]); res['trk'].append(d_trk[ii, s]); res['h40'].append(d40); res['h85'].append(d85)
            res['cos'].append(abs(cents(fo[h, s], fo[h - 1, s])))
            res['ch40'].append(abs(cents(FH[40][r, s], FH[40][r - 1, s]))); res['ch85'].append(abs(cents(FH[85][r, s], FH[85][r - 1, s])))
    out['fj'] = {k: np.array(v) for k, v in res.items()}
    out['secs'] = time.time() - tt0
    print(win, 'done', round(out['secs'], 1), flush=True)
    return out


def pctl(x, q):
    return float(np.percentile(x, q)) if len(x) else float('nan')


if __name__ == '__main__':
    t0 = time.time()
    with Pool(7) as p:
        outs = p.map(job, WINDOWS)
    pickle.dump(outs, open(HX / 'user_raw.pkl', 'wb'))
    L = []
    P = lambda s='': L.append(s)
    a5 = {(r['song'], r['t0']): r for r in json.load(open(HX.parent / 'A5' / 'primary_v15.json'))}
    P('# HAUX user windows (v1.5 = build_core algo 15, default16)')
    P('window | selected hops | checked pairs | >6 dB jumps | A5 primary_v15 (jumps/checked, build_core16c) ')
    for o in outs:
        sk, t0_, t1_ = o['win']; r = a5.get((sk, t0_))
        P(f'{sk} {t0_:.1f}-{t1_:.1f} | {o["nsel"]} | {o["nchk"]} | {o["njump"]} | ' + (f'{r["jumps"]}/{r["checked"]}' if r else 'n/a'))
    R = [r for o in outs for r in o['recs']]
    J = [r for r in R if r['d_ren'] > 6]
    P(f'\n## Q3: rendered a_2 jumps > 6 dB: {len(J)} of {len(R)} checked voice-hop pairs ({len(J) / len(R):.3f})')
    for W in (40, 85):
        din = np.array([r[f'din{W}'] for r in J]); ok = np.isfinite(din)
        P(f'\n### window {W} ms: jumps with a valid input fit {ok.sum()}')
        P(f'input change D_in (dB) at the jumps: median {np.median(din[ok]):.2f}, p75 {pctl(din[ok], 75):.2f}, p90 {pctl(din[ok], 90):.2f}, p99 {pctl(din[ok], 99):.2f}')
        P(f'**unsupported (D_in < 2 dB): {(din[ok] < 2).mean() * 100:.1f} %**  | D_in < 1 dB: {(din[ok] < 1).mean() * 100:.1f} % | D_in < 3 dB: {(din[ok] < 3).mean() * 100:.1f} % | D_in < 6 dB: {(din[ok] < 6).mean() * 100:.1f} %')
        # per window
        P('per window unsupported share: ' + ' ; '.join(f'{o["win"][0]} {o["win"][1]:.1f}: ' + (lambda dd: f'{(dd < 2).mean() * 100:.0f} % (n {len(dd)})')(np.array([r[f'din{W}'] for r in o['recs'] if r['d_ren'] > 6 and np.isfinite(r[f'din{W}'])])) for o in outs))
        d3 = np.array([r[f'd3_{W}'] for r in J]); ok3 = np.isfinite(d3)
        P(f'3-hop variant (input change h-2 -> h+1, 16 ms): valid {ok3.sum()}, unsupported (<2 dB) {(d3[ok3] < 2).mean() * 100:.1f} %, median {np.median(d3[ok3]):.2f} dB')
        df = np.array([r.get(f'dfix{W}', np.nan) for r in J]); okf = np.isfinite(df)
        P(f'fixed-frequency variant (2 f_osc(h) in both hops): valid {okf.sum()}, unsupported {(df[okf] < 2).mean() * 100:.1f} %, median {np.median(df[okf]):.2f} dB')
        sg = np.array([r['sign'] * r[f'sgn{W}'] for r in J]); hi = ok & (din >= 2)
        P(f'where the input changed >= 2 dB ({hi.sum()} jumps): same direction as the render in {(sg[hi] > 0).mean() * 100:.1f} %')
        # controls
        din_all = np.array([r[f'din{W}'] for r in R]); oka = np.isfinite(din_all)
        nj = np.array([r['d_ren'] <= 6 for r in R])
        P(f'control: D_in over all checked pairs ({oka.sum()}): median {np.median(din_all[oka]):.2f}, p90 {pctl(din_all[oka], 90):.2f}, share >= 2 dB {(din_all[oka] >= 2).mean() * 100:.1f} %, >= 6 dB {(din_all[oka] >= 6).mean() * 100:.1f} %')
        m = oka & nj
        P(f'control: non-jump pairs: share D_in >= 2 dB {(din_all[m] >= 2).mean() * 100:.1f} %; jump pairs: {(din[ok] >= 2).mean() * 100:.1f} %')
        # H_sal6 of jump hops
        h6 = np.array([r[f'h6{W}'] for r in R]); jm = np.array([r['d_ren'] > 6 for r in R])
        P(f'H_sal6 at f_osc (dB): jump hops median {np.nanmedian(h6[jm]):.1f}, non-jump {np.nanmedian(h6[~jm]):.1f}; among jumps: unsupported {np.nanmedian(h6[jm & (din_all < 2)]):.1f}, supported {np.nanmedian(h6[jm & (din_all >= 2)]):.1f}')
        # level of jump: amplitude of the input partial relative to window max? share of unsupported by size of the jump
        dr = np.array([r['d_ren'] for r in J])
        for lo_, hi_ in ((6, 9), (9, 15), (15, 1e9)):
            mm = ok & (dr >= lo_) & (dr < hi_)
            if mm.sum():
                P(f'  render jump {lo_}-{hi_ if hi_ < 1e8 else "inf"} dB: n {mm.sum()}, unsupported {(din[mm] < 2).mean() * 100:.1f} %')
    # f_h vs f_osc
    P('\n## Q2 in the user windows: hop-to-hop frequency jumps on consecutive hops (same slot/voice, state >= 2; f_h = comb refinement around f_track)')
    fj = {k: np.concatenate([o['fj'][k] for o in outs]) for k in outs[0]['fj']}
    n = len(fj['osc']); vs = n * HOP_S
    P(f'pairs {n} ({vs:.1f} voice-seconds)')
    P('series | jumps > 2 Hz per window summed | per voice-second | median |df| Hz | p95 |df| Hz | median cent | p95 cent')
    for nm_, k, kc in (('f_osc (rendered)', 'osc', 'cos'), ('f_track', 'trk', None), ('f_h W40', 'h40', 'ch40'), ('f_h W85', 'h85', 'ch85')):
        z = fj[k]
        c = fj[kc] if kc else np.full(len(z), np.nan)
        P(f'{nm_} | {(z > 2).sum()} | {(z > 2).sum() / vs:.2f} | {np.median(z):.3f} | {pctl(z, 95):.2f} | {np.nanmedian(c):.1f} | {np.nanpercentile(c, 95) if kc else float("nan"):.1f}')
    P('per window jumps > 2 Hz (f_osc / f_h40 / f_h85): ' + ' ; '.join(f'{o["win"][0]} {o["win"][1]:.1f}: {(o["fj"]["osc"] > 2).sum()}/{(o["fj"]["h40"] > 2).sum()}/{(o["fj"]["h85"] > 2).sum()} of {len(o["fj"]["osc"])}' for o in outs))
    m = fj['osc'] > 2
    P(f'at the {m.sum()} f_osc jumps > 2 Hz: f_h W40 moved < 1 Hz in {(fj["h40"][m] < 1).mean() * 100:.1f} %, < 2 Hz in {(fj["h40"][m] < 2).mean() * 100:.1f} %; W85 < 1 Hz in {(fj["h85"][m] < 1).mean() * 100:.1f} %, < 2 Hz in {(fj["h85"][m] < 2).mean() * 100:.1f} %; f_track < 2 Hz in {(fj["trk"][m] < 2).mean() * 100:.1f} %')
    P(f'\nsecs {time.time() - t0:.0f}')
    open(HX / 'user_report.txt', 'w').write('\n'.join(L))
    print('\n'.join(L))
