"""gate16 E5d: D3 variants on the real-music traces: trigger set (CAND->ON + REL->ON as written vs CAND->ON only) and a bound on the boosted amplitude
(A_new <= rho_b * A with rho_b = inf (as written), 2.0, 1.41).  Pooled over the 10 Slakh train tracks: added layer weight (dB), share of the added weight that is wrong notes."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S

DT = 16 / 3000.0


def prep(name):
    z = np.load(C.CACHE / f's_{name}.npz'); det = z['det']
    tr = C.get_core(name)
    d, hop, tc = X.hops_of(tr); raw = np.asarray(tr).reshape(-1, 8, 22); st = d['state']
    rf = C.ref(name)
    return det, d, hop, tc, raw, st, rf


def run(P, trig, rho_b, tau=0.050):
    det, d, hop, tc, raw, st, rf = P
    H = len(tc); o = {}; prev = {}; prevf = {}
    e_old = e_new = add_w = add_r = 0.0
    cache = {}
    for h in range(H):
        cur = {int(d['voice'][h][j]): (int(st[h][j]), d['fosc'][h][j]) for j in range(8) if st[h][j] > 0}
        fn = None
        for j in range(8):
            if st[h][j] != 2 or tc[h] <= 0.5: continue
            v = int(d['voice'][h][j]); ps = prev.get(v, 0)
            fire = (ps in (0, 1)) or (trig == 'both' and ps == 3)
            if fire: o[v] = 1.0
            else: o[v] = o.get(v, 0.0) * np.exp(-DT / tau)
            A = d['A'][h][j]; c = d['c'][h][j]; sg = d['sig'][h][j]
            w_old = (A * c * sg) ** 2; Anew = A
            if o[v] > 0.02:
                key = (h, j)
                f = prevf.get(v, d['fosc'][h][j]); fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400)); n0 = int(hop[h]) - 191
                nlo = int(np.clip(np.ceil(3000.0 / f), 30, 320))
                if n0 - nlo - 30 >= 0 and n0 + 30 < len(det):
                    Af = S.ls_multi(det, n0, [f], [fd], nlo)[0]
                    Af = min(Af, rho_b * A) if np.isfinite(rho_b) else Af
                    Anew = A + o[v] * max(0.0, Af - A)
            w_new = (Anew * c * sg) ** 2
            e_old += w_old; e_new += w_new
            if w_new > w_old:
                if fn is None:
                    f_ = C.targets_at(rf, tc[h], 'a'); fn = np.outer(f_, [.5, 1, 2, 3]).ravel() if len(f_) else np.array([])
                wrong = (len(fn) == 0) or np.min(C.cents(d['fosc'][h][j], fn)) > 50
                if wrong: add_w += w_new - w_old
                else: add_r += w_new - w_old
        for v in list(o):
            if v not in cur: o.pop(v)
        prev = {v: s for v, (s, f) in cur.items()}; prevf = {v: f for v, (s, f) in cur.items()}
    return e_old, e_new, add_w, add_r


def main():
    Ps = [prep(n) for n in C.TRACKS]
    print('variant                              | pooled layer weight change | added weight wrong / right | wrong share of added weight')
    for trig, rho_b, tau in (('both', np.inf, .05), ('both', 2.0, .05), ('births', np.inf, .05), ('births', 2.0, .05), ('births', np.inf, .025), ('births', 4.0, .025), ('births', np.inf, .015)):
        eo = en = aw = ar = 0.0
        for P in Ps:
            a, b, c_, d_ = run(P, trig, rho_b, tau); eo += a; en += b; aw += c_; ar += d_
        print(f'triggers {trig:6s}, tau_o {1000*tau:3.0f} ms, boost bound {"none" if not np.isfinite(rho_b) else f"A_fast<={rho_b}A":12s} | {10*np.log10(en/eo):+5.2f} dB | {aw:6.2f} / {ar:6.2f} | {100*aw/max(aw+ar,1e-9):4.0f} %')


if __name__ == '__main__':
    main()
