"""Q1: attribution of the 20-150 Hz layer energy to (voice, k). usage: b12_q1.py [eng]  -> q1_<eng>.txt, q1_<eng>.pkl"""
import sys, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
import soundfile as sf
from scipy.signal import find_peaks

KDB = -5.0     # engine out_db (default test_engine) -> all dBFS below include it (checked: model-actual = +5.0 dB without it)
eng = sys.argv[1] if len(sys.argv) > 1 else 'v15'
_inp = {}


def mm(t):
    return f'{int(t // 60)}:{t % 60:05.2f}'


def inp_peaks(sk, t0, t1):
    if sk not in _inp:
        x, fs = sf.read(MUSIC[SONG_IDX[sk]], always_2d=True, dtype='float64')
        g = np.gcd(fs, FS)
        _inp[sk] = resample_poly(x[:, :2].mean(1), FS // g, fs // g)
    x = _inp[sk]
    fr = 0.5; n = int(fr * FS); w = np.hanning(n); nf = 1 << 17
    fq = np.fft.rfftfreq(nf, 1 / FS); sel = (fq >= 25) & (fq <= 1200)
    out = []
    for s in np.arange(t0 - 0.75, t1 + 0.75, 0.125):
        i = int(s * FS)
        P = np.abs(np.fft.rfft(x[i:i + n] * w, nf))[sel]; f = fq[sel]
        d = 20 * np.log10(P + 1e-12); d -= d.max()
        pk, _ = find_peaks(d, height=-40, distance=int(2.0 / fq[1]))
        out.append((s + fr / 2, f[pk], d[pk]))
    return out


def near_cents(f, pf):
    return np.min(np.abs(1200 * np.log2(f / pf))) if len(pf) else 1e9


def analyse(sk, t0, t1, rep):
    P = rep.append
    sy = synth(sk, eng, t0, t1)
    lo, hi = sy['sel_lo'], sy['sel_hi']
    H = len(sy['hops'])
    comp = sy['comp']
    xt = total(sy)
    tot = band_hop_power(xt)
    # per component hop power
    cp = {k: band_hop_power(x) for k, x in comp.items()}
    sl = slice(lo, hi)
    pa_lo = hop_power(band_signal(sk, eng, 'lo'), sy['ts']); pa_mid = hop_power(band_signal(sk, eng, 'mid'), sy['ts'])
    pP_lo = hop_power(band_signal(sk, 'P1', 'lo'), sy['ts']); pP_mid = hop_power(band_signal(sk, 'P1', 'mid'), sy['ts'])
    E = lambda a: a[sl].sum()
    Elo_tot = E(tot['lo']); Emid_tot = E(tot['mid'])
    sum_lo = sum(E(c['lo']) for c in cp.values()); sum_mid = sum(E(c['mid']) for c in cp.values())
    P(f'=== {sk} {mm(t0)}-{mm(t1)}  engine {eng}  hops {hi - lo}')
    P(f'MEASURED levels, mean hop power in dBFS (layer after out filter, incl. engine out_db): ')
    P(f'  20-150 Hz: {eng} actual {db(pa_lo[sl].mean()):.1f} | resynth(trace) {db(tot["lo"][sl].mean()) + KDB:.1f} | P1 actual {db(pP_lo[sl].mean()):.1f}')
    P(f'  150-600 Hz: {eng} actual {db(pa_mid[sl].mean()):.1f} | resynth(trace) {db(tot["mid"][sl].mean()) + KDB:.1f} | P1 actual {db(pP_mid[sl].mean()):.1f}')
    P(f'  resynth-vs-actual series corr (shift -2 hops): lo {np.corrcoef(db(tot["lo"][sl]), db(np.roll(pa_lo, -2)[sl]))[0, 1]:.2f}, mid {np.corrcoef(db(tot["mid"][sl]), db(np.roll(pa_mid, -2)[sl]))[0, 1]:.2f}; sum of per-component energies / total (cross terms): lo {sum_lo / Elo_tot:.2f}, mid {sum_mid / Emid_tot:.2f}')
    # stationary model (no AM/FM): per component band_pow of the instantaneous (a, k f) of the hop
    fo = sy['fo']; st = sy['st']
    stat = np.zeros(H)
    for kk in range(2, 9):
        fk = kk * fo
        stat += np.where(sy['a'][kk - 2] > 0, band_pow(sy['a'][kk - 2], np.where(fk > 0, fk, 100.0), SOS_LO), 0.0).sum(1)
    P(f'  20-150 Hz of a stationary-sinusoid model (each (v,k) frozen per hop, no AM/FM sidebands): {db(stat[sl].mean()) + KDB:.1f} dBFS  -> excess of the true (re-synthesised) layer over it: {db(tot["lo"][sl].mean()) - db(stat[sl].mean()):+.1f} dB')
    # per component records
    rec = []
    for (v, kk), c in cp.items():
        pw = c['lo'][sl]; e = pw.sum()
        if e <= 0: continue
        # weights = hop power; state / f_osc / kf of the slot carrying this voice
        fv = np.full(H, np.nan); sv = np.zeros(H, int); av = np.zeros(H)
        for s in range(8):
            m = sy['vid'][:, s] == v
            fv[m] = fo[m, s]; sv[m] = st[m, s]; av[m] = sy['a'][kk - 2][m, s]
        rec.append(dict(v=v, k=kk, e=e, emid=c['mid'][sl].sum(), fv=fv[sl], sv=sv[sl], pw=pw, av=av[sl]))
    rec.sort(key=lambda r: -r['e'])
    Eall = sum(r['e'] for r in rec)
    # --- by k
    P('MEASURED share of the 20-150 Hz energy (sum of per-component energies) by harmonic k:')
    P('  ' + ', '.join(f'k={kk}: {sum(r["e"] for r in rec if r["k"] == kk) / Eall * 100:.1f}%' for kk in range(2, 9)))
    # --- by voice f_osc (energy weighted over hops) and by instantaneous k f
    fb = [0, 50, 75, 100, 125, 150, 200, 1e9]; kb = [0, 100, 150, 200, 300, 450, 1e9]
    hf = np.zeros(len(fb) - 1); hk = np.zeros(len(kb) - 1); hfk2 = np.zeros(len(fb) - 1)
    for r in rec:
        m = np.isfinite(r['fv'])
        for j in range(len(fb) - 1):
            hf[j] += r['pw'][m & (r['fv'] >= fb[j]) & (r['fv'] < fb[j + 1])].sum()
            if r['k'] == 2: hfk2[j] += r['pw'][m & (r['fv'] >= fb[j]) & (r['fv'] < fb[j + 1])].sum()
        kf = r['k'] * r['fv']
        for j in range(len(kb) - 1):
            hk[j] += r['pw'][m & (kf >= kb[j]) & (kf < kb[j + 1])].sum()
    P('MEASURED voice f_osc distribution of the 20-150 Hz energy (energy-weighted over hops): ' + ', '.join(f'{fb[j]:.0f}-{(fb[j + 1] if fb[j + 1] < 1e8 else 999):.0f} Hz: {hf[j] / hf.sum() * 100:.1f}%' for j in range(len(hf))))
    P('MEASURED instantaneous k*f_osc of the component, same weighting: ' + ', '.join(f'{kb[j]:.0f}-{(kb[j + 1] if kb[j + 1] < 1e8 else 999):.0f} Hz: {hk[j] / hk.sum() * 100:.1f}%' for j in range(len(hk))))
    # --- transient vs steady hops
    tr_share = 0.0
    chg = np.zeros((H, 8), bool)
    for s in range(8):
        v = sy['vid'][:, s]
        ap = np.concatenate([[0], sy['a'][0][:-1, s] + sy['a'][1][:-1, s]]); an = sy['a'][0][:, s] + sy['a'][1][:, s]
        newv = np.concatenate([[True], v[1:] != v[:-1]])
        dfo = np.concatenate([[0], np.abs(np.diff(fo[:, s]))])
        da = np.abs(20 * np.log10((an + 1e-9) / (ap + 1e-9)))
        chg[:, s] = newv | (dfo > 3.0) | (da > 3.0)
    ev = 0.0
    for r in rec:
        pass
    # energy of hops where ANY slot has a change flagged within +-1 hop vs none
    anychg = chg.any(1); anychg = anychg | np.roll(anychg, 1) | np.roll(anychg, -1)
    shr = tot['lo'][sl][anychg[sl]].sum() / Elo_tot
    P(f'MEASURED share of the 20-150 Hz layer energy in hops (+-1) where some voice has a birth/slot change, |df_osc| > 3 Hz/hop or |dA| > 3 dB/hop: {shr * 100:.0f}% (those hops are {anychg[sl].mean() * 100:.0f}% of the window)')
    # --- top voices (sum over k)
    byv = {}
    for r in rec: byv.setdefault(r['v'], []).append(r)
    vlist = sorted(byv, key=lambda v: -sum(r['e'] for r in byv[v]))
    peaks = inp_peaks(sk, t0, t1)
    pt = np.array([p[0] for p in peaks])
    P('Top voices by 20-150 Hz energy: id | share | mid(150-600) share of own energy | f_osc E-weighted mean [min-max] | main k (share of own) | kf mean | sounding hops ON/REL/CAND | ON<->REL changes | input relation (E-weighted: f_osc is a real partial / k*f_osc matches a partial (k) / none)')
    out_v = []
    for v in vlist[:10]:
        rs = byv[v]; ev_ = sum(r['e'] for r in rs); emid_ = sum(r['emid'] for r in rs)
        pw = sum(r['pw'] for r in rs)
        fv = rs[0]['fv']; m = np.isfinite(fv) & (pw > 0)
        fmean = np.sum(fv[m] * pw[m]) / pw[m].sum()
        kmain = max(rs, key=lambda r: r['e'])
        sv = rs[0]['sv']
        n_on = int((sv == 2).sum()); n_rel = int((sv == 3).sum()); n_c = int((sv == 1).sum())
        chg_ = int(((sv[1:] != sv[:-1]) & (sv[1:] >= 2) & (sv[:-1] >= 2)).sum())
        # input relation
        w_real = w_sub = w_none = 0.0; subk = {}
        for h in np.where(m)[0]:
            tt = sy['ts'][lo + h]; fr = peaks[int(np.argmin(np.abs(pt - tt)))]
            pf = fr[1][fr[2] > -30]
            f0 = fv[h]; wgt = pw[h]
            tol = max(50.0, 1200 * np.log2(1 + 2.5 / f0))
            if near_cents(f0, pf) <= tol: w_real += wgt
            else:
                hit = [kk for kk in (2, 3, 4) if near_cents(kk * f0, pf) <= tol]
                if hit: w_sub += wgt; subk[hit[0]] = subk.get(hit[0], 0) + wgt
                else: w_none += wgt
        ws = w_real + w_sub + w_none
        tm = ' '.join(f'k{kk}:{x / max(w_sub, 1e-30) * 100:.0f}%' for kk, x in sorted(subk.items()))
        P(f'  {v:5d} | {ev_ / Eall * 100:5.1f}% | {emid_ / max(ev_ + emid_, 1e-30) * 100:4.0f}% | {fmean:6.1f} [{np.nanmin(fv[m]):.0f}-{np.nanmax(fv[m]):.0f}] | k={kmain["k"]} ({kmain["e"] / ev_ * 100:.0f}%) | {kmain["k"] * fmean:5.1f} | {n_on}/{n_rel}/{n_c} | {chg_} | real {w_real / ws * 100:.0f}% / ghost {w_sub / ws * 100:.0f}% ({tm}) / none {w_none / ws * 100:.0f}%')
        out_v.append(dict(v=v, share=ev_ / Eall, fmean=fmean, kmain=kmain['k'], n=(n_on, n_rel, n_c), chg=chg_, real=w_real / ws, ghost=w_sub / ws, none=w_none / ws, emid=emid_, elo=ev_))
    # cumulative
    cs = np.cumsum([sum(r['e'] for r in byv[v]) / Eall for v in vlist])
    P(f'  voices needed for 50/80/90% of the 20-150 Hz energy: {int(np.searchsorted(cs, .5)) + 1}/{int(np.searchsorted(cs, .8)) + 1}/{int(np.searchsorted(cs, .9)) + 1} of {len(vlist)} voices')
    # overall input relation, energy weighted over ALL voices
    wr = sum(o['real'] * o['elo'] for o in out_v); wg = sum(o['ghost'] * o['elo'] for o in out_v); wn = sum(o['none'] * o['elo'] for o in out_v)
    P(f'  top-10 voices overall (E-weighted): f_osc real input partial {wr / (wr + wg + wn) * 100:.0f}%, sub-harmonic ghost (k f_osc matches a partial) {wg / (wr + wg + wn) * 100:.0f}%, matches nothing {wn / (wr + wg + wn) * 100:.0f}%')
    return dict(rec=[{k: v for k, v in r.items() if k in ('v', 'k', 'e', 'emid')} for r in rec], out_v=out_v, Elo_tot=Elo_tot, Emid_tot=Emid_tot, vlist=vlist)


if __name__ == '__main__':
    rep = []; res = {}
    for sk, t0, t1 in WINDOWS:
        res[(sk, t0)] = analyse(sk, t0, t1, rep)
        rep.append('')
    open(B12 / f'q1_{eng}.txt', 'w').write('\n'.join(rep))
    print('\n'.join(rep))
    pickle.dump(res, open(B12 / f'q1_{eng}.pkl', 'wb'))
