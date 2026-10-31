"""Engine streams for offline LS: bh (= bhRing_, stage 'selected_h') and the band/pre-HPSS stream (= detailRing52_, stage 'band_delayed191'),
both indexed by core sample index, plus the voice trace.  Config A.  Cached in cache/s_<key>.npz."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M
from vb_quality.stage_capture import INDEX as SI

_ctx = None


def get(key, x, cfg=None):
    p = C.CACHE / f's_{key}.npz'
    if p.exists():
        z = np.load(p); return dict(trace=z['trace'], bh=z['bh'], det=z['det'])
    global _ctx
    ctx = M.Ctx(X.CAND, 15, dict(cfg or dict(voicing=0, ampSource=0)))
    x = np.asarray(x, np.float32)
    x2 = np.stack([x, x], 1) if x.ndim == 1 else x
    r = ctx.render(key, x2, 0.0, voice=True, stage=True)
    st = r['stage']
    core = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
    bh = np.zeros(core.max() + 1); det = np.zeros_like(bh)
    bh[core] = st[:, SI['selected_h']]; det[core] = st[:, SI['band_delayed191']]
    np.savez_compressed(p, trace=np.asarray(r['voice'], float), bh=bh, det=det)
    return dict(trace=np.asarray(r['voice'], float), bh=bh, det=det)


# ---- LS helpers (single voice and joint), identical window to the core: past Hann (N_p), future Hann (N_f = min(N_p, 24))
def window(Np, Nf=24):
    Nf = min(Np, Nf)
    ms = np.arange(-Np, Nf + 1)
    w = np.where(ms <= 0, 0.5 * (1 + np.cos(np.pi * ms / (Np + 1))), 0.5 * (1 + np.cos(np.pi * ms / (Nf + 1))))
    return ms, w


def ls_multi(x, n0, freqs, chirps, Np, Nf=24, ridge=1e-4):
    """joint LS over len(freqs) voices; returns amplitudes (len(freqs),)"""
    ms, w = window(Np, Nf); t = ms / 3000.0
    cols = []
    for f, fd in zip(freqs, chirps):
        ph = 2 * np.pi * (f * t + .5 * fd * t * t); cols += [np.cos(ph), np.sin(ph)]
    B = np.stack(cols, 1)
    G = (B * w[:, None]).T @ B
    G += ridge * np.trace(G) / G.shape[0] * np.eye(G.shape[0])
    s = np.linalg.solve(G, (B * w[:, None]).T @ x[n0 + ms])
    return np.hypot(s[0::2], s[1::2])


def ls_probe(x, n0, f, fd, Np, probes=(22, 30, 38, 45), Nf=24):
    """single-tone amplitude at f and the median amplitude at f +- probes (same window); batch solve"""
    ms, w = window(Np, Nf); t = ms / 3000.0
    fr = np.array([f] + [f + s * p for p in probes for s in (-1, 1)])
    fr = np.maximum(fr, 3.0)
    chirp = np.zeros(len(fr)); chirp[0] = fd
    ph = 2 * np.pi * (fr[:, None] * t[None] + .5 * chirp[:, None] * t[None] ** 2)
    c, s = np.cos(ph), np.sin(ph)
    xs = x[n0 + ms]
    gcc = (c * c * w).sum(1); gss = (s * s * w).sum(1); gcs = (c * s * w).sum(1)
    rc = (c * xs * w).sum(1); rs = (s * xs * w).sum(1)
    lam = 1e-4 * (gcc + gss) / 2
    a11, a22, a12 = gcc + lam, gss + lam, gcs
    det = a11 * a22 - a12 ** 2
    al = (a22 * rc - a12 * rs) / det; be = (a11 * rs - a12 * rc) / det
    A = np.hypot(al, be)
    return A[0], np.median(A[1:])
