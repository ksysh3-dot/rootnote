"""gate16 E4c: complete D5 admission test on real music.  For never-born CAND episodes with >= 2 consecutive hops of SNR_v >= 25 dB and engine evidence (b) = 0:
apply (c) (|df|/f <= 3 %, |df| <= 200 Hz/s * dt between the two hops) and (b') on the bh spectrum at both hops (k=1..4, local max within max(4 Hz, 3 % k f),
>= 6 dB over the +-27-bin median, 'clamp' edge).  Reports how many would be BORN under v1.6 per second and how many of them are wrong notes (V6b rule).
Also gives the same statistic for the voices that v1.5 does admit (CAND -> ON) so the scale of the change is visible."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import e4_d5 as E

F_PROM = X.F_PROM


def main():
    tot = dict(cand=0, c_ok=0, adm=0, adm_wrong=0, dur=0.0, w_adm_wrong=0.0, w_adm_right=0.0)
    on_births = 0; on_births_wrong = 0
    for name in C.TRACKS:
        rf = C.ref(name)
        z = np.load(C.CACHE / f's_{name}.npz'); bh = z['bh']
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22)
        st = d['state']; dur = tc[-1] - 0.5
        hs, js = np.nonzero(st > 0); ids = d['voice'][hs, js]
        order = np.lexsort((hs, ids)); hs, js, ids = hs[order], js[order], ids[order]
        cuts = np.r_[0, np.flatnonzero(np.diff(ids) != 0) + 1, len(ids)]
        n_c = n_cok = n_adm = n_adm_wrong = 0; wr = rt = 0.0; n_adm_k2 = 0
        for a, b in zip(cuts[:-1], cuts[1:]):
            h_, j_ = hs[a:b], js[a:b]
            if tc[h_[0]] <= 0.5: continue
            s_ = st[h_, j_]
            if np.any(s_ == 2):
                # born voice: label at its first ON row
                k = int(np.flatnonzero(s_ == 2)[0]); f = raw[h_[k], j_[k], X.F_FTR]
                fn = C.targets_at(rf, tc[h_[k]], 'a'); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
                on_births += 1; on_births_wrong += int((not len(tgt)) or np.min(C.cents(f, tgt)) > 50)
                continue
            cm = s_ == 1; snr = d['snr'][h_, j_]; prom = raw[h_, j_, F_PROM]; f = raw[h_, j_, X.F_FTR]
            cond = cm & (snr >= 25.0) & (prom == 0)
            two = np.flatnonzero(cond[1:] & cond[:-1])
            if len(two) == 0: continue
            k = int(two[0]); n_c += 1
            dt = (hop[h_[k + 1]] - hop[h_[k]]) / 3000.0
            df = abs(f[k + 1] - f[k])
            if not (df <= .03 * f[k + 1] and df <= 200.0 * dt): continue
            n_cok += 1
            ok = True; ok2 = True
            for kk in (k, k + 1):
                mag = E.bh_mag(bh, int(hop[h_[kk]]))
                best, per = E.bprime(mag, f[kk], 'clamp')
                if best is None or best < 6.0: ok = False
                v2 = [v for v in per[1:] if v is not None]
                if not v2 or max(v2) < 6.0: ok2 = False
            n_adm_k2 += int(ok2)
            if not ok: continue
            n_adm += 1
            fn = C.targets_at(rf, tc[h_[k]], 'a'); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
            wrong = (not len(tgt)) or np.min(C.cents(f[k], tgt)) > 50
            n_adm_wrong += int(wrong)
            A = d['A'][h_[k + 1]][j_[k + 1]]
            if wrong: wr += A * A
            else: rt += A * A
        print(f'{name}: candidates {n_c} -> (c) ok {n_cok} -> (b\') ok = admitted {n_adm} ({n_adm/dur:.2f}/s), wrong {n_adm_wrong}; with k>=2 only (c-ok ones): {n_adm_k2}')
        tot['k2'] = tot.get('k2', 0) + n_adm_k2
        tot['cand'] += n_c; tot['c_ok'] += n_cok; tot['adm'] += n_adm; tot['adm_wrong'] += n_adm_wrong; tot['dur'] += dur
        tot['w_adm_wrong'] += wr; tot['w_adm_right'] += rt
    print(f"\nPOOLED over {tot['dur']:.0f} s: pattern episodes {tot['cand']}; pass (c) {tot['c_ok']}; pass (b') too = would be BORN by D5: {tot['adm']} ({tot['adm']/tot['dur']:.2f}/s), "
          f"wrong notes {tot['adm_wrong']} ({100*tot['adm_wrong']/max(tot['adm'],1):.0f} %)")
    print(f"v1.5 itself: voices that reached ON in the same 299 s: {on_births} ({on_births/tot['dur']:.2f}/s), wrong at first ON row {100*on_births_wrong/max(on_births,1):.0f} %")
    print(f"CAND-stage A^2 sum of the admitted: wrong {tot['w_adm_wrong']:.3f}, right {tot['w_adm_right']:.3f}")


if __name__ == '__main__':
    main()
