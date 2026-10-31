"""Diagnostic: why does the suite's V4c (bass+kick+pink, config A) give 1.24 dB while an independent recomputation gives 0.82 dB?
Uses the suite's own helpers only to extract what it uses (read-only)."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_metrics as M, research_core_signals as S
import research_core_xcheck as X

sig = S.flicker_signals(8.0)
ctx = M.Ctx('build_core/libpvbcapi.so', 15, dict(voicing=0, ampSource=0))
x = S.stereo(sig['bass+kick+pink'])
r0 = ctx.render('bkp', x, 0.0, harmonic=True, voice=True)
vs = M.voices(ctx, r0)
print('suite hop_offset', vs.hop_offset, 'n hops', len(vs.tc))
A = M.series_near(vs, 100.0, on=True)
print('suite A finite', np.isfinite(A).sum(), 'of', len(A))
# mine from the same trace rows (r0['voice'] is the raw 22-field trace)
tr = np.asarray(r0['voice'])
hop = tr[:, 0]
sel = (tr[:, 3] == 2) & (np.abs(tr[:, 5] - 100.0) < 5.0) & (tr[:, 8] > 0)
hh = {}
for h, a in zip(hop[sel], tr[sel, 8]):
    hh[h] = max(hh.get(h, 0.0), a)
print('mine hops with ON near 100:', len(hh))
# compare tc
core = M.hop_table(r0['harm'])[0]; tc_h = M.hop_table(r0['harm'])[1]
print('first 5 harmonic-row core idx', core[:5], 'tc', tc_h[:5], ' | first voice hops', np.unique(hop)[:5], ' (hop-382)/3000', (np.unique(hop)[:5] - 382) / 3000)
# map: for each harmonic row index i: tc_h[i] vs (core[i]-382)/3000
d = tc_h - (core - 382) / 3000.0
print('tc_harm - (core-382)/3000: min/max (s)', d.min(), d.max())
# per-hop comparison of suite A and mine
mine = np.full(len(core), np.nan)
idx = {int(c): i for i, c in enumerate(core)}
for h, a in hh.items():
    i = idx.get(int(h) - vs.hop_offset)
    if i is not None:
        mine[i] = a
both = np.isfinite(A) & np.isfinite(mine)
print('both finite', both.sum(), 'only suite', (np.isfinite(A) & ~np.isfinite(mine)).sum(), 'only mine', (~np.isfinite(A) & np.isfinite(mine)).sum())
print('max |A_suite - A_mine| on common', np.max(np.abs(A[both] - mine[both])))
# now the V4c statistic by both selections using suite tc
for nm, series, tcv in (('suite A, suite tc', A, vs.tc), ('mine A, harmonic tc', mine, tc_h)):
    res_all = []; per = []
    for c in range(2, 16):
        t0 = .5 * c
        s = np.flatnonzero((tcv >= t0 + .040) & (tcv < t0 + .450) & np.isfinite(series) & (series > 0))
        if len(s) < 5:
            continue
        u = tcv[s] - t0; rr = 20 * np.log10(series[s]) + 20 * np.log10(np.e) * u / .35
        res_all.append(rr - rr.mean()); per.append(rr.std())
    print(nm, 'std pooled per-note-mean-removed', np.std(np.concatenate(res_all)), 'n', sum(len(q) for q in res_all))
# the notes with the largest residual std
tcv = vs.tc
for c in range(2, 16):
    t0 = .5 * c
    s = np.flatnonzero((tcv >= t0 + .040) & (tcv < t0 + .450) & np.isfinite(A) & (A > 0))
    u = tcv[s] - t0; rr = 20 * np.log10(A[s]) + 20 * np.log10(np.e) * u / .35
    print(f'note {c:2d}: n {len(s):3d} std {rr.std():.3f} range {rr.min():.2f}..{rr.max():.2f}')
