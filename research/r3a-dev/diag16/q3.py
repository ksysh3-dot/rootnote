"""Q3: V7d LOGOFF 4.12 s (excerpt 37-49 s, hit at excerpt time 7.12 s). Core A voices around the hit, tracker a, and an offline plain LS
on the captured bh stream (stage 'selected_h' = bhRing_) with the core's window and a 128 ms Hann; local floor in the same window."""
import json
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
st = r0['stage']; rows = r0['harm']
P(f'stage rows {st.shape}, harmonic rows {rows.shape}')
ci = H.core_indices(rows) if hasattr(H, 'core_indices') else None
d, hop, tc = X.hops_of(r0['voice'])
raw = np.asarray(r0['voice']).reshape(-1, 8, 22)
# stage stream by core sample index
core_st = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
bh = np.zeros(core_st.max() + 1); det = np.zeros_like(bh)
bh[core_st] = st[:, SI['selected_h']]; det[core_st] = st[:, SI['band_delayed191']]
# tracker table per hop
hcore = M.hop_table(rows)[0]
ts = H.tracks(rows)
ident = ts[:, :, 0] + 65536 * ts[:, :, 13]
hop_i = hop.astype(np.int64)
hh_ = np.searchsorted(hcore, hop_i)
ok = (hh_ < len(hcore)) & (hcore[np.minimum(hh_, len(hcore) - 1)] == hop_i)
P(f'voice-trace hops matched to harmonic-trace hops: {ok.mean():.3f}')

sel = np.flatnonzero((tc >= T_HIT - 0.10) & (tc <= T_HIT + 0.10))
# voice ids with substance in the window
cand = {}
for h in sel:
    for j in range(8):
        if d['state'][h][j] > 0 and d['c'][h][j] > .05:
            cand.setdefault(int(d['voice'][h][j]), []).append((h, j))
P(f'voices active (state>0, c>0.05) within +-100 ms of excerpt time {T_HIT}: {sorted(cand)}')


def trk_a(h, j):
    if not ok[h]:
        return np.nan, np.nan
    k = hh_[h]; m = np.flatnonzero(ident[k] == raw[h, j, X.F_TRACK])
    return (ts[k][m[0]][4], ts[k][m[0]][2]) if len(m) else (np.nan, np.nan)


STATE = {0: '-', 1: 'CAND', 2: 'ON', 3: 'REL'}
tab = {}
for v, lst in sorted(cand.items()):
    fm = np.median([d['fosc'][h][j] for h, j in lst])
    P(f'\n== voice {v}: median f_osc {fm:.1f} Hz; per hop (t relative to the hit, ms): state coast f_osc | A(LS) | tr.a (tracker) | A/tr.a dB | SNR dB | N_v | prom | c | sigma | sub')
    rows_v = []
    for h in sel:
        js = np.flatnonzero((d['voice'][h] == v) & (d['state'][h] > 0))
        if not len(js):
            continue
        j = js[0]
        a_tr, f_tr = trk_a(h, j)
        A = d['A'][h][j]
        rows_v.append(dict(h=int(h), t_ms=1000 * (tc[h] - T_HIT), state=STATE[int(d['state'][h][j])], coast=int(d['coast'][h][j]), f=float(d['fosc'][h][j]), A=float(A), tra=float(a_tr),
                           snr=float(d['snr'][h][j]), np=int(raw[h, j, X.F_NP]), prom=int(raw[h, j, X.F_PROM]), c=float(d['c'][h][j]), sig=float(d['sig'][h][j]), sub=int(d['sub'][h][j] > .5)))
    tab[v] = rows_v
    for r in rows_v:
        P(f'  {r["t_ms"]:+7.1f} | {r["state"]:4s} co{r["coast"]:<2d} f{r["f"]:7.2f} | A {r["A"]:.4f} | tr.a {r["tra"]:.4f} | {20*np.log10(max(r["A"],1e-9)/max(r["tra"],1e-9)) if np.isfinite(r["tra"]) else float("nan"):+6.1f} | snr {r["snr"]:5.1f} | N {r["np"]:3d} | prom {r["prom"]} | c {r["c"]:.2f} | sig {r["sig"]:.2f} | sub {r["sub"]}')

# ---------------------------------------------------------------- offline LS
def ls_amp(x, n0, f, dfdt, wts, ms):
    """weighted LS of cos/sin at f (chirp dfdt) on x[n0+ms] with weights wts; returns (amplitude, phase)"""
    t = ms / 3000.0
    phi = 2 * np.pi * (f * t + 0.5 * dfdt * t * t)
    xs = x[n0 + ms]
    Bc, Bs = np.cos(phi), np.sin(phi)
    G = np.array([[np.sum(wts * Bc * Bc), np.sum(wts * Bc * Bs)], [np.sum(wts * Bc * Bs), np.sum(wts * Bs * Bs)]])
    G += 1e-4 * np.trace(G) / 2 * np.eye(2)
    rr = np.array([np.sum(wts * Bc * xs), np.sum(wts * Bs * xs)])
    a_, b_ = np.linalg.solve(G, rr)
    return float(np.hypot(a_, b_))


def core_window(Np, Nf):
    ms = np.arange(-Np, Nf + 1)
    w = np.where(ms <= 0, 0.5 * (1 + np.cos(np.pi * ms / (Np + 1))), 0.5 * (1 + np.cos(np.pi * ms / (Nf + 1))))
    return ms, w


