"""Q1b: where in time does the 20-150 Hz energy of a voice come from (steady, amplitude event, frequency event, birth/slot change) and how far is it
above the stationary-sinusoid leak of the same voice (skirt of the 20-150 Hz band-pass). usage: b12_q1b.py [eng]"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
eng = sys.argv[1] if len(sys.argv) > 1 else 'v15'
KDB = -5.0
rep = []; P = rep.append
for sk, t0, t1 in WINDOWS:
    sy = synth(sk, eng, t0, t1)
    lo, hi = sy['sel_lo'], sy['sel_hi']; H = len(sy['hops']); sl = slice(lo, hi)
    fo = sy['fo']; st = sy['st']; vid = sy['vid']
    cp = {k: band_hop_power(x, ('lo', 'mid')) for k, x in sy['comp'].items()}
    tot = band_hop_power(total(sy))
    # per voice: lo power series (sum over k), stationary series, flags
    P(f'=== {sk} {t0} {eng}: lo/mid energy per voice, excess over the stationary leak, and hop classes (amp event |dA|>6 dB/hop, freq event |df_osc|>2 Hz/hop, new voice in slot)')
    vs = sorted({v for (v, k) in cp}, key=lambda v: -sum(c['lo'][sl].sum() for (vv, kk), c in cp.items() if vv == v))
    Etot = sum(c['lo'][sl].sum() for c in cp.values()); Emid = sum(c['mid'][sl].sum() for c in cp.values())
    cls_tot = {'steady': 0, 'amp': 0, 'freq': 0, 'new': 0}; cls_n = {'steady': 0, 'amp': 0, 'freq': 0, 'new': 0}
    P('  id | lo share | mid share | lo/mid dB | stationary-lo/mid dB (steady leak) | excess dB | lo energy: steady/amp-event/freq-event/new-voice hops [%] | f_osc range')
    rows = []
    for v in vs[:8]:
        plo = sum(c['lo'] for (vv, kk), c in cp.items() if vv == v); pmid = sum(c['mid'] for (vv, kk), c in cp.items() if vv == v)
        stat_lo = np.zeros(H); a_v = np.zeros(H); f_v = np.full(H, np.nan); new = np.zeros(H, bool)
        for s in range(8):
            m = vid[:, s] == v
            f_v[m] = fo[m, s]
            for kk in range(2, 9):
                fk = kk * fo[:, s]
                stat_lo += np.where(m & (sy['a'][kk - 2][:, s] > 0), band_pow(sy['a'][kk - 2][:, s], np.where(fk > 0, fk, 100.0), SOS_LO), 0.0)
            a_v[m] = np.sqrt(sum(sy['a'][kk][m, s] ** 2 for kk in range(7)))
            idx = np.where(m)[0]
            if len(idx): new[idx[0]] = True
            prevv = np.concatenate([[-1], vid[:-1, s]])
            new |= m & (prevv != v)
        da = np.concatenate([[0], np.abs(20 * np.log10((a_v[1:] + 1e-9) / (a_v[:-1] + 1e-9)))]); df = np.concatenate([[0], np.abs(np.diff(f_v))])
        da = np.where(np.isfinite(da), da, 0); df = np.where(np.isfinite(df), df, 0)
        ev_a = (da > 6) | np.roll(da > 6, -1); ev_f = (df > 2) | np.roll(df > 2, -1); ev_n = new | np.roll(new, -1)
        cls = np.where(ev_n, 3, np.where(ev_a, 1, np.where(ev_f, 2, 0)))
        act = (a_v > 0)[sl]
        e = plo[sl]
        parts = [e[(cls[sl] == c) & act].sum() / e.sum() * 100 for c in range(4)]
        hn = [((cls[sl] == c) & act).sum() for c in range(4)]
        for c, nm in enumerate(('steady', 'amp', 'freq', 'new')):
            cls_tot[nm] += e[(cls[sl] == c) & act].sum(); cls_n[nm] += hn[c]
        rm = db(plo[sl].sum()) - db(pmid[sl].sum()); sm = db(stat_lo[sl].sum()) - db(np.maximum(0, 1) * 1.0)  # placeholder
        # stationary mid for the same voice
        stat_mid = np.zeros(H)
        for s in range(8):
            m = vid[:, s] == v
            for kk in range(2, 9):
                fk = kk * fo[:, s]
                stat_mid += np.where(m & (sy['a'][kk - 2][:, s] > 0), band_pow(sy['a'][kk - 2][:, s], np.where(fk > 0, fk, 100.0), SOS_MID), 0.0)
        srm = db(stat_lo[sl].sum()) - db(stat_mid[sl].sum())
        P(f'  {v:5d} | {plo[sl].sum() / Etot * 100:5.1f}% | {pmid[sl].sum() / Emid * 100:5.1f}% | {rm:6.1f} | {srm:6.1f} | {rm - srm:+5.1f} | {parts[0]:3.0f}/{parts[1]:3.0f}/{parts[2]:3.0f}/{parts[3]:3.0f} (hops {hn[0]}/{hn[1]}/{hn[2]}/{hn[3]}) | {np.nanmin(f_v[sl]):.0f}-{np.nanmax(f_v[sl]):.0f}')
        rows.append((v, parts))
    Et = sum(cls_tot.values())
    P(f'  top-8 voices pooled: lo energy by hop class (hop counts): ' + ', '.join(f'{k} {cls_tot[k] / Et * 100:.0f}% ({cls_n[k]} hops)' for k in cls_tot))
    # burstiness of the total lo power
    pl = np.sort(tot['lo'][sl])[::-1]
    P(f'  burstiness of the 20-150 Hz layer power: top 5% of the hops carry {pl[:len(pl) // 20].sum() / pl.sum() * 100:.0f}% , top 20% carry {pl[:len(pl) // 5].sum() / pl.sum() * 100:.0f}% (steady signal: 5%/20%)')
    P(f'  total lo/mid energy ratio (resynth): {db(tot["lo"][sl].sum()) - db(tot["mid"][sl].sum()):.1f} dB')
    P('')
open(B12 / f'q1b_{eng}.txt', 'w').write('\n'.join(rep)); print('\n'.join(rep))
