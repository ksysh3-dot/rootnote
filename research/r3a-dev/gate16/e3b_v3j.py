"""gate16 E3b: false-trigger rate of the v1.6 drop rule ((i) & (ii), 2 consecutive measured hops) on the steady noisy tone signals of Q9.2.
Uses the same offline emulation as q9 (single-voice LS on the engine bh stream), but with the SNR-fall condition (ii) added."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S
import proxy16 as PX
import research_core_signals as RS

DT = 16 / 3000.0


def firings(D, use_ii, nocap=False):
    d, raw, st, tc, hop, bh = D['d'], D['raw'], D['st'], D['tc'], D['hop'], D['bh']
    H = len(tc); fb = PX.prev_freq_table(D)
    n_fire = 0; on_s = (st == 2).sum() * DT
    for v in np.unique(d['voice'][st > 0]):
        hs, js = np.nonzero((d['voice'] == v) & (st > 0)); o = np.argsort(hs); hs, js = hs[o], js[o]
        Nprev = None; force = 0; low = 0
        for k, (h, j) in enumerate(zip(hs, js)):
            Nco = int(raw[h, j, X.F_NP])
            if Nco <= 0 or st[h][j] not in (2, 3): continue
            n0 = hop[h] - 191
            if n0 - 330 < 0 or n0 + 30 >= len(bh): continue
            f = fb[h, j]; fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400))
            ls1 = lambda N: S.ls_multi(bh, n0, [f], [fd], int(N))[0]
            nlo = int(np.clip(np.ceil(3000.0 / f), 30, 320))
            Nc = Nco if (Nprev is None or nocap) else (min(Nco, Nprev + 16) if Nco > Nprev else Nco)
            if force > 0:
                Nc = nlo; force -= 1
            else:
                A_now = ls1(Nc); A_lo = ls1(nlo) if nlo != Nc else A_now
                c1 = 20 * np.log10(max(A_lo, 1e-12) / max(A_now, 1e-12)) <= -6
                c2 = True
                if use_ii:
                    c2 = (k >= 4) and ((d['snr'][hs[k - 4]][js[k - 4]] - d['snr'][h][j]) > 3.0)
                low = low + 1 if (c1 and c2) else 0
                if low >= 2:
                    force = 3; low = 0; n_fire += 1
            Nprev = Nc
    return n_fire, on_s


def main():
    sigs = []
    xb, _ = PX.sig_bass_pink_snr(6.0, 8.0); sigs.append(('bass(350ms decay)+pink band SNR 6 dB', 'bassp6', xb))
    xs, _ = PX.sig_steady(6.0, 10.0); sigs.append(('steady 100 Hz + pink SNR 6 dB', 'steady6', xs))
    x8, _ = PX.sig_steady(8.0, 10.0); sigs.append(('steady 100 Hz + pink SNR 8 dB', 'steady8', x8))
    xt = RS.load_excerpt(RS.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0); sigs.append(('Track00060 36-48 s', 't60_36_48', xt))
    print('| signal | ON voice-s | (i) only firings /ON-s | (i)&(ii) firings /ON-s |')
    for lab, key, x in sigs:
        D = PX.load(key, x)
        a, on_s = firings(D, False); b, _ = firings(D, True)
        print(f'| {lab} | {on_s:.1f} | {a} ({a/on_s:.2f}) | {b} ({b/on_s:.2f}) |')


if __name__ == '__main__':
    main()
