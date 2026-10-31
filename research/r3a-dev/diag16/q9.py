"""Q9: tail candidate evaluated OFFLINE.  The core's window choice (np field = N_v / N_J actually used per voice-hop) is kept as the 'target'; the candidate adds
the amplitude-drop rule: if A_LS(N_min=30) <= A_LS(current window) - 6 dB on 2 consecutive hops -> N = 30 for the following 3 hops, afterwards re-growth of N
limited to +16 samples per hop until the core's target is reached.  A_LS = single-voice LS on the engine's bh stream (core window shape).  The candidate's A for
the proxy layer is A_trace * A_LS(N_cand) / A_LS(N_core).  False triggers = rule firings per second."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_signals as RS
import streams16 as S
import proxy16 as PX

DT = 16 / 3000.0
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def emulate(D, rule=True):
    d, raw, st, tc, hop, bh = D['d'], D['raw'], D['st'], D['tc'], D['hop'], D['bh']
    H = len(tc); fb = PX.prev_freq_table(D)
    scale = np.ones((H, 8)); Nc_map = np.zeros((H, 8)); trig = []
    voices = np.unique(d['voice'][st > 0])
    for v in voices:
        hs, js = np.nonzero((d['voice'] == v) & (st > 0)); o = np.argsort(hs); hs, js = hs[o], js[o]
        force = 0; regrow = False; low = 0; Nprev = None
        for h, j in zip(hs, js):
            Nco = int(raw[h, j, X.F_NP])
            if Nco <= 0 or st[h][j] not in (2, 3):
                continue
            n0 = hop[h] - 191
            if n0 - Nco < 0 or n0 + 30 >= len(bh):
                continue
            f = fb[h, j]; fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400))
            ls1 = lambda N: S.ls_multi(bh, n0, [f], [fd], int(N))[0]
            forced = False
            if not rule:
                Nc = Nco
            elif force > 0:
                Nc = 30; force -= 1; forced = True
                if force == 0:
                    regrow = True
            else:
                Nc = Nco if not regrow or Nprev is None else min(Nco, Nprev + 16)
                if regrow and Nc >= Nco:
                    regrow = False
            if rule and not forced:
                A30 = ls1(30) if Nc != 30 else None
                ANc = ls1(Nc)
                if A30 is None:
                    A30 = ANc
                drop = 20 * np.log10(max(A30, 1e-12) / max(ANc, 1e-12)) <= -6
                low = low + 1 if drop else 0
                if low >= 2:
                    force = 3; low = 0; trig.append((tc[h], int(v)))
            if Nc != Nco:
                scale[h, j] = np.clip(ls1(Nc) / max(ls1(Nco), 1e-12), 0.0, 10.0)
            Nc_map[h, j] = Nc; Nprev = Nc
    return scale, Nc_map, trig


def line_metrics(D, scale, dur, label):
    amp, _ = PX.proxy_amp(D, scale); tt, env = PX.env_at(D['tc'], amp, dur)
    r, t, tl = PX.v3h_gated(tt, env)
    # rebound of the dominant voice's A (candidate) within 0-50 ms after the note end
    d, st, tc = D['d'], D['st'], D['tc']; reb = []; a32 = []
    for i in range(2, 40):
        t_e = i * PX.PER + PX.STEP_DUR; f0 = PX.STEP_NOTES[i]
        hs = np.flatnonzero((tc >= t_e - .045) & (tc <= t_e + .05)); ser = []
        for h in hs:
            near = [j for j in range(8) if st[h][j] > 0 and abs(d['fosc'][h][j] - f0) <= .12 * f0]
            if not near:
                continue
            j = max(near, key=lambda q: d['A'][h][q]); ser.append((tc[h] - t_e, d['A'][h][j] * scale[h, j]))
        ser = np.array(ser)
        pre = ser[(ser[:, 0] >= -.045) & (ser[:, 0] <= -.008), 1].mean()
        post = ser[ser[:, 0] >= 0]
        k = int(np.argmin(post[:, 1])); reb.append(20 * np.log10(post[k:, 1].max() / max(post[k, 1], 1e-9)))
        q = np.argmin(np.abs(post[:, 0] - .032)); a32.append(20 * np.log10(max(post[q, 1], 1e-9) / pre))
    reb = np.array(reb)
    P(f'  {label}: proxy tail first -20 dB {PX.stat(t)} ms; settled tail (last above -20 dB) {PX.stat(tl)} ms; A rebound median {np.median(reb):.1f} dB, notes with rebound > 6 dB {int((reb>6).sum())}/{len(reb)}; A at +32 ms re pre-end median {np.median(a32):+.1f} dB')
    return t, tl


def main():
    sig, onsets = PX.sig_step_line(25.0)
    D = PX.load('step25', sig); dur = len(sig) / PX.FS
    P('### Q9.1 gated step line, band SNR 25 dB (proxy layer; real layer: tail first -20 dB median 44.2 [5.1, 64.1] ms, settled tail 60.2 ms, A rebound median 15.8 dB in 31/38 notes)')
    sc0, N0, tr0 = emulate(D, rule=False)
    line_metrics(D, np.ones((len(D['tc']), 8)), dur, 'baseline (core as is)')
    sc1, N1, tr1 = emulate(D, rule=True)
    line_metrics(D, sc1, dur, 'with the drop rule')
    on_s = (D['st'] == 2).sum() * DT
    P(f'  rule firings on the line: {len(tr1)} in {dur:.1f} s ({len(tr1)/dur:.2f}/s; {len(tr1)/38:.2f} per note of 38 note ends; legitimate firings are expected at every note end)')
    # timing of the firings relative to the note end
    rel = []
    for (t_, v) in tr1:
        k = np.floor((t_ - PX.STEP_DUR) / PX.PER + 1e-9); t_end = k * PX.PER + PX.STEP_DUR
        rel.append((t_ - t_end) * 1000)
    rel = np.array(rel)
    P(f'  firing times relative to the preceding note end (ms): median {np.median(rel):.1f}, p10 {np.percentile(rel,10):.1f}, p90 {np.percentile(rel,90):.1f}; fraction within -10..+40 ms of a note end {100*np.mean((rel>-10)&(rel<40)):.0f} %')
    # N path
    P('  median N_core vs N_candidate at offsets from the note end (ms): ' + '; '.join(
        f'{o:+d}: {np.median([N0[h, j] for i in range(2, 40) for h in np.flatnonzero(np.abs(D["tc"] - (i*PX.PER+PX.STEP_DUR + o/1000.)) < 0.0027) for j in range(8) if N0[h, j] > 0] or [0]):.0f} / '
        f'{np.median([N1[h, j] for i in range(2, 40) for h in np.flatnonzero(np.abs(D["tc"] - (i*PX.PER+PX.STEP_DUR + o/1000.)) < 0.0027) for j in range(8) if N1[h, j] > 0] or [0]):.0f}' for o in (0, 16, 32, 48, 64)))
    P('\n### Q9.2 false triggers per second of the rule (rule firings; no true amplitude drop is intended in the steady cases)')
    P('| signal | audio s | ON voice-seconds | firings | per audio second | per ON voice-second |')
    P('|---|---|---|---|---|---|')
    sigs = []
    xb, _ = PX.sig_bass_pink_snr(6.0, 8.0); sigs.append(('(i-a) bass notes (350 ms decay) + pink, band SNR 6 dB', 'bassp6', xb))
    xs, _ = PX.sig_steady(6.0, 10.0); sigs.append(('(i-b) steady 100 Hz tone + pink, band SNR 6 dB', 'steady6', xs))
    x8, _ = PX.sig_steady(8.0, 10.0); sigs.append(('(ii) SNR 8 dB chatter tone (steady 100 Hz + pink)', 'steady8', x8))
    xt = RS.load_excerpt(RS.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0); sigs.append(('(iii) Track00060 36-48 s (real music; firings include true amplitude drops)', 't60_36_48', xt))
    for lab, key, x in sigs:
        Dx = PX.load(key, x)
        _, _, tr = emulate(Dx, rule=True)
        n = len(x) if np.ndim(x) == 1 else x.shape[0]
        secs = n / PX.FS; onv = (Dx['st'] == 2).sum() * DT
        P(f'| {lab} | {secs:.1f} | {onv:.1f} | {len(tr)} | {len(tr)/secs:.2f} | {len(tr)/max(onv,1e-9):.2f} |')
        if key == 'bassp6':
            inter = 0
            for (t_, v) in tr:
                u = t_ % 0.5
                inter += int(0.04 <= u <= 0.40)
            P(f'      of these {inter} fall 40-400 ms after a bass onset (note interior), the rest at the onset or at the decay end where the amplitude really changes')
    open(C.D16 / 'q9_report.txt', 'w').write('\n'.join(out))


if __name__ == '__main__':
    main()
