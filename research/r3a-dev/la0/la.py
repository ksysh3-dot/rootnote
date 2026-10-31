"""Section-14 lookahead prototype LA (offline, Python).  See CHOICES.md for every reading of the pre-registration that is not literal.
All positions inside this module are STREAM sample indices (3 kHz); stream_time()/stream_index() convert to input seconds.
L_samp = round(3 L_ms); a track hop (frame centre c) is usable at output position t iff c + 191 <= t + L_samp   (TRK_LAG = 191 samples =
the half tracker frame; with trk_lag = 0 the 'hop-centre' sensitivity reading c <= t + L is obtained)."""
import bisect
import numpy as np
from data import stream_time, stream_index, HOP, HOP_S, FSC

NP_MAX, NF_MAX = 320, 650
E_WIN = 30                    # 10 ms short envelope window
GRID_E, GRID_A = 4, 8         # evaluation grids (stream samples): e(t) 1.33 ms, A(t) 2.67 ms
RIDGE = 1e-4
SMOOTH = 30                   # 10 ms zero-phase smoothing of A
FADE_S = 15                   # 5 ms gate fade
TRK_LAG = 191


def _phase(PH, ja, J, jav, fav):
    """phase of stream samples J (any int array) for a chunk with dense phase PH starting at index ja; samples beyond jav (the newest usable
    hop) continue at the frequency fav.  jav broadcastable against J."""
    Jc = np.minimum(J, jav)
    idx = np.clip(Jc - ja, 0, len(PH) - 1)
    return PH[idx] + 2 * np.pi * fav * np.maximum(J - jav, 0) / FSC


class Chunk:
    pass


def build_chunks(sig, L_ms, trk_lag=TRK_LAG):
    """Chunks = runs of one tracker id (all tracks with state>0 of the P1 reference trace); consecutive runs of (nearly) equal frequency are joined
    when the gap <= 50 ms and the join is knowable inside the lookahead: gap_time <= (L_samp - trk_lag)/3000 (so none at L = 0)."""
    ts, tc, H = sig.ts, sig.tc1, sig.nhop
    valid = ts[:H, :, 1] > 0
    ident = (ts[:H, :, 0] + 65536 * ts[:H, :, 13]).astype(np.int64)
    Ls = int(round(3 * L_ms))
    runs = []
    for tid in np.unique(ident[valid]):
        hs, js = np.nonzero(valid & (ident == tid))
        cut = np.flatnonzero(np.diff(hs) != 1) + 1
        for a, b in zip(np.r_[0, cut], np.r_[cut, len(hs)]):
            runs.append(dict(id=int(tid), hs=hs[a:b], js=js[a:b]))
    runs.sort(key=lambda r: r['hs'][0])
    nxt = [-1] * len(runs); prv = [-1] * len(runs)
    maxgap = min(0.050, (Ls - trk_lag) / FSC)
    if maxgap >= 0:
        cand = []
        starts = np.array([r['hs'][0] for r in runs])
        for ia, A in enumerate(runs):
            hA = A['hs'][-1]; fA = ts[hA, A['js'][-1], 2]
            lo = np.searchsorted(starts, hA + 1)               # B must start after A ends
            for ib in range(lo, len(runs)):
                B = runs[ib]
                gap = (B['hs'][0] - hA - 1) * HOP_S
                if gap > maxgap + 1e-9:
                    break
                fB = ts[B['hs'][0], B['js'][0], 2]
                if abs(fB - fA) <= 0.03 * fA:
                    cand.append((gap, abs(fB - fA) / fA, ia, ib))
        cand.sort()
        for gap, df, ia, ib in cand:
            if nxt[ia] < 0 and prv[ib] < 0:
                nxt[ia] = ib; prv[ib] = ia
    chunks = []
    for i0, r in enumerate(runs):
        if prv[i0] >= 0:
            continue
        seq = [i0]
        while nxt[seq[-1]] >= 0:
            seq.append(nxt[seq[-1]])
        hs = np.concatenate([runs[i]['hs'] for i in seq]); js = np.concatenate([runs[i]['js'] for i in seq])
        h0, h1 = hs[0], hs[-1]
        hr = np.arange(h0, h1 + 1)
        ch = Chunk()
        ch.cid = len(chunks); ch.id = runs[i0]['id']; ch.h0, ch.h1 = int(h0), int(h1)
        ch.hs, ch.js = hs, js                                   # real hops
        ch.tc = tc[hr]                                          # hop centres of the whole range (gap hops included)
        freal = ts[hs, js, 2]
        ch.f = np.interp(tc[hr], tc[hs], freal)
        ch.a_real = ts[hs, js, 4]; ch.raw_real = ts[hs, js, 12]; ch.res_real = ts[hs, js, 6]; ch.dfdt_real = ts[hs, js, 3]
        ch.t_real = tc[hs]
        chunks.append(ch)
    return chunks


