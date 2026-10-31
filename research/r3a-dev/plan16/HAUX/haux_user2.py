"""HAUX user windows, extra controls for Q3 (reads user_raw.pkl and the traces; fixed-frequency input change for ALL pairs, signed correlation, f_osc coincidence)."""
import os, sys, pickle, time
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
import numpy as np
from multiprocessing import Pool
from pathlib import Path
import haux_lib as H
import haux_user as U
HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')


def job(args):
    oi, win = args
    sk, t0, t1 = win
    z = np.load(HX / 'tmp' / f'{sk}_v15_trace.npz'); tr = {k: z[k].astype(np.float64) for k in z.files}
    hop = tr['hop'][:, 0]; tin = (hop - 382) / 3000.0 + U.CORE_T0 + U.LAG
    st, vid, a2, fo = tr['state'], tr['voice'], tr['a_2'], tr['f_osc']
    x = U.get_x(sk)
    outs = pickle.load(open(HX / 'user_raw.pkl', 'rb'))[oi]
    rows = []
    cache = {}
    def seg_of(h, W):
        if (h, W) not in cache:
            cache[(h, W)] = H.segment(x, int(round(tin[h] * U.FS)), H.WINLEN[W])
        return cache[(h, W)]
    for r in outs['recs']:
        h, s = r['h'], r['s']
        rec = dict(d_ren=r['d_ren'], sgn_ren=r['sign'], dfo=abs(fo[h, s] - fo[h - 1, s]))
        for W in (40, 85):
            w = H.hann(H.WINLEN[W])
            E, Ei, a_n = H.comb_fit(seg_of(h, W), w, fo[h, s])
            E, Ei, a_p = H.comb_fit(seg_of(h - 1, W), w, fo[h, s])        # fixed frequency 2 f_osc(h) in both hops
            ok = a_n[1] > 0 and a_p[1] > 0
            rec[f'dfix{W}'] = abs(20 * np.log10(a_n[1] / a_p[1])) if ok else np.nan
            rec[f'sfix{W}'] = np.sign(np.log(a_n[1] / a_p[1])) if ok else np.nan
            rec[f'sfol{W}'] = r[f'sgn{W}'] * r[f'din{W}']             # signed follow-voice change
        rows.append(rec)
    return rows


if __name__ == '__main__':
    t0 = time.time()
    with Pool(7) as p:
        res = p.map(job, list(enumerate(U.WINDOWS)))
    R = [r for rr in res for r in rr]
    pickle.dump(R, open(HX / 'user_raw2.pkl', 'wb'))
    L = []
    P = lambda s='': L.append(s)
    J = np.array([r['d_ren'] > 6 for r in R])
    dren_s = np.array([r['d_ren'] * r['sgn_ren'] for r in R])
    P(f'# HAUX user windows extra controls: pairs {len(R)}, jumps {J.sum()}')
    for W in (40, 85):
        dfix = np.array([r[f'dfix{W}'] for r in R]); sfix = np.array([r[f'sfix{W}'] for r in R]); ok = np.isfinite(dfix)
        sfol = np.array([r[f'sfol{W}'] for r in R]); okf = np.isfinite(sfol)
        sfix_s = dfix * sfix
        P(f'\n### window {W} ms')
        P(f'fixed-frequency input change (2 f_osc(h) in both hops): jump pairs: median {np.nanmedian(dfix[J]):.2f} dB, share < 2 dB {(dfix[J & ok] < 2).mean() * 100:.1f} % | non-jump pairs: median {np.nanmedian(dfix[~J]):.2f} dB, share < 2 dB {(dfix[~J & ok] < 2).mean() * 100:.1f} %')
        P(f'  share of pairs with fixed-freq input change >= 6 dB: jump {(dfix[J & ok] >= 6).mean() * 100:.1f} %, non-jump {(dfix[~J & ok] >= 6).mean() * 100:.1f} %')
        c1 = np.corrcoef(dren_s[ok], sfix_s[ok])[0, 1]; c2 = np.corrcoef(dren_s[J & ok], sfix_s[J & ok])[0, 1]
        P(f'signed correlation render dB step vs input dB step (fixed freq): all pairs {c1:.3f}, jump pairs {c2:.3f}')
        c3 = np.corrcoef(dren_s[okf], sfol[okf])[0, 1]; c4 = np.corrcoef(dren_s[J & okf], sfol[J & okf])[0, 1]
        P(f'signed correlation render step vs input step (follow-voice): all pairs {c3:.3f}, jump pairs {c4:.3f}')
        big = J & ok & (dfix >= 6)
        P(f'jumps whose input (fixed freq) moved >= 6 dB: {big.sum()} ({big.sum() / J.sum() * 100:.1f} % of jumps); same direction in {(np.sign(dren_s[big]) == sfix[big]).mean() * 100:.1f} %')
    dfo = np.array([r['dfo'] for r in R])
    P(f'\njumps coinciding with an f_osc change > 2 Hz at the same hop: {(dfo[J] > 2).mean() * 100:.1f} % (non-jump pairs: {(dfo[~J] > 2).mean() * 100:.1f} %)')
    for W in (40, 85):
        dfix = np.array([r[f'dfix{W}'] for r in R])
        m = J & (dfix < 2)
        P(f'W{W}: unsupported (fixed-freq) jumps with f_osc change > 2 Hz: {(dfo[m] > 2).mean() * 100:.1f} %')
    P(f'secs {time.time() - t0:.0f}')
    open(HX / 'user_report2.txt', 'w').write('\n'.join(L)); print('\n'.join(L))
