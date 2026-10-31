"""gate16 E1c: footprint of D1 with the literal predicate 'closer than 2*kappa*fs/(N_J+N_f) at the CURRENT window N_J' (not at 320).
N_J is not in the 22-field trace for stage-2 voices; estimate N_J_cur = max over the LS voices of the traced Np (the stage-1-only voices show N_J itself, the stage-2 voices
N_v <= N_J, so this is a LOWER bound of the current N_J and therefore a lower bound of the D1 footprint).  Counts hops where one member is coasting and the other tracked."""
import numpy as np
import common16 as C
import research_core_xcheck as X

LIM320 = 2 * 3000.0 / (320 + 24)


def main():
    rows = []
    for name in C.TRACKS:
        rf = C.ref(name)
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22); st = d['state']; H = len(tc)
        w = np.where(st > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
        prev_f = {}
        for h in range(H):
            cur_f = {int(d['voice'][h][j]): d['fosc'][h][j] for j in range(8) if st[h][j] > 0}
            if tc[h] > 0.5:
                L = [j for j in range(8) if st[h][j] in (1, 2) or (st[h][j] == 3 and d['c'][h][j] > .1)]
                if len(L) >= 2:
                    fb = {j: prev_f.get(int(d['voice'][h][j]), d['fosc'][h][j]) for j in L}
                    njc = max(int(raw[h, j, X.F_NP]) for j in L)
                    lim_cur = 2 * 3000.0 / (njc + 24)
                    fn = None
                    for ia in range(len(L)):
                        for ib in range(ia + 1, len(L)):
                            ja, jb = L[ia], L[ib]
                            dfq = abs(fb[ja] - fb[jb])
                            if dfq < 3.0 or dfq >= lim_cur: continue
                            ca, cb = d['coast'][h][ja] > 0, d['coast'][h][jb] > 0
                            if ca == cb: continue
                            jc, jt = (ja, jb) if ca else (jb, ja)
                            if fn is None:
                                f_ = C.targets_at(rf, tc[h], 'a'); fn = np.outer(f_, [.5, 1, 2, 3]).ravel() if len(f_) else np.array([])
                            wrongc = (len(fn) == 0) or np.min(C.cents(d['fosc'][h][jc], fn)) > 50
                            rows.append((dfq, njc, lim_cur, w[h][jc], not wrongc, st[h][jt]))
    ar = np.array(rows, float)
    n320 = (ar[:, 0] < LIM320)
    print(f'D1 fires (literal, current N_J lower bound) on {len(ar)} pair-hops; of them with df < 17.4 Hz (what Q10/Q7 looked at): {int(n320.sum())}; df between 17.4 and the current limit: {int((~n320).sum())}')
    far = ~n320
    print(f'  the extra {int(far.sum())} hops: coasting-member weight right {ar[far & (ar[:,4]>0),3].sum():.3f} wrong {ar[far & (ar[:,4]==0),3].sum():.3f}; median df {np.median(ar[far,0]):.1f} Hz, median current N_J {np.median(ar[far,1]):.0f}')
    print(f'  all: weight removed right {ar[ar[:,4]>0,3].sum():.3f} wrong {ar[ar[:,4]==0,3].sum():.3f}')
    for lo, hi in ((3, 17.4), (17.4, 30), (30, 50), (50, 120)):
        m = (ar[:, 0] >= lo) & (ar[:, 0] < hi)
        if m.sum(): print(f'  df {lo}-{hi} Hz: {int(m.sum())} hops, right-weight {ar[m & (ar[:,4]>0),3].sum():.3f}, wrong-weight {ar[m & (ar[:,4]==0),3].sum():.3f}, N_J_cur median {np.median(ar[m,1]):.0f}')


if __name__ == '__main__':
    main()