def hann_window(N=384):
    ms = np.arange(-N // 2, N // 2)
    return ms, 0.5 * (1 + np.cos(2 * np.pi * ms / N))


def floor_amp(x, n0, f, dfdt, wts, ms, others):
    """median LS amplitude at test frequencies 22-45 Hz away from f (both sides), excluding +-22 Hz around other voice frequencies"""
    ds = np.r_[np.arange(22, 46, 1.5), -np.arange(22, 46, 1.5)]
    fs_ = [f + q for q in ds if f + q > 5]
    fs_ = [q for q in fs_ if all(abs(q - o) > 22 for o in others)]
    if len(fs_) < 4:
        fs_ = [f + q for q in ds if f + q > 5]
    a = np.array([ls_amp(x, n0, q, 0.0, wts, ms) for q in fs_])
    return float(np.median(a)), float(np.mean(a)), len(fs_)


# pick the voice and hop with the largest A/tr.a excess near the hit
best = None
for v, rows_v in tab.items():
    for r in rows_v:
        if np.isfinite(r['tra']) and abs(r['t_ms']) < 60 and r['c'] > .5:
            ex = r['A'] / max(r['tra'], 1e-9)
            if best is None or r['A'] > best[0]:
                best = (r['A'], v, r)
P(f'\nlargest A within +-60 ms: voice {best[1]} hop {best[2]["h"]} t {best[2]["t_ms"]:+.1f} ms A {best[2]["A"]:.4f} tr.a {best[2]["tra"]:.4f}')
rep = {}
for v in sorted(cand):
    rows_v = tab[v]
    if not rows_v:
        continue
    P(f'\n== offline LS for voice {v} (f_osc as traced; bh = stage selected_h; core window = past Hann N_v / future 24; Hann128 = 384-sample Hann centred on n_h): ' +
      'per hop: t_ms | A_core | A_LS(core window, N_v) | A_LS(Hann128) | floor_med(core win) | floor_med(Hann128) | tone/floor dB (core win) | tone/floor dB (Hann128) | tr.a')
    for r in rows_v:
        h = r['h']; ih = int(hop_i[h]); n0 = ih - 191
        j = np.flatnonzero((d['voice'][h] == v) & (d['state'][h] > 0))[0]
        f = r['f']; dfdt = float(np.clip(raw[h, j, X.F_DFDT], -400, 400))
        others = [d['fosc'][h][q] for q in range(8) if d['state'][h][q] > 0 and d['voice'][h][q] != v and d['c'][h][q] > .05]
        Np = max(r['np'], 30)
        ms1, w1 = core_window(Np, min(Np, 24))
        ms2, w2 = hann_window(384)
        a1 = ls_amp(bh, n0, f, dfdt, w1, ms1); a2 = ls_amp(bh, n0, f, dfdt, w2, ms2)
        f1 = floor_amp(bh, n0, f, dfdt, w1, ms1, others); f2 = floor_amp(bh, n0, f, dfdt, w2, ms2, others)
        r.update(A_ls_core=a1, A_ls_hann=a2, floor_core=f1[0], floor_hann=f2[0], ratio_core_db=20 * np.log10(a1 / max(f1[0], 1e-12)), ratio_hann_db=20 * np.log10(a2 / max(f2[0], 1e-12)))
        P(f'  {r["t_ms"]:+7.1f} | {r["A"]:.4f} | {a1:.4f} | {a2:.4f} | {f1[0]:.4f} | {f2[0]:.4f} | {r["ratio_core_db"]:+5.1f} | {r["ratio_hann_db"]:+5.1f} | {r["tra"]:.4f}   (N_v {Np}, f {f:.1f})')
    rep[v] = rows_v

# ---------------------------------------------------------------- spectrum of bh: before / at / after the hit (tone vs broadband)
def hann_spec(x, c_slot, N, f_lo=60, f_hi=260):
    ms = np.arange(-N // 2, N // 2); w = 0.5 * (1 + np.cos(2 * np.pi * ms / N))
    seg = x[c_slot + ms] * w
    nfft = 8192
    S = np.abs(np.fft.rfft(seg, nfft)) * 2 / w.sum()
    f = np.fft.rfftfreq(nfft, 1 / 3000)
    m = (f >= f_lo) & (f <= f_hi)
    return f[m], S[m]


h_hit = int(np.argmin(np.abs(tc - T_HIT)))
n_hit = int(hop_i[h_hit]) - 191
P('\n== spectrum of the bh stream (3 kHz harmonic band): 128 ms Hann (384) vs 16 ms Hann (48) vs 30-sample window, centred on the hit. Peak amplitude (sine units) near 131 Hz, and median level 160-260 Hz')
for lab, off in (('-100 ms', -300), ('-50 ms', -150), ('hit', 0), ('+30 ms', 90), ('+60 ms', 180), ('+100 ms', 300)):
    for N in (384, 96, 48):
        f, S = hann_spec(bh, n_hit + off, N)
        m = (f >= 120) & (f <= 145); k = np.argmax(S[m])
        P(f'  {lab:8s} N={N:3d}: peak in 120-145 Hz: {S[m][k]:.4f} at {f[m][k]:.1f} Hz; median 60-260 Hz {np.median(S):.4f}; max 60-260 {S.max():.4f} at {f[np.argmax(S)]:.1f} Hz')
# HPSS-raw 'detail' stream the same
P('  (detail stream, ampSource 1 input) :')
for lab, off in (('hit', 0), ('+30 ms', 90)):
    for N in (384, 96):
        f, S = hann_spec(det, n_hit + off, N)
        m = (f >= 120) & (f <= 145); k = np.argmax(S[m])
        P(f'  {lab:8s} N={N:3d}: peak in 120-145 Hz: {S[m][k]:.4f} at {f[m][k]:.1f} Hz; median 60-260 {np.median(S):.4f}')
json.dump(rep, open(C.D16 / 'q3.json', 'w'), indent=1, default=float)
open(C.D16 / 'q3_report.txt', 'w').write('\n'.join(out))
