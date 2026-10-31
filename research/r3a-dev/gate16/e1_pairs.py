"""gate16 E1b: D1 premise check on the cached v1.5 core traces (10 Slakh TRAIN tracks).
Pair-hops = two LS-set voices (CAND/ON, or REL with c>0.1) whose basis frequencies (f_osc of the previous hop) are 3 .. 17.4 Hz apart (D1 range; < 3 Hz is the existing
merge) and exactly one of them is coasting (coast>0).  For those hops: which member is the right one (V6b label rule: within 50 cent of 0.5/1/2/3 x any sounding note),
how long the coasting member has been coasting, whether it later gets a track again (the voice survives = it was the real continuation), and the layer weight
w = (A c sigma)^2 of each member.  D1 removes the coasting member."""
import numpy as np
import common16 as C
import research_core_xcheck as X

LIM = 2 * 3000.0 / (320 + 24)   # 17.44 Hz


def main():
    cnt = {}
    W = {}
    coast_hist = {1: 0, 2: 0, 3: 0, 4: 0}
    recov = [0, 0]
    allrec = []
    for name in C.TRACKS:
        rf = C.ref(name)
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22)
        H = len(tc); st = d['state']
        w = np.where(st > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
        ever_on = set(int(d['voice'][h][j]) for h in range(H) for j in range(8) if st[h][j] == 2)
        # voice series for the look-ahead
        idx = {}
        for j in range(8):
            for h in range(H):
                if st[h][j] > 0:
                    idx[(int(d['voice'][h][j]), h)] = j
        prev_f = {}
        for h in range(H):
            cur_f = {int(d['voice'][h][j]): d['fosc'][h][j] for j in range(8) if st[h][j] > 0}
            if tc[h] > 0.5:
                L = [j for j in range(8) if st[h][j] in (1, 2) or (st[h][j] == 3 and d['c'][h][j] > .1)]
                if len(L) >= 2:
                    fb = {j: prev_f.get(int(d['voice'][h][j]), d['fosc'][h][j]) for j in L}
                    fn = None
                    for ia in range(len(L)):
                        for ib in range(ia + 1, len(L)):
                            ja, jb = L[ia], L[ib]
                            dfq = abs(fb[ja] - fb[jb])
                            if not (3.0 <= dfq < LIM): continue
                            ca, cb = d['coast'][h][ja] > 0, d['coast'][h][jb] > 0
                            if ca == cb: continue
                            jc, jt = (ja, jb) if ca else (jb, ja)
                            if fn is None:
                                f_ = C.targets_at(rf, tc[h], 'a'); fn = np.outer(f_, [.5, 1, 2, 3]).ravel() if len(f_) else np.array([])
                            lab = lambda f: (len(fn) == 0) or np.min(C.cents(f, fn)) > 50      # True = wrong
                            wc, wt = lab(d['fosc'][h][jc]), lab(d['fosc'][h][jt])
                            key = ('coast right' if not wc else 'coast wrong') + ' / ' + ('track right' if not wt else 'track wrong')
                            cnt[key] = cnt.get(key, 0) + 1
                            W[key] = W.get(key, 0.0) + w[h][jc]
                            W['TRK:' + key] = W.get('TRK:' + key, 0.0) + w[h][jt]
                            cc = int(d['coast'][h][jc])
                            coast_hist[min(cc, 4)] += 1
                            # look ahead: does the coasting voice get a track again within 48 hops?
                            v = int(d['voice'][h][jc]); ok = False
                            for hh in range(h + 1, min(H, h + 49)):
                                jj = idx.get((v, hh))
                                if jj is None: break
                                if d['coast'][hh][jj] == 0:
                                    ok = True; break
                            recov[0] += int(ok); recov[1] += 1
                            allrec.append((cc, ok, w[h][jc], not wc, d['A'][h][jc], d['A'][h][jt], w[h][jt], not wt, dfq,
                                           st[h][jt], float(int(d['voice'][h][jt]) in ever_on), st[h][jc],
                                           float(d['snr'][h][jt] >= 15.0 and raw[h, jt, X.F_PROM] > 0)))
            prev_f = cur_f
    tot = sum(cnt.values())
    print(f'pair-hops (3 <= df < {LIM:.1f} Hz, exactly one member coasting): {tot}')
    for k in sorted(cnt):
        print(f'  {k:32s}: {cnt[k]:6d} hops ({100*cnt[k]/tot:5.1f} %)  weight of the COASTING member {W[k]:8.3f}   weight of the TRACKED member {W["TRK:"+k]:8.3f}')
    wc_right = sum(v for k, v in W.items() if (not k.startswith('TRK')) and k.startswith('coast right'))
    wc_wrong = sum(v for k, v in W.items() if (not k.startswith('TRK')) and k.startswith('coast wrong'))
    print(f'weight D1 would remove: right {wc_right:.3f}, wrong {wc_wrong:.3f}  (right share of removed weight {100*wc_right/(wc_right+wc_wrong):.0f} %)')
    print(f'coast counter of the removed member at the hop: 1: {coast_hist[1]}, 2: {coast_hist[2]}, 3: {coast_hist[3]}, >=4: {coast_hist[4]}  ({100*coast_hist[1]/tot:.0f} % are 1-hop drop-outs)')
    print(f'the coasting member gets a track again within 48 hops (it was the real continuation): {recov[0]}/{recov[1]} = {100*recov[0]/recov[1]:.0f} %')
    ar = np.array(allrec, dtype=float)
    for lo, hi in ((1, 1), (2, 3), (4, 9), (10, 48)):
        m = (ar[:, 0] >= lo) & (ar[:, 0] <= hi)
        if m.sum():
            print(f'  coast {lo}-{hi}: {int(m.sum())} hops, recovers {100*ar[m,1].mean():.0f} %, weight {ar[m,2].sum():.3f}, right share by hops {100*ar[m,3].mean():.0f} %')
    tm = ar[:, 9]   # state of the tracked member
    for stv, nm in ((1, 'CAND'), (2, 'ON'), (3, 'REL')):
        m = tm == stv
        if m.sum():
            print(f'  tracked member is {nm}: {int(m.sum())} pair-hops ({100*m.mean():.0f} %), coasting member right in {100*ar[m,3].mean():.0f} %, coasting weight {ar[m,2].sum():.3f}, '
                  f'that tracked voice ever reaches ON: {100*ar[m,10].mean():.0f} %, coasting member recovers {100*ar[m,1].mean():.0f} %')
    mc = (tm == 1) & (ar[:, 10] == 0)
    print(f'  tracked member is a CAND that NEVER becomes ON: {int(mc.sum())} pair-hops ({100*mc.mean():.0f} %): D1 would eject a coasting voice for a non-voice; coasting right share {100*ar[mc,3].mean():.0f} %, '
          f'removed weight right {ar[mc & (ar[:,3]>0),2].sum():.3f} wrong {ar[mc & (ar[:,3]==0),2].sum():.3f}, recovers {100*ar[mc,1].mean():.0f} %')
    print('variants of the D1 predicate (removed weight of the coasting member): [right, wrong], share of hops that recover')
    base = lambda m: (ar[m & (ar[:, 3] > 0), 2].sum(), ar[m & (ar[:, 3] == 0), 2].sum(), ar[m, 1].mean() if m.sum() else 0, int(m.sum()))
    allm = np.ones(len(ar), bool)
    for lab, m in (('D1 as written (any coasting)', allm),
                   ('coast >= 2', ar[:, 0] >= 2), ('coast >= 4', ar[:, 0] >= 4), ('coast >= 8', ar[:, 0] >= 8), ('coast >= 12', ar[:, 0] >= 12),
                   ('coasting A < tracked A', ar[:, 4] < ar[:, 5]), ('coast >= 4 & coasting A < tracked A', (ar[:, 0] >= 4) & (ar[:, 4] < ar[:, 5])),
                   ('df < 8 Hz', ar[:, 8] < 8.0), ('df < 6 Hz & coast >= 4', (ar[:, 8] < 6.0) & (ar[:, 0] >= 4)),
                   ('tracked member ON', ar[:, 9] == 2), ('tracked ON, or CAND with (a)&(b) now', (ar[:, 9] == 2) | ((ar[:, 9] == 1) & (ar[:, 12] > 0))),
                   ('tracked ON & coasting A < tracked A', (ar[:, 9] == 2) & (ar[:, 4] < ar[:, 5])),
                   ('tracked ON/CAND(a,b) & coasting A < tracked A', (((ar[:, 9] == 2) | ((ar[:, 9] == 1) & (ar[:, 12] > 0)))) & (ar[:, 4] < ar[:, 5]))):
        r_, w_, rc, n = base(m)
        print(f'  {lab:40s}: hops {n:6d}, removed right {r_:6.3f} wrong {w_:6.3f} (right share {100*r_/max(r_+w_,1e-9):4.1f} %), recovers {100*rc:3.0f} %')


if __name__ == '__main__':
    main()
