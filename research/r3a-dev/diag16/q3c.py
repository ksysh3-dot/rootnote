"""Q3c: where does the +13.6 dB core-vs-P1 layer energy at the LOGOFF 4.12 s hit come from? voice-weight budget, core vs P1, and the layer energies."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M

FS = X.FS
T_HIT = 7.12
lg = X.read_excerpt(X.LOGOFF, 37.0, 12.0)
ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0)); ctx1 = M.Ctx(X.REF, 6, None)
r0 = ctx.render('lg', lg, 0.0, harmonic=True, voice=True); rd = ctx.render('lg', lg, -120.0)
p0 = ctx1.render('lg', lg, 0.0, harmonic=True); pd = ctx1.render('lg', lg, -120.0)
lay = X.band_fft(M.layer_of(r0, rd), 150, 600); lay1 = X.band_fft(M.layer_of(p0, pd), 150, 600)
d, hop, tc = X.hops_of(r0['voice'])
vs1 = M.vs_from_harm(p0['harm'])
for half in (0.03, 0.05, 0.10):
    a, b = int((T_HIT - half) * FS), int((T_HIT + half) * FS)
    ec = np.sum(lay[a:b] ** 2); e1 = np.sum(lay1[a:b] ** 2)
    win = (tc >= T_HIT - half) & (tc <= T_HIT + half); win1 = (vs1.tc >= T_HIT - half) & (vs1.tc <= T_HIT + half)
    wc = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)[win].sum(); w1 = vs1.w[win1].sum()
    print(f'+-{half*1000:.0f} ms: layer energy core {10*np.log10(ec):.1f} dB, P1 {10*np.log10(e1):.1f} dB, diff {10*np.log10(ec/e1):+.1f} dB;  voice-weight sum core {wc:.4g}, P1 {w1:.4g}, diff {10*np.log10(wc/max(w1,1e-30)):+.1f} dB')
print('\n10 ms boxes around the hit (ms relative): core layer dB | P1 layer dB | diff | core weight sum | P1 weight sum | P1 gain (header 17, mean) | core sum a2^2+a3^2')
rows1 = p0['harm']; tc1 = vs1.tc
for k in range(-12, 13):
    a_ = T_HIT + 0.010 * k; b_ = a_ + 0.010
    ia, ib = int(a_ * FS), int(b_ * FS)
    ec = 10 * np.log10(np.sum(lay[ia:ib] ** 2) + 1e-30); e1 = 10 * np.log10(np.sum(lay1[ia:ib] ** 2) + 1e-30)
    m = (tc >= a_) & (tc < b_); m1 = (tc1 >= a_) & (tc1 < b_)
    wcs = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)[m].sum(); w1s = vs1.w[m1].sum()
    g = rows1[m1, 17].mean() if m1.any() else np.nan
    a23 = np.nansum(np.where(d['state'][m] > 0, d['a2'][m] ** 2 + d['a3'][m] ** 2, 0.0))
    print(f'  {10*k:+4d}: {ec:7.1f} | {e1:7.1f} | {ec-e1:+6.1f} | {wcs:.4f} | {w1s:.4f} | {g:.3f} | {a23:.4f}')
print('\nper-voice weight share within +-50 ms (core):')
win = (tc >= T_HIT - 0.05) & (tc <= T_HIT + 0.05)
wc = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
acc = {}
for h in np.flatnonzero(win):
    for j in range(8):
        if wc[h][j] > 0:
            acc.setdefault(int(d['voice'][h][j]), [0.0, []])
            acc[int(d['voice'][h][j])][0] += wc[h][j]; acc[int(d['voice'][h][j])][1].append(d['fosc'][h][j])
for v, (s, fl) in sorted(acc.items(), key=lambda kv: -kv[1][0]):
    print(f'  voice {v}: weight {s:.4g} ({100*s/wc[win].sum():.1f} %), median f_osc {np.median(fl):.1f} Hz')
print('\nP1 tracks within +-50 ms: per track weight (a*fade)^2')
win1 = (vs1.tc >= T_HIT - 0.05) & (vs1.tc <= T_HIT + 0.05)
acc1 = {}
for h in np.flatnonzero(win1):
    for j in range(vs1.f.shape[1]):
        if vs1.valid[h][j] and vs1.w[h][j] > 0:
            acc1.setdefault(int(vs1.vid[h][j]), [0.0, [], []])
            acc1[int(vs1.vid[h][j])][0] += vs1.w[h][j]; acc1[int(vs1.vid[h][j])][1].append(vs1.f[h][j]); acc1[int(vs1.vid[h][j])][2].append(vs1.c[h][j])
for v, (s, fl, fd) in sorted(acc1.items(), key=lambda kv: -kv[1][0])[:8]:
    print(f'  P1 track {v}: weight {s:.4g} ({100*s/vs1.w[win1].sum():.1f} %), median f {np.median(fl):.1f} Hz, fade median {np.median(fd):.2f}')
