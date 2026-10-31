"""Rows of the comparison table as VOICE lists (t, f, amp) and the common synthesis (k = 2, 3 phase-continuous oscillators, voicing-0 P1 weights,
causal output filter kOutSos at 3 kHz, x16 to 48 kHz).  Every row goes through exactly the same synthesis."""
import numpy as np
from scipy.signal import sosfilt, resample_poly
from data import HOP_S, FS, stream_time
import tables as T
from la import GRID_A, FADE_S

FSC = 3000.0


def _runs(h):
    cut = np.flatnonzero(np.diff(h) != 1) + 1
    return list(zip(np.r_[0, cut], np.r_[cut, len(h)]))


def _voice(tc, hs, f, amp, **meta):
    """voice from contiguous hop indices hs: one hop of zero amplitude before/after"""
    t = np.concatenate([[tc[hs[0]] - HOP_S], tc[hs], [tc[hs[-1]] + HOP_S]])
    ff = np.concatenate([[f[0]], f, [f[-1]]]); aa = np.concatenate([[0.0], amp, [0.0]])
    return dict(t=t, f=ff, amp=aa, hs=hs, **meta)


def voices_core(sig):
    d = sig.core_d; tc = sig.core_tc; st = d['state']
    out = []
    for v in np.unique(d['voice'][st > 0]):
        hs, js = np.nonzero((d['voice'] == v) & (st > 0))
        o = np.argsort(hs); hs, js = hs[o], js[o]
        for a, b in _runs(hs):
            h, j = hs[a:b], js[a:b]
            f = d['fosc'][h, j]; amp = d['A'][h, j] * d['c'][h, j] * d['sig'][h, j]
            out.append(_voice(tc, h, f, amp, kind='core', vid=int(v), state=st[h, j].astype(int)))
    return out


def voices_p1(sig, fade_min=0.0):
    ts, tc, H = sig.ts, sig.tc1, sig.nhop
    valid = ts[:H, :, 1] > 0
    ident = (ts[:H, :, 0] + 65536 * ts[:H, :, 13]).astype(np.int64)
    out = []
    for tid in np.unique(ident[valid]):
        hs, js = np.nonzero(valid & (ident == tid))
        for a, b in _runs(hs):
            h, j = hs[a:b], js[a:b]
            f = ts[h, j, 2]; fade = ts[h, j, 7]; amp = ts[h, j, 4] * fade
            out.append(_voice(tc, h, f, amp, kind='p1', vid=int(tid), fade=fade))
    return out


def voices_la(res, on_flags=None, sig_tc=None):
    """LA voices: one per interval that is ON.  on_flags: bool array indexed by interval id (None = all on)."""
    out = []
    Ls = int(round(3 * res['L_ms']))
    for iv in res['ivs']:
        if on_flags is not None and not on_flags[iv['ivid']]:
            continue
        n = len(iv['Af'])
        if n == 0:
            continue
        ch = iv['ch']
        jj = (iv['m0'] + np.arange(n)) * GRID_A
        t = stream_time(jj)
        t_on = stream_time(iv['j_on']); t_off = stream_time(iv['j_off'])
        gin = np.clip((t - t_on) / (FADE_S / FSC), 0.0, 1.0)
        amp = iv['Af'] * gin
        tt = np.concatenate([[t_on], t, [t_off, t_off + FADE_S / FSC]])
        aa = np.concatenate([[0.0], amp, [amp[-1], 0.0]])
        shift = max(ch.D, 0) / FSC
        ff = np.interp(tt - shift, ch.tc, ch.f)
        out.append(dict(t=tt, f=ff, amp=aa, kind='la', ivid=iv['ivid'], cid=ch.cid))
    return out


def render_layer(voices, dur_s, lag=0.0):
    """3 kHz layer (causal kOutSos filtered)"""
    n = int(np.ceil(dur_s * FSC)) + 8
    y = np.zeros(n)
    for v in voices:
        t = v['t'] + lag
        i0 = max(0, int(np.floor(t[0] * FSC))); i1 = min(n, int(np.ceil(t[-1] * FSC)) + 1)
        if i1 <= i0 + 1:
            continue
        tt = np.arange(i0, i1) / FSC
        f = np.interp(tt, t, v['f']); a = np.interp(tt, t, v['amp'], left=0.0, right=0.0)
        ph = 2 * np.pi * np.cumsum(f) / FSC
        g2, g3 = T.harm_gains(f, 3)
        y[i0:i1] += a * (g2 * np.cos(2 * ph) + g3 * np.cos(3 * ph))
    return sosfilt(T.OUT_SOS, y)


def up48(y3):
    return resample_poly(y3, 16, 1)
