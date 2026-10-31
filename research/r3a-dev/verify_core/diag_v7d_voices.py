"""V7d: what is the core layer (config A) doing at the LOGOFF hits (input time 7.12 s / 7.73 s of the 37-49 s excerpt)? Which voices, frequencies,
harmonics; what does P1 do there (tracks, fade)."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
import research_core_metrics as M          # only for the P1 harmonic-trace parse (diagnostic, not a metric)
FS = X.FS
cand = X.open_lib(X.CAND)
lg = X.read_excerpt(X.LOGOFF, 37.0, 12.0)
r = X.render(cand, lg, 15, 0.0, out_db=-5.0, cfg=X.CFG['A'], trace=True)
rd = X.render(cand, lg, 15, -120.0, out_db=-5.0, cfg=X.CFG['A'])
lay = X.band_fft(X.layer(r, rd), 150, 600)
d, hop, tc = X.hops_of(r['trace'])

# P1 side (harmonic trace via the suite's parser)
ctx = M.Ctx(X.REF, 6, None)
r1 = ctx.render('lg', lg, 0.0, harmonic=True)
vs1 = M.vs_from_harm(r1['harm'])
rd1 = ctx.render('lg', lg, -120.0)
lay1 = X.band_fft(M.layer_of(r1, rd1), 150, 600)


def peaks(sig, c, half=0.05, nlist=4):
    a, b = int((c - half) * FS), int((c + half) * FS)
    seg = sig[a:b] * np.hanning(b - a)
    P = np.abs(np.fft.rfft(seg, 1 << 16)) ** 2; f = np.fft.rfftfreq(1 << 16, 1 / FS)
    m = (f >= 150) & (f <= 600)
    idx = np.flatnonzero(m & (P >= np.roll(P, 1)) & (P >= np.roll(P, -1)))
    idx = idx[np.argsort(P[idx])[::-1][:nlist]]
    tot = 10 * np.log10(np.sum(seg ** 2) + 1e-30)
    return tot, [(round(float(f[i]), 1), round(float(10 * np.log10(P[i] / P[idx[0]] + 1e-30)), 1)) for i in sorted(idx, key=lambda q: f[q])]


for hit, c0 in ((4.12, 7.12), (4.73, 7.73)):
    print(f'================ hit {hit} s  (excerpt time {c0} s)')
    for t_lo, t_hi in ((c0 - 0.25, c0 + 0.20),):
        print(' core voices per hop (ON/REL/CAND, f_osc, A, c, sigma, a2, a3, subordinate), every 2nd hop:')
        for h in range(len(tc)):
            if not (t_lo <= tc[h] <= t_hi) or h % 4:
                continue
            row = []
            for s in range(8):
                if d['state'][h][s] == 0 or d['c'][h][s] < 0.05:
                    continue
                row.append(f's{int(d["state"][h][s])} f{d["fosc"][h][s]:6.1f} A{d["A"][h][s]:.4f} c{d["c"][h][s]:.2f} g{d["sig"][h][s]:.2f} a2 {d["a2"][h][s]:.4f} a3 {d["a3"][h][s]:.4f}{" SUB" if d["sub"][h][s] > .5 else ""}')
            print(f'  tc {tc[h]-c0:+.3f} | ' + ' || '.join(row))
        print(' P1 tracks per hop (f, a, fade), every 4th hop:')
        for h in range(len(vs1.tc)):
            if not (t_lo <= vs1.tc[h] <= t_hi) or h % 4:
                continue
            row = [f'f{vs1.f[h][j]:6.1f} a{vs1.A[h][j]:.4f} fade{vs1.c[h][j]:.2f}' for j in range(vs1.f.shape[1]) if vs1.valid[h][j] and 20 <= vs1.f[h][j] <= 700 and vs1.c[h][j] >= 0.05]
            print(f'  tc {vs1.tc[h]-c0:+.3f} | ' + ' || '.join(row))
    for nm, sig in (('core A layer', lay), ('P1 layer', lay1)):
        for lab, c in (('before hit (-150 ms)', c0 - 0.15), ('at hit', c0), ('after hit (+150 ms)', c0 + 0.15)):
            tot, pk = peaks(sig, c)
            print(f'  {nm:13s} {lab:22s} 150-600 Hz energy {tot:7.1f} dB; spectral peaks (Hz, dB re strongest): {pk}')
