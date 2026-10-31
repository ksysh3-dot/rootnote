"""Q2b: energy-weighted classification of the P1 permission for the v15 voices that carry the 20-150 Hz energy: k=2 mask (permission),
input-grid evidence, P1 target amplitude vs v15 a_2. usage: b12_q2b.py [eng]"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
from b12_p1join import *
eng = sys.argv[1] if len(sys.argv) > 1 else 'v15'
rep = []; P = rep.append
allrec = []
for sk, t0, t1 in WINDOWS:
    sy = synth(sk, eng, t0, t1)
    lo, hi = sy['sel_lo'], sy['sel_hi']; sl = slice(lo, hi)
    cpw = {k: band_hop_power(x, ('lo', 'mid')) for k, x in sy['comp'].items()}
    ci, tk, hm, hd = p1_tracks(sk); ids = tid(tk); pos = {int(c): i for i, c in enumerate(ci)}
    tr = load(sk, eng)['tr']; coast = tr['coasting'][sy['ix']]; trk = tr['track'][sy['ix']]
    recs = []
    for v in {v for (v, k) in cpw}:
        plo = sum(c['lo'] for (vv, kk), c in cpw.items() if vv == v)
        pmid = sum(c['mid'] for (vv, kk), c in cpw.items() if vv == v)
        for s in range(8):
            for h in np.where(sy['vid'][:, s] == v)[0]:
                if not (lo <= h < hi) or sy['st'][h, s] < 1: continue
                j = pos.get(int(sy['hops'][h])); a2 = sy['a'][0][h, s]
                row = np.where((ids[j] == int(trk[h, s])) & (tk[j][:, 1] > 0))[0] if (j is not None and trk[h, s] > 0) else []
                if len(row) == 0:
                    recs.append((plo[h], pmid[h], 0, np.nan, np.nan, np.nan, int(coast[h, s] > 0), sy['fo'][h, s]))
                else:
                    t = tk[j][row[0]]; hh = hm[j][row[0]][0]
                    recs.append((plo[h], pmid[h], 1, hh[2], hh[5], 20 * np.log10(max(hh[0], 1e-12) / max(a2, 1e-12)), int(t[1]), sy['fo'][h, s]))
    R = np.array(recs, float)
    allrec.append(R)
    W = R[:, 0]; Wm = R[:, 1]
    def sh(m, w=W): return w[m].sum() / w.sum() * 100
    nt = R[:, 2] == 0
    has = ~nt
    mask = np.where(has, R[:, 3], np.nan); ev = R[:, 4]; dT = R[:, 5]
    cls = {
        'no P1 track with this id (tracker lost it, v15 voice still coasting)': nt,
        'P1 track present, k=2 permission 0 (mask 0)': has & (mask <= 1e-6),
        'P1 track present, 0 < mask < 0.5': has & (mask > 1e-6) & (mask < 0.5),
        'P1 track present, mask >= 0.5': has & (mask >= 0.5),
    }
    P(f'=== {sk} {t0} (v15 voices, all voices of the window; weights = 20-150 Hz hop power | 150-600 Hz hop power)')
    for n_, m in cls.items():
        P(f'  {n_}: lo {sh(m):5.1f}% | mid {sh(m, Wm):5.1f}% | hop-slots {m.sum()}')
    m0 = cls['P1 track present, k=2 permission 0 (mask 0)']
    P(f'  within mask 0: input-grid evidence (0 = no input partial within tolGrid of 2f): evidence==0 share lo {sh(m0 & (ev <= 1e-6)):.1f}% of total; evidence>0 {sh(m0 & (ev > 1e-6)):.1f}%')
    mm_ = has & (mask > 1e-6)
    P(f'  where P1 does sound k=2: P1 target amplitude vs v15 a_2 (dB, P1-v15) lo-weighted median {np.median(dT[mm_]) if mm_.any() else np.nan:+.1f}; mask lo-weighted median {np.median(mask[mm_]) if mm_.any() else np.nan:.2f}')
    P('')
Rall = np.vstack(allrec)
W = Rall[:, 0]; Wm = Rall[:, 1]; has = Rall[:, 2] == 1; mask = Rall[:, 3]
P('=== pooled over the four windows (equal weight per hop-slot power, so louder windows count more)')
for n_, m in {'no P1 track with this id': ~has, 'P1 track, mask 0': has & (mask <= 1e-6), 'P1 track, 0<mask<0.5': has & (mask > 1e-6) & (mask < .5), 'P1 track, mask>=0.5': has & (mask >= .5)}.items():
    P(f'  {n_}: lo {W[m].sum() / W.sum() * 100:5.1f}% | mid {Wm[m].sum() / Wm.sum() * 100:5.1f}%')
open(B12 / f'q2b_{eng}.txt', 'w').write('\n'.join(rep)); print('\n'.join(rep))