def prepare_chunk(ch, nstream, L_ms, trk_lag=TRK_LAG):
    """presence in stream samples, dense phase"""
    Ls = int(round(3 * L_ms)); D = trk_lag - Ls; ch.D = D; sh = max(D, 0)
    jf = stream_index(ch.tc[0]); jl = stream_index(ch.tc[-1] + HOP_S)
    ch.ja_p = int(round(jf)) + sh                                # presence start / end (stream samples)
    ch.jb_p = int(round(jl)) + sh
    ja = ch.ja_p - NP_MAX - 40; jb = ch.jb_p + NF_MAX + 80
    jr = np.arange(ja, jb + 1)
    fj = np.interp(stream_time(jr), ch.tc, ch.f)                 # hold outside the hop range
    ch.PH = np.cumsum(2 * np.pi * fj / FSC); ch.jd = ja
    ch.fj = fj
    return ch


def f_at_j(ch, j):
    return np.interp(stream_time(np.asarray(j, float)), ch.tc, ch.f)


def short_env(ch, x, L_ms, trk_lag=TRK_LAG):
    """e(t): 10 ms Hann LS amplitude at the chunk frequency, window [t-(10-fut), t+fut], fut = min(5 ms, L); on the GRID_E grid of the presence"""
    Ls = int(round(3 * L_ms)); fN = min(15, Ls); pN = E_WIN - fN
    off = np.arange(-pN, fN + 1)
    w = np.where(off <= 0, 0.5 * (1 + np.cos(np.pi * off / (pN + 1))), 0.5 * (1 + np.cos(np.pi * off / (fN + 1))))
    jk = np.arange(ch.ja_p, ch.jb_p + 1, GRID_E)
    if len(jk) == 0:
        return jk, np.zeros(0)
    J = jk[:, None] + off[None, :]
    jav = (jk - ch.D)[:, None]
    fav = np.interp(stream_time(jav[:, 0].astype(float)), ch.tc, ch.f)[:, None]
    ph = _phase(ch.PH, ch.jd, J, jav, fav)
    ok = (J >= 0) & (J < len(x))
    xs = np.where(ok, x[np.clip(J, 0, len(x) - 1)], 0.0); wm = w[None, :] * ok
    c, s = np.cos(ph), np.sin(ph)
    gcc = (wm * c * c).sum(1); gss = (wm * s * s).sum(1); gcs = (wm * c * s).sum(1)
    rc = (wm * c * xs).sum(1); rs = (wm * s * xs).sum(1)
    lam = RIDGE * (gcc + gss) / 2
    a11, a22 = gcc + lam, gss + lam
    det = a11 * a22 - gcs ** 2
    det = np.where(det > 1e-30, det, 1e-30)
    al = (a22 * rc - gcs * rs) / det; be = (a11 * rs - gcs * rc) / det
    return jk, np.hypot(al, be)


