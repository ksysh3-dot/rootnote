"""gate16 E5: D3 (onset boost) checks on cached v1.5 streams.
(1) steady-state gain/bias: A_fast (single-voice LS on detailRing52_, window N_lo,v past / N_f=24 future) vs the traced A (final) of ON voices, c > 0.9, in
    clean and noisy steady tones and in real music.  D3 adds o_v * max(0, A_fast - A): any steady-state excess is boost the moment a trigger fires.
(2) trigger statistics on real music: CAND->ON and REL->ON events per second, and their coincidence with drum onsets (0..120 ms after any drum / kick MIDI onset)
    compared with the share of time covered by such windows."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S


def a_fast(x, n0, f, fd, N):
    return S.ls_multi(x, n0, [f], [fd], int(N))[0]


def steady(key, label, tmin=0.6, tmax=1e9):
    z = np.load(C.CACHE / f's_{key}.npz'); bh, det = z['bh'], z['det']
    d, hop, tc = X.hops_of(z['trace']); raw = np.asarray(z['trace']).reshape(-1, 8, 22)
    H = len(tc); r_det, r_bh, exc = [], [], []
    prev = {}
    for h in range(H):
        cur = {int(d['voice'][h][j]): d['fosc'][h][j] for j in range(8) if d['state'][h][j] > 0}
        if tmin < tc[h] < tmax:
            for j in range(8):
                if d['state'][h][j] != 2 or d['c'][h][j] < .9 or d['A'][h][j] <= 0: continue
                v = int(d['voice'][h][j]); f = prev.get(v, d['fosc'][h][j]); fd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400))
                n0 = int(hop[h]) - 191
                if n0 - 60 < 0 or n0 + 30 >= len(bh): continue
                nlo = int(np.clip(np.ceil(3000.0 / f), 30, 320))
                Af = a_fast(det, n0, f, fd, nlo); Ab = a_fast(bh, n0, f, fd, nlo); A = d['A'][h][j]
                r_det.append(20 * np.log10(max(Af, 1e-12) / A)); r_bh.append(20 * np.log10(max(Ab, 1e-12) / A)); exc.append(max(0.0, Af - A) / A)
        prev = cur
    r_det, r_bh, exc = map(np.array, (r_det, r_bh, exc))
    if len(r_det) == 0:
        print(f'{label}: no ON voice hops'); return
    print(f'{label:34s} n={len(r_det):6d}: A_fast(det,N_lo)/A_trace dB median {np.median(r_det):+5.2f} p10 {np.percentile(r_det,10):+5.1f} p90 {np.percentile(r_det,90):+5.1f} '
          f'| same on bh {np.median(r_bh):+5.2f} p90 {np.percentile(r_bh,90):+5.1f} | frac A_fast > 1.5 A: {100*np.mean(r_det>3.5):4.1f} %, > 2 A: {100*np.mean(r_det>6):4.1f} % | mean excess max(0,Af-A)/A {np.mean(exc):.2f}')


def triggers():
    tot_t = 0.0; ev = []; rel = []
    cov_all = []
    for name in C.TRACKS:
        rf = C.ref(name)
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); st = d['state']; H = len(tc)
        dur = tc[-1] - 0.5; tot_t += dur
        drums = rf['drum_on']; kicks = rf['kick_on']
        since = lambda t: (t - drums[drums <= t].max()) if np.any(drums <= t) else 1e9
        ks = lambda t: (t - kicks[kicks <= t].max()) if np.any(kicks <= t) else 1e9
        # share of time within 120 ms after a drum / kick
        tt = np.arange(0.5, tc[-1], 0.01)
        cov_all.append((np.mean([since(t) <= .12 for t in tt]), np.mean([ks(t) <= .12 for t in tt]), dur))
        prev = {}
        for h in range(1, H):
            for j in range(8):
                if st[h][j] != 2: continue
                v = int(d['voice'][h][j])
                p = {int(d['voice'][h - 1][q]): int(st[h - 1][q]) for q in range(8) if st[h - 1][q] > 0}
                if tc[h] > 0.5 and p.get(v, 0) in (1, 3):
                    (ev if p[v] == 1 else rel).append((name, tc[h], since(tc[h]), ks(tc[h])))
    cov = np.array(cov_all)
    cd = np.average(cov[:, 0], weights=cov[:, 2]); ck = np.average(cov[:, 1], weights=cov[:, 2])
    print(f'\ntriggers on {tot_t:.0f} s of real music (10 Slakh train tracks, v1.5): CAND->ON {len(ev)} ({len(ev)/tot_t:.2f}/s), REL->ON {len(rel)} ({len(rel)/tot_t:.2f}/s)')
    for nm, L in (('CAND->ON', ev), ('REL->ON', rel)):
        a = np.array([[e[2], e[3]] for e in L])
        print(f'  {nm}: within 120 ms after a drum onset {100*np.mean(a[:,0]<=.12):.0f} % (time share {100*cd:.0f} %); after a kick {100*np.mean(a[:,1]<=.12):.0f} % (time share {100*ck:.0f} %)')


if __name__ == '__main__':
    steady('bare100', 'bare 100 Hz note (clean)')
    steady('steady8', 'steady tone + pink SNR 8 dB')
    steady('steady6', 'steady tone + pink SNR 6 dB')
    steady('bassp6', 'bass+pink SNR 6 dB')
    steady('bkp_0', 'bass+kick(on onsets)+pink')
    steady('bkp_250', 'bass+kick(+250ms)+pink')
    for t in ('Track00060', 'Track00040', 'Track00001', 'Track00025'):
        steady(t, f'real music {t}')
    steady('LOGOFF', 'LOGOFF 20-50 s')
    triggers()
