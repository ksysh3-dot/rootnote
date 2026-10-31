"""gate16 E5c: how much layer energy would D3 add on real music?  Offline D3 emulation on the cached v1.5 core traces + detailRing52_ streams (10 Slakh train tracks, LOGOFF):
triggers = CAND->ON and REL->ON (the two observable ones; transition entry is not in the trace, so this is a lower bound), o = 1 at the trigger, exp(-dt/tau_o) afterwards
(tau_o = 50 ms), A_fast = single-voice LS on det with window N_lo,v past / N_f=24 future at the voice's basis frequency, A_new = A + o*max(0, A_fast - A) (no D2 cap).
Reports 10log10(sum (A_new c sigma)^2 / sum (A c sigma)^2) over all voice hops, the share of voice-hops with o > 0.1, and (Slakh tracks) the added energy split into wrong / right notes."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S

DT = 16 / 3000.0
TAU = 0.050


def run(name, labels=True, tau=TAU):
    z = np.load(C.CACHE / f's_{name}.npz'); det = z['det']
    tr = C.get_core(name) if name != 'LOGOFF' else z['trace']
    d, hop, tc = X.hops_of(tr); raw = np.asarray(tr).reshape(-1, 8, 22); st = d['state']; H = len(tc)
    rf = C.ref(name) if (labels and name != 'LOGOFF') else None
    o = {}; prev = {}; prevf = {}
    e_old = e_new = 0.0; n_on = n_boost = 0; add_w = add_r = 0.0
    for h in range(H):
        cur = {int(d['voice'][h][j]): (int(st[h][j]), d['fosc'][h][j]) for j in range(8) if st[h][j] > 0}
        fn = None
        for j in range(8):
            if st[h][j] != 2 or tc[h] <= 0.5: continue
            v = int(d['voice'][h][j]); ps = prev.get(v, 0)
            if ps in (0, 1, 3): o[v] = 1.0
            else: o[v] = o.get(v, 0.0) * np.exp(-DT / tau)
            A = d['A'][h][j]; c = d['c'][h][j]; sg = d['sig'][h][j]
            w_old = (A * c * sg) ** 2; n_on += 1
            Anew = A
            if o[v] > 0.02:
                f = prevf.get(v, d['fosc'][h][j]); fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400)); n0 = int(hop[h]) - 191
                nlo = int(np.clip(np.ceil(3000.0 / f), 30, 320))
                if n0 - nlo - 30 >= 0 and n0 + 30 < len(det):
                    Af = S.ls_multi(det, n0, [f], [fd], nlo)[0]
                    Anew = A + o[v] * max(0.0, Af - A)
                if o[v] > 0.1: n_boost += 1
            w_new = (Anew * c * sg) ** 2
            e_old += w_old; e_new += w_new
            if rf is not None and w_new > w_old:
                if fn is None:
                    f_ = C.targets_at(rf, tc[h], 'a'); fn = np.outer(f_, [.5, 1, 2, 3]).ravel() if len(f_) else np.array([])
                wrong = (len(fn) == 0) or np.min(C.cents(d['fosc'][h][j], fn)) > 50
                if wrong: add_w += w_new - w_old
                else: add_r += w_new - w_old
        for v in list(o):
            if v not in cur: o.pop(v)
        prev = {v: s for v, (s, f) in cur.items()}; prevf = {v: f for v, (s, f) in cur.items()}
    return e_old, e_new, n_on, n_boost, add_w, add_r


def main():
    tot_old = tot_new = 0.0; aw = ar = 0.0
    for name in C.TRACKS + ['LOGOFF']:
        eo, en, n_on, nb, a_w, a_r = run(name)
        print(f'{name:11s}: layer weight sum old {eo:8.3f} -> with D3 {en:8.3f} ({10*np.log10(en/eo):+5.2f} dB); ON voice-hops with o>0.1: {100*nb/max(n_on,1):4.1f} %'
              + (f'; added weight wrong {a_w:.3f} right {a_r:.3f}' if name != 'LOGOFF' else ''))
        if name != 'LOGOFF':
            tot_old += eo; tot_new += en; aw += a_w; ar += a_r
    print(f'POOLED Slakh: {10*np.log10(tot_new/tot_old):+5.2f} dB layer weight; added weight wrong {aw:.2f} right {ar:.2f} ({100*aw/(aw+ar):.0f} % of the added weight is wrong notes; baseline wrong share 34.5 %)')


if __name__ == '__main__':
    main()
