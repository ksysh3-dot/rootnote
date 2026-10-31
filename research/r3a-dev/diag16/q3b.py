"""Q3b: emulate the core's stage-1 joint LS offline at the LOGOFF hit hops (bh stream captured from the engine) and test the two-close-voice hypothesis
(voice 488 at 131.8 Hz and the coasting voice 492 at 137.0 Hz, 5.2 Hz apart)."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M
import test_harmonic_continuity as H
from vb_quality.stage_capture import INDEX as SI

FS = X.FS
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


T_HIT = 7.12
lg = X.read_excerpt(X.LOGOFF, 37.0, 12.0)
ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
r0 = ctx.render('lg', lg, 0.0, harmonic=True, voice=True, stage=True)
st = r0['stage']
core_st = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
bh = np.zeros(core_st.max() + 1); bh[core_st] = st[:, SI['selected_h']]
d, hop, tc = X.hops_of(r0['voice'])
raw = np.asarray(r0['voice']).reshape(-1, 8, 22)
hop_i = hop.astype(np.int64)


def window(Np, Nf):
    ms = np.arange(-Np, Nf + 1)
    return ms, np.where(ms <= 0, 0.5 * (1 + np.cos(np.pi * ms / (Np + 1))), 0.5 * (1 + np.cos(np.pi * ms / (Nf + 1))))


def joint(h, vids, NJ, Nf=24, fb=None, chirp=True):
    ih = int(hop_i[h]); n0 = ih - 191
    ms, w = window(NJ, min(NJ, Nf))
    t = ms / 3000.0
    cols = []
    for v in vids:
        j = np.flatnonzero(d['voice'][h] == v)[0]
        f = fb[v] if fb and v in fb else d['fosc'][h][j]
        dfd = float(np.clip(raw[h, j, X.F_DFDT], -400, 400)) if chirp else 0.0
        phi = 2 * np.pi * (f * t + .5 * dfd * t * t)
        cols += [np.cos(phi), np.sin(phi)]
    Bm = np.stack(cols, 1)
    G = (Bm * w[:, None]).T @ Bm
    lam = 1e-4 * np.trace(G) / (2 * len(vids))
    Gl = G + lam * np.eye(len(G))
    x = bh[n0 + ms]
    sol = np.linalg.solve(Gl, (Bm * w[:, None]).T @ x)
    A = np.hypot(sol[0::2], sol[1::2])
    dg = np.sqrt(np.diag(G)); Gn = G / np.outer(dg, dg)
    return A, np.linalg.cond(Gn), np.linalg.cond(Gl / np.outer(dg, dg))


sel = np.flatnonzero((tc >= T_HIT - 0.02) & (tc <= T_HIT + 0.10))
P('Joint stage-1 LS emulation: set = voices ON/CAND or REL with c>0.1 at hop h; basis frequency = f_osc of the previous hop (the f the LS used); window past N_J (taken from the np field of a low-SNR voice) / future 24.')
P('| t ms | N_J | set (id:f_osc) | trace A | emulated A (joint) | emulated A (voice 492 removed) | emulated A (single 488) | cond(G normalised) |')
P('|---|---|---|---|---|---|---|---|')
for h in sel:
    vs = [int(d['voice'][h][j]) for j in range(8) if d['state'][h][j] in (1, 2) or (d['state'][h][j] == 3 and d['c'][h][j] > .1)]
    if 488 not in vs:
        continue
    # N_J: np of the lowest-SNR ON voice with np>0 if SNR<18 else take np of voice 488
    j488 = np.flatnonzero(d['voice'][h] == 488)[0]
    if d['snr'][h][j488] >= 18:      # voices with SNR >= 18 dB get the stage-2 window N_v in the np field, not N_J: skip these hops
        continue
    NJ = int(raw[h, j488, X.F_NP]) if raw[h, j488, X.F_NP] > 0 else 320
    fb = {}
    for v in vs:
        jp = np.flatnonzero(d['voice'][h - 1] == v)
        if len(jp):
            fb[v] = d['fosc'][h - 1][jp[0]]
    A, cn, cl = joint(h, vs, NJ, fb=fb)
    vs2 = [v for v in vs if v != 492]
    A2, _, _ = joint(h, vs2, NJ, fb=fb) if 492 in vs else (A, 0, 0)
    A1, _, _ = joint(h, [488], NJ, fb=fb)
    tr = {int(d['voice'][h][j]): d['A'][h][j] for j in range(8) if d['voice'][h][j] in vs}
    P(f'| {1000*(tc[h]-T_HIT):+.1f} | {NJ} | ' + ' '.join(f'{v}:{d["fosc"][h][np.flatnonzero(d["voice"][h]==v)[0]]:.1f}' for v in vs) + ' | ' +
      ' '.join(f'{v}:{tr[v]:.4f}' for v in vs) + ' | ' + ' '.join(f'{v}:{a:.4f}' for v, a in zip(vs, A)) + ' | ' + (' '.join(f'{v}:{a:.4f}' for v, a in zip(vs2, A2)) if 492 in vs else '-') +
      f' | {A1[0]:.4f} | {cn:.1f} |')

# contribution of the spike hop(s) to the +-50 ms weight sum (proxy for the layer energy; weight (A c sigma)^2 summed over voices and hops)
wm = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)
win = (tc >= T_HIT - 0.05) & (tc <= T_HIT + 0.05)
tot = wm[win].sum()
h34 = int(np.argmin(np.abs(tc - (T_HIT + 0.034))))
P(f'\nsum of (A c sigma)^2 over all voices and hops within +-50 ms of {T_HIT}: {tot:.4g}; hop at +34 ms contributes {wm[h34].sum():.4g} ({100*wm[h34].sum()/tot:.1f} % of the window sum; voices 488+492 {100*sum(wm[h34][np.flatnonzero(d["voice"][h34]==v)[0]] for v in (488,492))/tot:.1f} %)')
# if voices 488 and 492 at +/-1 hop of +34 ms were limited to the tracker-level amplitude 0.026 (488) / 0.026 (492)
wm2 = wm.copy()
for hh in (h34 - 1, h34, h34 + 1):
    for v in (488, 492):
        j = np.flatnonzero(d['voice'][hh] == v)[0]
        wm2[hh, j] = min(wm2[hh, j], (0.026 * d['c'][hh][j] * d['sig'][hh][j]) ** 2)
P(f'if A of voices 488 and 492 at the three hops +29..+39 ms were capped at 0.026: window weight sum {10*np.log10(wm2[win].sum()/tot):+.2f} dB')
# the harmonic amplitude a_2 / a_3 of the same voices (what is actually synthesised)
j488 = np.flatnonzero(d['voice'][h34] == 488)[0]; j492 = np.flatnonzero(d['voice'][h34] == 492)[0]
P(f'a_2/a_3 at +34 ms: voice 488 {d["a2"][h34][j488]:.4f}/{d["a3"][h34][j488]:.4f}, voice 492 {d["a2"][h34][j492]:.4f}/{d["a3"][h34][j492]:.4f}')
open(C.D16 / 'q3b_report.txt', 'w').write('\n'.join(out))
