"""gate16 E4d: who would D5 speed up?  Voices that DID reach ON in v1.5 (10 Slakh train tracks): their CAND phase length and how many of the CAND hops were held back
by evidence (b) alone ((a) SNR >= 15 held, (b) did not), and for those hops whether SNR_v >= 25 dB (the D5 precondition) held.  Right/wrong split by the V6b rule at the ON row."""
import numpy as np
import common16 as C
import research_core_xcheck as X


def main():
    n = 0; held = 0; held25 = 0; right_held = right_held25 = 0; right = 0
    lens = []; delay_b = []; delay_b25 = []
    for name in C.TRACKS:
        rf = C.ref(name)
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22)
        st = d['state']
        hs, js = np.nonzero(st > 0); ids = d['voice'][hs, js]
        order = np.lexsort((hs, ids)); hs, js, ids = hs[order], js[order], ids[order]
        cuts = np.r_[0, np.flatnonzero(np.diff(ids) != 0) + 1, len(ids)]
        for a, b in zip(cuts[:-1], cuts[1:]):
            h_, j_ = hs[a:b], js[a:b]
            s_ = st[h_, j_]
            if tc[h_[0]] <= 0.5 or s_[0] != 1 or not np.any(s_ == 2): continue
            k_on = int(np.flatnonzero(s_ == 2)[0])
            cand = np.arange(k_on)
            snr = d['snr'][h_, j_][cand]; prom = raw[h_, j_, X.F_PROM][cand]
            held_rows = (snr >= 15.0) & (prom == 0)
            held25_rows = held_rows & (snr >= 25.0)
            f = raw[h_[k_on], j_[k_on], X.F_FTR]
            fn = C.targets_at(rf, tc[h_[k_on]], 'a'); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
            isright = not ((not len(tgt)) or np.min(C.cents(f, tgt)) > 50)
            n += 1; right += int(isright); lens.append(k_on)
            if held_rows.any():
                held += 1; right_held += int(isright)
                delay_b.append(int(held_rows.sum()))
            if held25_rows.any():
                held25 += 1; right_held25 += int(isright)
                delay_b25.append(int(held25_rows.sum()))
    print(f'voices that reached ON (born as CAND): {n} (right at the ON row: {100*right/n:.0f} %); CAND phase length median {np.median(lens):.0f} hops, p90 {np.percentile(lens,90):.0f}')
    print(f'  with >=1 CAND hop where (a) held and (b) did not: {held} ({100*held/n:.0f} %), of those right {100*right_held/max(held,1):.0f} %; median such hops {np.median(delay_b) if delay_b else 0:.0f}')
    print(f'  ... of which D5-eligible (>=1 of those hops with SNR_v >= 25 dB): {held25} ({100*held25/n:.1f} % of all births), right {100*right_held25/max(held25,1):.0f} %')


if __name__ == '__main__':
    main()
