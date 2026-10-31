"""S19-D step 2: attribute 5 ms boxes of 20-150 Hz layer energy to voice events (RESULTANT_CORE 19.1). See CHOICES.md.
usage: s19_attr.py  -> s19_attr.json + s19_attr.txt"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
from pathlib import Path
import p_primary as P
from scipy.signal import butter, sosfiltfilt
SOS3 = butter(4, [20, 150], 'bandpass', fs=3000, output='sos')
S19 = Path('/home/ksysh/r3a-dev/plan16/S19'); CACHE = S19 / 'cache'
T0 = 1359.0 / 48000.0; HOPS = 16 / 3000.0; BOX = 240; FS = 48000
TYPES = ['birth', 'REL>ON', 'ON>REL', 'release', 'window', 'fosc_jump', 'amp_jump', 'note_chg']
ROWS = [('b0p0', 'v1.6-a base'), ('b3p2', "A5' best"), ('f4', 'phase pull off')]
BAND_F = 75.0   # k=2 inside 20-150 Hz  <=> f_osc <= 75 Hz
MATCH = 0.010; COVER = 0.5


def events(d):
    st, vid = d['state'], d['voice']
    H, S = st.shape
    s0 = np.vstack([np.zeros((1, S), st.dtype), st[:-1]]); v0 = np.vstack([np.full((1, S), -1, vid.dtype), vid[:-1]])
    same = (vid == v0) & (st > 0) & (s0 > 0)
    ev = {}
    ev['birth'] = (st >= 2) & ~((s0 == 3) & same) & ~((s0 >= 2) & same)
    ev['REL>ON'] = same & (s0 == 3) & (st == 2)
    ev['ON>REL'] = same & (s0 == 2) & (st == 3)
    ev['release'] = (s0 >= 2) & ((st == 0) | ~same)
    on2 = same & (st >= 2) & (s0 >= 2)
    Np = d['Np']; Np0 = np.vstack([np.zeros((1, S), Np.dtype), Np[:-1]])
    ev['window'] = on2 & (Np0 > 0) & (Np > 0) & (np.abs(Np - Np0) / np.maximum(Np0, 1e-9) > 0.25)
    fo = d['f_osc']; fo0 = np.vstack([np.zeros((1, S), fo.dtype), fo[:-1]])
    ev['fosc_jump'] = on2 & (np.abs(fo - fo0) > 2.0)
    Pw = d['A'].astype(np.float64) * d['c'] * d['sigma']; P0 = np.vstack([np.zeros((1, S)), Pw[:-1]])
    ok = on2 & (Pw > 1e-9) & (P0 > 1e-9)
    ev['amp_jump'] = ok & (np.abs(20 * np.log10(np.where(ok, Pw, 1.0) / np.where(ok, P0, 1.0))) > 6.0)
    ft = d['f_track']; ft2 = np.vstack([np.zeros((2, S), ft.dtype), ft[:-2]]); v2 = np.vstack([np.full((2, S), -1, vid.dtype), vid[:-2]])
    ok = on2 & (vid == v2) & (ft > 0) & (ft2 > 0)
    ev['note_chg'] = ok & (np.abs(1200 * np.log2(np.where(ok, ft, 1.0) / np.where(ok, ft2, 1.0))) > 50.0)
    for k in ev:
        ev[k][0] = False
    inband = np.ones_like(fo, bool)
    return ev, inband


def slot_energy(d):
    """B1-2 style per-voice reconstruction: k=2,3 of each slot rebuilt from the trace as ResultantCore::synthesize (A5P oracle_p.rebuild), 20-150 Hz zero-phase at 3 kHz,
    energy per hop output block (16 core samples). returns (H, S) float"""
    ih = d['hop'][:, 0].astype(np.int64); st = d['state']; vid = d['voice']; H, S = st.shape
    j16 = np.arange(16) / 16.0
    E = np.zeros((H, S))
    for s in range(S):
        y = np.zeros(int(ih.max()) + 64)
        act = st[:, s] >= 1; i = 0
        while i < H:
            if not act[i]:
                i += 1; continue
            j = i + 1
            while j < H and act[j] and vid[j, s] == vid[i, s]:
                j += 1
            if j - i >= 2:
                idx = np.arange(i, j)
                th = d['theta_hat'][idx, s].astype(np.float64); ps = [d['psi_2'][idx, s].astype(np.float64), d['psi_3'][idx, s].astype(np.float64)]
                am = [d['a_2'][idx, s].astype(np.float64), d['a_3'][idx, s].astype(np.float64)]
                for q in range(1, len(idx)):
                    t0 = np.remainder(th[q - 1] + np.pi, 2 * np.pi) - np.pi
                    dth = (th[q] - th[q - 1]) / 16.0
                    ph = t0 + dth * np.arange(16)
                    base = ih[idx[q]]
                    for kk, pp, a in ((2, ps[0], am[0]), (3, ps[1], am[1])):
                        if a[q] == 0 and a[q - 1] == 0:
                            continue
                        aa = a[q - 1] + (a[q] - a[q - 1]) * j16
                        y[base:base + 16] += aa * np.cos(kk * ph + pp[q - 1] + (pp[q] - pp[q - 1]) * j16)
            i = j
        if not np.any(y):
            continue
        yb = sosfiltfilt(SOS3, y)
        E[:, s] = (yb[ih[:, None] + np.arange(16)[None, :]] ** 2).sum(1)
    return E


def attribute(d, boxes, box_sel):
    """box_sel: bool mask over boxes to include. returns dict: energy per class (exclusive, any-match), totals"""
    ih = d['hop'][:, 0].astype(np.int64); H = len(ih)
    tc_hop = (ih - 398 + 8) / 3000.0 + T0
    ev, inband = events(d)
    fo = d['f_osc']; a2 = d['a_2'].astype(np.float64)
    wt = d['_E']
    n = len(boxes); tc = (np.arange(n) + 0.5) * BOX / FS
    hn = np.clip(np.rint((tc - tc_hop[0]) / HOPS).astype(int), 0, H - 1)
    w = wt[hn]; tot = w.sum(1)
    order = np.argsort(-w, axis=1); ws = np.take_along_axis(w, order, 1); cs = np.cumsum(ws, 1)
    keep_sorted = (cs - ws) < COVER * tot[:, None]
    sel = np.zeros_like(w, bool); np.put_along_axis(sel, order, keep_sorted, 1)
    sel &= w > 0
    hit = {k: np.zeros(n, bool) for k in TYPES}
    for dd in range(-3, 4):
        h = np.clip(hn + dd, 0, H - 1)
        valid = np.abs(tc_hop[h] - tc) <= MATCH
        for k in TYPES:
            hit[k] |= valid & (ev[k][h] & sel).any(1)
    has = tot > 0
    ex = np.full(n, -1)           # -1 no voice, len(TYPES) none
    ex[has] = len(TYPES)
    for i in range(len(TYPES) - 1, -1, -1):
        ex[has & hit[TYPES[i]]] = i
    top = np.argmax(w, 1); ftop = fo[hn, top]
    m = box_sel
    E = boxes
    out = dict(total=float(E[m].sum()), novoice=float(E[m & ~has].sum()), noevent=float(E[m & (ex == len(TYPES))].sum()), none_direct=float(E[m & (ex == len(TYPES)) & (ftop <= BAND_F)].sum()),
               excl={k: float(E[m & (ex == i)].sum()) for i, k in enumerate(TYPES)},
               anym={k: float(E[m & hit[k] & has].sum()) for k in TYPES})
    # lag diagnostic: correlation of sqrt box energy with sqrt predicted weight
    return out, ev, inband, tc_hop, (w.sum(1), hn)


def counts(ev, inband, tc_hop, t0, t1):
    m = (tc_hop >= t0) & (tc_hop < t1)
    return {k: int((ev[k] & inband)[m].sum()) for k in TYPES}, float(m.sum() * HOPS)


def lag_diag(boxes, pw, sel):
    a = np.sqrt(boxes[sel]); 
    best = None
    for lag in range(-8, 9):
        b = np.sqrt(np.roll(pw, lag)[sel]); c = np.corrcoef(a, b)[0, 1]
        if best is None or c > best[0]: best = (c, lag)
    return best


def main():
    out = {}
    songs = sorted(P.MUSIC)
    for lab, nm in ROWS:
        res = {'win': {'tot': None}, 'songs': []}
        win_acc = None; win_cnt = {k: 0 for k in TYPES}; win_dur = 0.0
        for i in range(len(P.MUSIC)):
            f = CACHE / f'r_{lab}_s{i:02d}.npz'
            if not f.exists():
                continue
            z = np.load(f); d = {k: z[k] for k in z.files if k != 'box'}; boxes = z['box']; d['_E'] = slot_energy(d)
            n = len(boxes); tcb = (np.arange(n) + 0.5) * BOX / FS
            allsel = np.ones(n, bool)
            r, ev, inb, tch, (pw, hn) = attribute(d, boxes, allsel)
            c, dur = counts(ev, inb, tch, 0, 1e9)
            lg = lag_diag(boxes, pw, pw > 0)
            res['songs'].append(dict(idx=i, name=P.MUSIC[i].name, res=r, counts=c, dur=dur, lag=lg))
            for sk, j in P.SONG_IDX.items():
                if j != i: continue
                for (s, t0, t1) in P.WINDOWS:
                    if s != sk: continue
                    selw = (tcb >= t0) & (tcb < t1)
                    rw, *_ = attribute(d, boxes, selw)
                    cw, dw = counts(ev, inb, tch, t0, t1)
                    if win_acc is None:
                        win_acc = {kk: (dict.fromkeys(TYPES, 0.0) if isinstance(rw[kk], dict) else 0.0) for kk in rw}
                    for kk in rw:
                        if isinstance(rw[kk], dict):
                            for k in TYPES: win_acc[kk][k] += rw[kk][k]
                        else:
                            win_acc[kk] += rw[kk]
                    for k in TYPES: win_cnt[k] += cw[k]
                    win_dur += 14.0 if False else (t1 - t0)
        res['win'] = dict(res=win_acc, counts=win_cnt, dur=win_dur)
        out[lab] = res
    json.dump(out, open(S19 / 's19_attr.json', 'w'), indent=1)
    return out


if __name__ == '__main__':
    main()