def find_intervals(jk, e, L_ms):
    """boundaries on the GRID_E grid.  returns list of (k_on, k_off) with k_off exclusive (index into jk)"""
    n = len(e)
    Lg = int(round(3 * L_ms / GRID_E))
    pers = int(round(3 * min(L_ms, 50.0) / GRID_E))
    out = []
    i = 0
    thr_db = 10 ** (-12 / 20)
    while i < n:
        we = min(n - 1, i + Lg)
        M = e[i:we + 1].max()
        if not M > 1e-12:
            i += 1; continue
        k_on = i + int(np.argmax(e[i:we + 1] > 0.5 * M))
        srt = []; k_off = n
        for k in range(k_on, n):
            bisect.insort(srt, e[k])
            if k == k_on:
                continue
            m = len(srt); med = srt[m // 2] if m % 2 else 0.5 * (srt[m // 2 - 1] + srt[m // 2])
            thr = med * thr_db
            if e[k] < thr and np.all(e[k:min(n, k + pers + 1)] < thr):
                k_off = k; break
        out.append((k_on, k_off))
        i = k_off if k_off > k_on else k_on + 1
    return out


def solve_amplitudes(sig, x, chunks, ivs, L_ms, trk_lag=TRK_LAG, want_ratio=True):
    """A(t) on the GRID_A grid for every interval, joint over all intervals active at that grid time, capped at 2 x single.
    ivs: list of dicts with keys ch (Chunk), j_on, j_off (stream samples, off exclusive).  Fills iv['m0'], iv['Aj'], iv['As'], iv['nact'].  Returns ratio array."""
    Ls = int(round(3 * L_ms)); Nf = min(NF_MAX, Ls)
    for iv in ivs:
        iv['m0'] = int(np.ceil(iv['j_on'] / GRID_A)); iv['m1'] = int(np.ceil(iv['j_off'] / GRID_A))      # grid points m0..m1-1
        n = max(iv['m1'] - iv['m0'], 0)
        iv['Aj'] = np.zeros(n); iv['As'] = np.zeros(n); iv['nact'] = np.zeros(n, int)
    active = {}
    for ii, iv in enumerate(ivs):
        for m in range(iv['m0'], iv['m1']):
            active.setdefault(m, []).append(ii)
    ratios = []; nx = len(x)
    for m in sorted(active):
        lst = active[m]
        jc = m * GRID_A
        J = np.arange(jc - NP_MAX, jc + Nf + 1)
        w = np.where(J <= jc, 0.5 * (1 + np.cos(np.pi * (J - jc) / (NP_MAX + 1))), 0.5 * (1 + np.cos(np.pi * (J - jc) / (Nf + 1))))
        okx = (J >= 0) & (J < nx)
        xs = np.where(okx, x[np.clip(J, 0, nx - 1)], 0.0); wv = w * okx
        V = len(lst); cols = np.zeros((2 * V, len(J)))
        jav = jc - ivs[lst[0]]['ch'].D
        for q, ii in enumerate(lst):
            iv = ivs[ii]; ch = iv['ch']
            mask = (J >= iv['j_on']) & (J < iv['j_off'])
            fav = float(np.interp(stream_time(float(jav)), ch.tc, ch.f))
            ph = _phase(ch.PH, ch.jd, J, jav, fav)
            cols[2 * q] = np.cos(ph) * mask; cols[2 * q + 1] = np.sin(ph) * mask
        Bw = cols * wv[None, :]
        G = Bw @ cols.T; r = Bw @ xs
        lam = RIDGE * np.trace(G) / (2 * V)
        sol = np.linalg.solve(G + lam * np.eye(2 * V), r)
        Aj = np.hypot(sol[0::2], sol[1::2])
        for q, ii in enumerate(lst):
            Gq = G[2 * q:2 * q + 2, 2 * q:2 * q + 2]; rq = r[2 * q:2 * q + 2]
            lq = RIDGE * np.trace(Gq) / 2
            sq = np.linalg.solve(Gq + lq * np.eye(2), rq)
            As = float(np.hypot(sq[0], sq[1]))
            iv = ivs[ii]; k = m - iv['m0']
            iv['Aj'][k] = Aj[q]; iv['As'][k] = As; iv['nact'][k] = V
            if V >= 2 and As > 1e-9:
                ratios.append((Aj[q] / As, V))
    for iv in ivs:
        iv['A'] = np.minimum(iv['Aj'], 2.0 * iv['As'])
    return np.array(ratios) if ratios else np.zeros((0, 2))


def smooth(iv, L_ms):
    """zero-phase 10 ms boxcar of the capped A inside the interval, future half limited to L"""
    A = iv['A']; n = len(A)
    if n == 0:
        iv['Af'] = A; return
    Ls = int(round(3 * L_ms)); fut = min(SMOOTH // 2, Ls); past = SMOOTH - fut
    jj = (iv['m0'] + np.arange(n)) * GRID_A
    c = np.concatenate([[0.0], np.cumsum(A)])
    lo = np.searchsorted(jj, jj - past, 'left'); hi = np.searchsorted(jj, jj + fut, 'right')
    iv['Af'] = (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def run_la(sig, stream, L_ms, trk_lag=TRK_LAG):
    """full LA analysis of one signal: chunks, intervals, amplitudes.  Returns dict(chunks, ivs, ratios)"""
    x = sig.stream(stream); nx = len(x)
    chunks = build_chunks(sig, L_ms, trk_lag)
    ivs = []
    for ch in chunks:
        prepare_chunk(ch, nx, L_ms, trk_lag)
        jk, e = short_env(ch, x, L_ms, trk_lag)
        if len(jk) == 0:
            continue
        for k_on, k_off in find_intervals(jk, e, L_ms):
            j_on = int(jk[k_on]); j_off = int(jk[k_off]) if k_off < len(jk) else int(ch.jb_p) + 1
            if j_off - j_on < GRID_A // 2:
                continue
            ivs.append(dict(ch=ch, cid=ch.cid, j_on=j_on, j_off=j_off, ivid=len(ivs)))
    ratios = solve_amplitudes(sig, x, chunks, ivs, L_ms, trk_lag)
    for iv in ivs:
        smooth(iv, L_ms)
    return dict(chunks=chunks, ivs=ivs, ratios=ratios, L_ms=L_ms, stream=stream, trk_lag=trk_lag)
