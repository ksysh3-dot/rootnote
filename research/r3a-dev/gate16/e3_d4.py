"""gate16 E3: emulate D4 (v1.6 literal) on the cached step25 streams (diag16 cache) and measure the V3h.rebound-like statistic.
Variants: base (v1.5 core), q9rule (i only + regrow cap after a forced hold, as Q9), cap (growth cap +16/hop always, no drop rule),
v16 ((i)&(ii) drop rule + always-on cap), v16i ((i) only + always-on cap).
Also an oracle: the A of a fixed-N single LS (N=57 and N=320) to show the noise-limited floor of the rebound statistic."""
import sys
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S
import proxy16 as PX

DT = 16 / 3000.0
sig, onsets = PX.sig_step_line(25.0)
D = PX.load('step25', sig)
d, raw, st, tc, hop, bh = D['d'], D['raw'], D['st'], D['tc'], D['hop'], D['bh']
H = len(tc)
fb_tab = PX.prev_freq_table(D)


def emulate(mode):
    scale = np.ones((H, 8)); Nc_map = np.zeros((H, 8)); fires = []
    voices = np.unique(d['voice'][st > 0])
    for v in voices:
        hs, js = np.nonzero((d['voice'] == v) & (st > 0)); o = np.argsort(hs); hs, js = hs[o], js[o]
        Nprev = None; force = 0; low = 0; regrow = False; pend = 0
        for k, (h, j) in enumerate(zip(hs, js)):
            Nco = int(raw[h, j, X.F_NP])
            if Nco <= 0 or st[h][j] not in (2, 3):
                continue
            n0 = hop[h] - 191
            if n0 - 330 < 0 or n0 + 30 >= len(bh):
                continue
            f = fb_tab[h, j]; fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400))
            ls1 = lambda N: S.ls_multi(bh, n0, [f], [fd], int(N))[0]
            nlo = int(np.clip(np.ceil(3000.0 / f), 30, 320))
            # --- target after the growth cap
            if mode in ('cap', 'v16', 'v16i'):
                Nc = Nco if Nprev is None else (min(Nco, Nprev + 16) if Nco > Nprev else Nco)
            elif mode == 'q9rule':
                Nc = Nco if (not regrow or Nprev is None) else min(Nco, Nprev + 16)
                if regrow and Nc >= Nco: regrow = False
            elif mode in ('lit', 'arm', 'nocap'):
                # own hysteresis emulation from the voice SNR (single-voice line: target = N_snr(SNR_v)); 25 %/3-hop rule; cap +16 per STEP
                snr_v = d['snr'][h][j]
                tgt = int(np.clip(30 if snr_v >= 30 else (320 if snr_v <= 12 else round(np.exp(np.log(nlo) + (30 - snr_v) / 18 * (np.log(320) - np.log(nlo))))), nlo, 320))
                if Nprev is None:
                    Nc = tgt; pend = 0
                else:
                    Nc = Nprev
                    if abs(tgt - Nprev) > .25 * Nprev or (mode == 'arm' and pend >= 3 and tgt != Nprev):
                        pend += 1
                        if pend >= 3:
                            if mode == 'nocap': Nc = tgt; pend = 0
                            elif tgt > Nprev:
                                Nc = min(tgt, Nprev + 16); pend = 0 if mode == 'lit' else (3 if Nc < tgt else 0)
                            else:
                                Nc = tgt; pend = 0
                    else:
                        pend = 0
            elif mode.startswith('N') and mode[1:].isdigit():
                Nc = int(mode[1:])
            else:
                Nc = Nco
            forced = False
            if mode in ('q9rule', 'v16', 'v16i'):
                if force > 0:
                    Nc = nlo; force -= 1; forced = True
                    if force == 0 and mode == 'q9rule': regrow = True
                else:
                    A_now = ls1(Nc); A_lo = ls1(nlo) if nlo != Nc else A_now
                    c1 = 20 * np.log10(max(A_lo, 1e-12) / max(A_now, 1e-12)) <= -6
                    c2 = True
                    if mode == 'v16':
                        # SNR_v 4 measured hops ago (previous 4 rows of this voice)
                        if k >= 4:
                            s_now = d['snr'][h][j]; s_old = d['snr'][hs[k - 4]][js[k - 4]]
                            c2 = (s_old - s_now) > 3.0
                        else:
                            c2 = False
                    drop = c1 and c2
                    low = low + 1 if drop else 0
                    if low >= 2:
                        force = 3; low = 0; fires.append((tc[h], int(v)))
            if Nc != Nco:
                scale[h, j] = np.clip(ls1(Nc) / max(ls1(Nco), 1e-12), 0.0, 10.0)
            Nc_map[h, j] = Nc; Nprev = Nc
    return scale, Nc_map, fires


def rebound_stats(scale, win=(-0.045, 0.05), post_win=0.05):
    reb, a32, mins = [], [], []
    for i in range(2, 40):
        t_e = i * PX.PER + PX.STEP_DUR; f0 = PX.STEP_NOTES[i]
        hs = np.flatnonzero((tc >= t_e + win[0]) & (tc <= t_e + win[1])); ser = []
        for h in hs:
            near = [j for j in range(8) if st[h][j] > 0 and abs(d['fosc'][h][j] - f0) <= .12 * f0]
            if not near: continue
            j = max(near, key=lambda q: d['A'][h][q]); ser.append((tc[h] - t_e, d['A'][h][j] * scale[h, j]))
        ser = np.array(ser)
        if len(ser) < 6: continue
        post = ser[(ser[:, 0] >= 0) & (ser[:, 0] <= post_win + 1e-9)]
        if len(post) < 4: continue
        k = int(np.argmin(post[:, 1]))
        reb.append(20 * np.log10(post[k:, 1].max() / max(post[k, 1], 1e-9)))
    reb = np.array(reb)
    return reb


def run():
    print('rebound = max(A after the min) / min(A), min taken within the first 0-50 ms (Q9 window) and within 0-80 ms (13.3 window); A = single-voice LS proxy x scale')
    for mode in ('base', 'nocap', 'lit', 'arm', 'cap'):
        scale, Nmap, fires = emulate(mode)
        r50 = rebound_stats(scale, (-.045, .05), .05)
        r80 = rebound_stats(scale, (-.045, .08), .08)
        # N path medians
        offs = (0, 16, 32, 48, 64, 96)
        npath = []
        for o in offs:
            vals = [Nmap[h, j] for i in range(2, 40) for h in np.flatnonzero(np.abs(tc - (i * PX.PER + PX.STEP_DUR + o / 1000.)) < 0.0027) for j in range(8) if Nmap[h, j] > 0]
            npath.append(np.median(vals) if vals else 0)
        amp, _ = PX.proxy_amp(D, scale); tt, env = PX.env_at(tc, amp, len(sig) / PX.FS)
        r, t, tl = PX.v3h_gated(tt, env)
        print(f'{mode:7s}: rebound(0-50ms) median {np.median(r50):5.1f} dB, >6 dB in {int((r50>6).sum())}/{len(r50)}; rebound(0-80ms) median {np.median(r80):5.1f} dB, >6 dB in {int((r80>6).sum())}/{len(r80)}; '
              f'firings {len(fires)} ({len(fires)/(len(sig)/PX.FS):.2f}/s); proxy tail(first -20dB) {PX.stat(t)}; settled tail {PX.stat(tl)}; N path (ms 0,16,32,48,64,96) {npath}')


if __name__ == '__main__':
    run()
