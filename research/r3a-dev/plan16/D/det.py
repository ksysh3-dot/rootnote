"""Plan16 D detector (E-p, E-e, E-r) + D-full / D-oracle voice construction.  Readings: CHOICES.md sections 3-5."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import dsig                                  # noqa: patches data (audio keys, cache)
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from dcommon import *

HOP = HOP_S
L_RS = LD.L_RS
SLOPE_LO, SLOPE_HI = -60.0 * 16 / 3000, 10.0 * 16 / 3000          # dB per hop
FADE_EP, FADE_EE = 0.010, 0.015
REF_PRE = 26
DB = lambda a: 20 * np.log10(np.maximum(a, 1e-6))


# ------------------------------------------------------------------------------------------ causal LS features
def ls_feat(x, jend, f, N, ridge=1e-4, block=6000):
    """causal LS at constant frequency f over N samples ending at jend (Hann past half).  returns amp^2, mean-square residual"""
    n_ = np.arange(-(N - 1), 1)
    w = 0.5 * (1 + np.cos(np.pi * n_ / (N + 1)))
    A2 = np.zeros(len(jend)); RS = np.zeros(len(jend))
    for s in range(0, len(jend), block):
        je = jend[s:s + block]; ff = np.maximum(f[s:s + block], 1.0)
        J = je[:, None] + n_[None, :]
        ok = (J >= 0) & (J < len(x))
        xs = np.where(ok, x[np.clip(J, 0, len(x) - 1)], 0.0)
        wm = w[None, :] * ok
        ph = 2 * np.pi * ff[:, None] * n_[None, :] / FSC
        c, s_ = np.cos(ph), np.sin(ph)
        gcc = (wm * c * c).sum(1); gss = (wm * s_ * s_).sum(1); gcs = (wm * c * s_).sum(1)
        rc = (wm * c * xs).sum(1); rs = (wm * s_ * xs).sum(1)
        lam = ridge * (gcc + gss) / 2
        a11, a22 = gcc + lam, gss + lam
        det = np.maximum(a11 * a22 - gcs ** 2, 1e-30)
        al = (a22 * rc - gcs * rs) / det; be = (a11 * rs - gcs * rc) / det
        A2[s:s + block] = al ** 2 + be ** 2
        res = xs - al[:, None] * c - be[:, None] * s_
        RS[s:s + block] = (wm * res ** 2).sum(1) / np.maximum(wm.sum(1), 1e-30)
    return A2, RS


def line_pred(y):
    """pred[i], slope[i] (dB/hop, clipped): linear fit over y[i-26 .. i-4] extended to i; nan for i < 26"""
    n = len(y); pred = np.full(n, np.nan); slope = np.full(n, np.nan)
    if n < REF_PRE + 1:
        return pred, slope
    W = sliding_window_view(y, 23)                      # window k covers y[k .. k+22]
    k = np.arange(23) - 11.0
    yb = W.mean(1)
    b = np.clip((k[None, :] * (W - yb[:, None])).sum(1) / (k ** 2).sum(), SLOPE_LO, SLOPE_HI)
    idx = np.arange(REF_PRE, n)                         # i; window start i-26, centre i-15
    pred[idx] = yb[idx - REF_PRE] + b[idx - REF_PRE] * 15.0
    slope[idx] = b[idx - REF_PRE]
    return pred, slope


class SongData:
    """per-song cached features (setting independent)"""
    def __init__(self, sig):
        self.sig = sig; self.x = sig.bh
        d = sig.core_d; tc = sig.core_tc; self.tc = tc
        self.T = tc + LAG
        st = d['state']
        self.runs = []
        for v in np.unique(d['voice'][st > 0]):                 # same iteration as rows.voices_core
            hs, js = np.nonzero((d['voice'] == v) & (st > 0))
            o = np.argsort(hs); hs, js = hs[o], js[o]
            for a, b in R._runs(hs):
                h, j = hs[a:b], js[a:b]
                self.runs.append(dict(vid=int(v), hs=h, js=j, f=d['fosc'][h, j].copy(), st=st[h, j].astype(int), co=(d['coast'][h, j] > 0),
                                      amp=(d['A'][h, j] * d['c'][h, j] * d['sig'][h, j]).copy(), T=self.T[h], jj=stream_index(self.T[h])))
        allj = np.concatenate([r['jj'] for r in self.runs]) if self.runs else np.zeros(0)
        allf = np.concatenate([r['f'] for r in self.runs]) if self.runs else np.zeros(0)
        je = np.rint(allj).astype(int)
        A32, _ = ls_feat(self.x, je, allf, 32)
        A64, RS64 = ls_feat(self.x, je, allf, 64)
        Am, _ = ls_feat(self.x, je, np.maximum(allf - 10.0, 5.0), 64)
        Ap, _ = ls_feat(self.x, je, allf + 10.0, 64)
        Eb = np.maximum(np.maximum(A64, Am), Ap)
        o = 0
        for r in self.runs:
            n = len(r['hs']); sl = slice(o, o + n); o += n
            r['Aobs'] = DB(np.sqrt(A32[sl]))
            r['Eb'] = 10 * np.log10(np.maximum(Eb[sl], 1e-14))
            r['rho'] = 10 * np.log10(np.maximum(RS64[sl], 1e-16) / np.maximum(A64[sl] / 2, 1e-16))
            r['predA'], r['slopeA'] = line_pred(r['Aobs'])
            r['predE'], _ = line_pred(r['Eb'])
        # P1 reference-trace candidates (hop level)
        ts = sig.ts[:sig.nhop]
        self.ts_f = ts[:, :, 2]; self.ts_ok = (ts[:, :, 1] > 0) & (ts[:, :, 2] >= 30) & (ts[:, :, 2] <= 300)
        self.ts_id = (ts[:, :, 0] + 65536 * ts[:, :, 13]).astype(np.int64)
        hh, jj_ = np.nonzero(self.ts_ok)
        jend = np.rint(stream_index(self.T[hh])).astype(int)
        ff = self.ts_f[hh, jj_]
        a0, _ = ls_feat(self.x, jend, ff, 64); a1, _ = ls_feat(self.x, jend, np.maximum(ff - 10, 5.0), 64); a2, _ = ls_feat(self.x, jend, ff + 10, 64)
        self.ts_E = np.full(self.ts_f.shape, np.nan)
        self.ts_E[hh, jj_] = 10 * np.log10(np.maximum(np.maximum(a0, np.maximum(a1, a2)), 1e-14))

    def alt_rise(self, h, f_v, th_db):
        """best alternate candidate at hop h: (found, f_alt) where its band energy rose >= th_db over h-6 (same track id), > 50 cent from f_v"""
        if h < 6:
            return False, 0.0
        best = (False, 0.0, -1e9)
        for j in np.flatnonzero(self.ts_ok[h]):
            if abs(cents(self.ts_f[h, j], f_v)) <= 50.0:
                continue
            jm = np.flatnonzero(self.ts_ok[h - 6] & (self.ts_id[h - 6] == self.ts_id[h, j]))
            if not len(jm):
                continue
            rise = self.ts_E[h, j] - self.ts_E[h - 6, jm[0]]
            if rise >= th_db and rise > best[2]:
                best = (True, float(self.ts_f[h, j]), rise)
        return best[0], best[1]


# ------------------------------------------------------------------------------------------ detection
def detect_run(S, r, th, log=None):
    """th: dict(db, cent, nhop).  returns (events, pieces) or (events=[], pieces=None) when nothing fires.
    event: dict(kind, ib, idc, t, f, lead, vid) ; piece: dict(i0, i1, sk, ek, ers)"""
    n = len(r['hs']); st = r['st']; co = r['co']; f = r['f']; Ao = r['Aobs']; Eb = r['Eb']; rho = r['rho']
    jj = r['jj']; hs = r['hs']
    TH, TC, NH = th['db'], th['cent'], th['nhop']
    on_idx = np.flatnonzero(st >= 2)
    events, pieces = [], []
    if not len(on_idx):
        return events, None
    pc = dict(i0=0, sk='birth', ers=[])
    note0 = int(on_idx[0]); peak = -1e9; cnt = 0; last_ep = -99; last_er = -99
    i = note0

    def lead(b, d):
        return int(np.rint(jj[d]) - np.rint(jj[b]))

    def close(pc, i1, ek):
        pc['i1'] = i1; pc['ek'] = ek; pieces.append(pc)

    def next_rebirth(j0):
        for j in range(max(j0, 1), n):
            if st[j] == 2 and st[j - 1] == 3:
                return j
        return None

    def mute_then(from_i):
        j = next_rebirth(from_i + 1)
        return j

    while i < n:
        if st[i] < 2:
            i += 1; continue
        peak = max(peak, Ao[i]) if i >= note0 else Ao[i]
        elig = (st[i] >= 2) and (not co[i])
        fired = None
        # ---------------- E-p (1): pitch step
        if elig and i - 5 >= note0 and i - 2 - last_ep >= 11 and np.all(st[i - 2:i + 1] >= 2) and not co[i - 2:i + 1].any():
            b = i - 2
            pre = float(np.median(f[b - 3:b])); post = f[b:b + 3]
            cp = cents(post, pre)
            if np.all(np.abs(cp) > TC) and (np.all(cp > 0) or np.all(cp < 0)):
                w0 = max(i - 28, 0)
                fw = f[w0:i + 1]; dc = np.diff(cents(fw, fw[0])) if len(fw) > 1 else np.zeros(0)
                glide = len(dc) > 0 and (np.all(dc >= -3) or np.all(dc <= 3)) and abs(cents(fw[-1], fw[0])) >= 100 and np.max(np.abs(dc)) <= 25
                if not glide:
                    fired = ('Ep', b, float(np.median(post)), 1)
        # ---------------- E-p (2): explanation stealing
        if fired is None and elig and i - 12 >= note0 and i - 1 - last_ep >= 11:
            if rho[i] - np.median(rho[i - 12:i - 5]) >= TH:
                ok, fa = S.alt_rise(int(hs[i]), float(f[i]), TH)
                if ok:
                    k0 = max(i - 4, note0 + 1)
                    b = k0 + int(np.argmax(rho[k0:i + 1] - rho[k0 - 1:i]))
                    fired = ('Ep', b, fa, 2)
        # ---------------- E-r
        if fired is None and elig and i - note0 >= 8 and i - last_er >= 11:
            rise = Eb[i] - Eb[i - 4:i].min()
            if i - note0 >= REF_PRE and np.isfinite(r['predE'][i]):
                pr = r['predE'][i]
            else:
                lo = note0; hi = i - 4
                pr = float(np.median(Eb[lo:hi])) if hi - lo >= 2 else np.inf
            if rise >= TH and Eb[i] >= pr + TH:
                k0 = i - 3
                b = k0 + int(np.argmax(Eb[k0:i + 1] - Eb[k0 - 1:i]))
                fired = ('Er', b, float(f[i]), 0)
        if fired is not None and fired[0] == 'Ep':
            _, b, fnew, via = fired
            ev = dict(kind='Ep', ib=int(b), idc=int(i), t=float(r['T'][b]), f=float(fnew), lead=lead(b, i), vid=r['vid'], via=via, fold=float(np.median(f[max(b - 3, 0):b])))
            events.append(ev)
            # M5 new voice?
            h = int(hs[b])
            lo_h, hi_h = max(h - 2, 0), min(h + 3, S.ts_f.shape[0])
            near = S.ts_ok[lo_h:hi_h] & (np.abs(cents(S.ts_f[lo_h:hi_h], fnew)) <= 50.0)
            comp = 35.0 <= fnew <= 220.0
            d_ = S.sig.core_d
            others = [d_['fosc'][h, q] for q in range(8) if d_['state'][h, q] >= 2 and int(d_['voice'][h, q]) != r['vid']]
            comp = comp and all(abs(cents(fnew, o)) > 50.0 for o in others)
            close(pc, b - 1, 'Ep')
            last_ep = b
            if near.any() and comp:
                ev['new'] = True
                pc = dict(i0=b, sk='Ep', ers=[]); note0 = b; peak = float(Ao[b:i + 1].max()); cnt = 0
                i += 1; continue
            ev['new'] = False
            j = mute_then(i)
            if j is None:
                pc = None; break
            events.append(dict(kind='birth', ib=j, idc=j, t=float(r['T'][j]), f=float(f[j]), lead=0, vid=r['vid']))
            pc = dict(i0=j, sk='birth2', ers=[]); note0 = j; peak = Ao[j]; cnt = 0; i = j + 1
            continue
        if fired is not None and fired[0] == 'Er':
            _, b, fr, _ = fired
            events.append(dict(kind='Er', ib=int(b), idc=int(i), t=float(r['T'][b]), f=float(fr), lead=lead(b, i), vid=r['vid']))
            pc['ers'].append(int(b)); note0 = int(b); last_er = int(b); peak = float(Ao[b:i + 1].max()); cnt = 0
            i += 1; continue
        # ---------------- E-e
        c1 = (i - note0 >= REF_PRE) and np.isfinite(r['predA'][i]) and Ao[i] < r['predA'][i] - TH
        c2 = Ao[i] < peak - 15.0
        if c1 or c2:
            cnt += 1
        else:
            cnt = 0
        if cnt >= NH:
            b = i - NH + 1
            ev = dict(kind='Ee', ib=int(b), idc=int(i), t=float(r['T'][b]), f=float(f[max(b - 1, 0)]), lead=lead(b, i), vid=r['vid'])
            events.append(ev)
            close(pc, b - 1, 'Ee')
            # revival (causal, 80 ms = 15 hops after the decision)
            rv = None
            ref0 = r['predA'][i]; sl = r['slopeA'][i]
            for k in range(i + 1, min(n, i + 16)):
                if st[k] < 2:
                    continue
                ref = (ref0 + sl * (k - i)) if np.isfinite(ref0) else peak - 12.0
                if Ao[k] >= ref - 3.0:
                    rv = k; break
            if rv is not None:
                ev['revived'] = True
                events.append(dict(kind='rev', ib=int(rv), idc=int(rv), t=float(r['T'][rv]), f=float(f[rv]), lead=0, vid=r['vid']))
                pc = dict(i0=rv, sk='rev', ers=[]); note0 = rv; peak = float(Ao[rv]); cnt = 0; i = rv + 1
                continue
            ev['revived'] = False
            j = mute_then(i)
            if j is None:
                pc = None; break
            events.append(dict(kind='birth', ib=j, idc=j, t=float(r['T'][j]), f=float(f[j]), lead=0, vid=r['vid']))
            pc = dict(i0=j, sk='birth2', ers=[]); note0 = j; peak = Ao[j]; cnt = 0; i = j + 1
            continue
        i += 1
    if pc is not None:
        close(pc, n - 1, 'run_end')
    if not any(e['kind'] in ('Ep', 'Er', 'Ee') for e in events):
        return events, None
    return events, pieces


def detect_song(S, th):
    allev, allpc = [], []
    for ri, r in enumerate(S.runs):
        ev, pc = detect_run(S, r, th)
        for e in ev:
            e['ri'] = ri
        allev.append(ev); allpc.append(pc)
    return allev, allpc


# ------------------------------------------------------------------------------------------ single-voice re-measure LS (R2's LS, vectorised)
def ls_single(x, ch, j_on, j_off, ms, block=400):
    Np, Nf = la.NP_MAX, 191
    offs = np.arange(-Np, Nf + 1)
    w = np.where(offs <= 0, 0.5 * (1 + np.cos(np.pi * offs / (Np + 1))), 0.5 * (1 + np.cos(np.pi * offs / (Nf + 1))))
    nx = len(x); out = np.zeros(len(ms))
    for s in range(0, len(ms), block):
        jc = ms[s:s + block] * la.GRID_A
        J = jc[:, None] + offs[None, :]
        okx = (J >= 0) & (J < nx)
        xs = np.where(okx, x[np.clip(J, 0, nx - 1)], 0.0)
        mask = (J >= j_on) & (J < j_off)
        jav = (jc - ch.D)[:, None]
        fav = np.interp(stream_time(jav[:, 0].astype(float)), ch.tc, ch.f)[:, None]
        ph = la._phase(ch.PH, ch.jd, J, jav, fav)
        c = np.cos(ph) * mask; s_ = np.sin(ph) * mask
        wv = w[None, :] * okx
        gcc = (wv * c * c).sum(1); gss = (wv * s_ * s_).sum(1); gcs = (wv * c * s_).sum(1)
        rc = (wv * c * xs).sum(1); rs = (wv * s_ * xs).sum(1)
        lam = la.RIDGE * (gcc + gss) / 2
        a11, a22 = gcc + lam, gss + lam
        det = np.maximum(a11 * a22 - gcs ** 2, 1e-30)
        al = (a22 * rc - gcs * rs) / det; be = (a11 * rs - gcs * rc) / det
        out[s:s + block] = np.hypot(al, be)
    return out


def smooth_grid(ms, A):
    """la.smooth on a grid-index series (within the evaluated interval)"""
    if len(A) == 0:
        return A
    fut = min(la.SMOOTH // 2, 191); past = la.SMOOTH - fut
    jj = ms * la.GRID_A
    c = np.concatenate([[0.0], np.cumsum(A)])
    lo = np.searchsorted(jj, jj - past, 'left'); hi = np.searchsorted(jj, jj + fut, 'right')
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def remeasure_window(S, ch, t_on, t_off, region_start=None):
    """returns (t_grid, A_smooth) of the single-voice LS over the window [t_on, t_off) (basis clipped to it), evaluated on the whole window or from region_start (minus 2 grid points for the smoother)"""
    j_on = int(round(float(stream_index(t_on)))); j_off = int(round(float(stream_index(t_off))))
    if j_off - j_on < la.GRID_A // 2:
        return np.zeros(0), np.zeros(0)
    m0 = int(np.ceil(j_on / la.GRID_A)); m1 = int(np.ceil(j_off / la.GRID_A))
    ms_all = np.arange(m0, m1)
    if len(ms_all) == 0:
        return np.zeros(0), np.zeros(0)
    if region_start is not None:
        jr = float(stream_index(region_start))
        ms = ms_all[ms_all * la.GRID_A >= jr - 2 * la.GRID_A - 16]
    else:
        ms = ms_all
    if len(ms) == 0:
        return np.zeros(0), np.zeros(0)
    A = ls_single(S.x, ch, j_on, j_off, ms)
    A = smooth_grid(ms, A)
    t = stream_time(ms * la.GRID_A)
    if region_start is None:
        A = A * np.clip((t - t_on) / (la.FADE_S / FSC), 0.0, 1.0)         # 5 ms ramp
    return t, A


def rc_fade(t, t0, dur, rising):
    u = np.clip((t - t0) / dur, 0.0, 1.0)
    return 0.5 * (1 - np.cos(np.pi * u)) if rising else 0.5 * (1 + np.cos(np.pi * u))


def build_piece_voices(S, r, pieces):
    """D-full voices of one modified run (input time)."""
    out = []
    T, f, amp, hs = r['T'], r['f'], r['amp'], r['hs']
    nx = len(S.x)
    last_amp = None
    for pci, pc in enumerate(pieces):
        i0, i1 = pc['i0'], pc['i1']
        if i1 < i0:
            continue
        # chunk (frequency track of the piece)
        ch = la.Chunk(); ch.cid = 0; ch.id = 0
        ch.tc = T[i0:i1 + 1].copy(); ch.f = f[i0:i1 + 1].copy()
        if len(ch.tc) == 1:
            ch.tc = np.array([ch.tc[0], ch.tc[0] + HOP]); ch.f = np.array([ch.f[0], ch.f[0]])
        la.prepare_chunk(ch, nx, L_RS, 191)
        W = [i0] + list(pc['ers']) + [i1 + 1]
        t_a = T[i0]; t_z = T[i1] + HOP                           # t_z = boundary time (fade start) / window end
        t_grid_end = T[i1] if pc['ek'] == 'run_end' else t_z
        ta_b = T[i0] - (HOP if pc['sk'] == 'birth' and i0 == 0 else 0.0)
        # fine grid
        ja = int(np.floor(float(stream_index(ta_b)) / 8.0)) * 8; jz = int(np.ceil(float(stream_index(t_grid_end)) / 8.0)) * 8
        tail = {'Ee': FADE_EE, 'Ep': FADE_EP}.get(pc['ek'], 0.0)
        jz_f = jz + int(np.ceil(tail * FSC / 8.0)) * 8 + (8 if tail else 0)
        tg = stream_time(np.arange(ja, jz_f + 1, 8).astype(float))
        fg = np.interp(tg, T[i0:i1 + 1], f[i0:i1 + 1])
        ag = np.interp(tg, T[i0:i1 + 1], amp[i0:i1 + 1])
        # re-measured regions
        for k in range(len(W) - 1):
            w0, w1 = W[k], W[k + 1] - 1
            t_on = T[w0]; t_off = T[w1] + HOP
            start_ev = (k > 0) or pc['sk'] in ('Ep', 'rev')
            end_ev = (k < len(W) - 2) or pc['ek'] in ('Ep', 'Ee')
            if start_ev:
                tr, Ar = remeasure_window(S, ch, t_on, t_off)
                if len(tr):
                    wgt = ((tg >= t_on) & (tg <= t_off)).astype(float)
                    are = np.interp(tg, tr, Ar)
                    if k > 0:                                          # M7: E-r window cap 12 dB above the previous A
                        prev = float(np.interp(t_on - HOP, tg, ag))
                        are = np.minimum(are, 4.0 * max(prev, 1e-9))
                    ag = np.where(wgt > 0, are, ag)
            elif end_ev:
                rs = t_off - 0.020
                tr, Ar = remeasure_window(S, ch, t_on, t_off, region_start=rs)
                if len(tr):
                    wgt = np.clip((tg - (rs - 0.005)) / 0.010, 0.0, 1.0) * (tg <= t_off)
                    ag = np.where(tg <= t_off, (1 - wgt) * ag + wgt * np.interp(tg, tr, Ar), ag)
        # M5: first 40 ms of an E-p-new piece capped by the previous piece's A
        if pc['sk'] == 'Ep' and last_amp is not None:
            ag = np.where(tg < t_a + 0.040, np.minimum(ag, last_amp), ag)
        # fades
        if pc['sk'] == 'Ep':
            ag = ag * rc_fade(tg, t_a, FADE_EP, True)
        if pc['ek'] in ('Ee', 'Ep'):
            end_val = float(np.interp(t_z, tg, ag)); fe = float(np.interp(t_z, tg, fg))
            held = tg > t_z
            ag = np.where(held, end_val, ag); fg = np.where(held, fe, fg)
            ag = ag * np.where(held, rc_fade(tg, t_z, tail, False), 1.0)
            last_amp = float(np.interp(t_z - HOP, tg, ag))
        else:
            last_amp = float(np.interp(t_z - HOP, tg, ag))
        t_list, f_list, a_list = list(tg), list(fg), list(ag)
        if pc['sk'] == 'birth' and i0 == 0:
            a_list[0] = 0.0
        if pc['ek'] == 'run_end':
            t_list.append(float(T[i1] + HOP)); f_list.append(float(fg[-1])); a_list.append(0.0)
        out.append(dict(t=np.array(t_list), f=np.array(f_list), amp=np.array(a_list), kind='dfull', vid=r['vid']))
    return out


def dfull_voices(S, allpc):
    """core voices (shifted into input time) for untouched runs + rebuilt pieces for modified runs"""
    cv = E.shift(R.voices_core(S.sig), LAG)
    assert len(cv) == len(S.runs), (len(cv), len(S.runs))
    out = []
    for v, r, pcs in zip(cv, S.runs, allpc):
        if pcs is None:
            out.append(v)
        else:
            out.extend(build_piece_voices(S, r, pcs))
    return out


# ------------------------------------------------------------------------------------------ D-oracle
def hop_intervals(r, i0, i1, ers):
    """ON/REL hops of r[i0..i1] -> list of interval dicts (split at gaps and 3->2), as real_intervals_core"""
    idx = np.arange(i0, i1 + 1)
    idx = idx[r['st'][idx] >= 2]
    if not len(idx):
        return []
    stt = r['st'][idx]
    cut = np.flatnonzero((np.diff(idx) != 1) | ((stt[:-1] == 3) & (stt[1:] == 2))) + 1
    out = []
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(idx)]):
        h = idx[a:b]
        t_on = float(r['T'][h[0]]); t_off = float(r['T'][h[-1]]) + HOP
        rs = [float(r['T'][e]) for e in ers if h[0] < e <= h[-1]]
        out.append(dict(t_on=t_on, t_off=t_off, fm=float(np.median(r['f'][h])), rsplits=rs, vid=r['vid']))
    return out


def oracle_intervals(S, allpc):
    out = []
    for r, pcs in zip(S.runs, allpc):
        if pcs is None:
            out += hop_intervals(r, 0, len(r['hs']) - 1, [])
        else:
            for pc in pcs:
                out += hop_intervals(r, pc['i0'], pc['i1'], pc['ers'])
    return out


def build_oracle_voices(sig, kept, segs):
    """items from kept intervals (truth f), windows cut at E-r times, merged into one voice per interval (continuous phase, no fade inside)"""
    items, grp = [], []
    nshort = 0; tshort = 0.0
    for gi, q in enumerate(kept):
        f = segs[q['w']]['f']
        cuts = [q['t_on']] + sorted(q['rsplits']) + [q['t_off']]
        for a, b in zip(cuts[:-1], cuts[1:]):
            it = SR.const_item(f, a, b)
            if it['j_off'] - it['j_on'] < la.GRID_A // 2:
                nshort += 1; tshort += max(b - a, 0.0); continue
            items.append(it); grp.append((gi, a, b))
    if not items:
        return [], nshort, tshort
    nx = len(sig.bh); chunks, ivs = [], []
    for it in items:
        ch = la.Chunk(); ch.cid = len(chunks); ch.id = len(chunks)
        ch.tc = np.asarray(it['tc'], float); ch.f = np.asarray(it['f'], float)
        la.prepare_chunk(ch, nx, L_RS, 191)
        chunks.append(ch)
        ivs.append(dict(ch=ch, cid=ch.cid, j_on=int(it['j_on']), j_off=int(it['j_off']), ivid=len(ivs)))
    la.solve_amplitudes(sig, sig.bh, chunks, ivs, L_RS, 191)
    for iv in ivs:
        la.smooth(iv, L_RS)
    # voices: windows of the same group are concatenated
    bygrp = {}
    for iv, (gi, a, b) in zip(ivs, grp):
        bygrp.setdefault(gi, []).append(iv)
    voices = []
    for gi, lst in bygrp.items():
        tt_all, aa_all = [], []
        for k, iv in enumerate(lst):
            n = len(iv['Af'])
            if n == 0:
                continue
            ch = iv['ch']
            jj = (iv['m0'] + np.arange(n)) * la.GRID_A
            t = stream_time(jj)
            t_on = stream_time(iv['j_on']); t_off = stream_time(iv['j_off'])
            amp = iv['Af'] * (np.clip((t - t_on) / (la.FADE_S / FSC), 0.0, 1.0) if k == 0 else 1.0)
            if k == 0:
                tt_all.append(np.array([t_on])); aa_all.append(np.array([0.0]))
            tt_all.append(t); aa_all.append(amp)
            if k == len(lst) - 1:
                tt_all.append(np.array([t_off, t_off + la.FADE_S / FSC])); aa_all.append(np.array([amp[-1], 0.0]))
        if not tt_all:
            continue
        tt = np.concatenate(tt_all); aa = np.concatenate(aa_all)
        o = np.argsort(tt, kind='stable'); tt, aa = tt[o], aa[o]
        voices.append(dict(t=tt, f=np.full(len(tt), segs[kept[gi]['w']]['f']), amp=aa, kind='oracle', gi=gi))
    return voices, nshort, tshort
