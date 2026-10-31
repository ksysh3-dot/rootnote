"""S19-O oracle library (see CHOICES.md). Offline, numbers only. Reads S19/cache; never touches engine sources."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19')
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfiltfilt, sosfilt
import s19_attr as A
import p_primary as P

O_DIR = Path('/home/ksysh/r3a-dev/plan16/S19/O'); OC = O_DIR / 'cache'; OC.mkdir(exist_ok=True)
CACHE = A.CACHE
TYPES = A.TYPES
NT = len(TYPES)
CFS = 3000.0
HOPS = 16 / 3000.0
FSH = 1.0 / HOPS            # 187.5 Hz hop rate
SOS_LO = A.SOS3
SOS_MID = butter(4, [150, 600], 'bandpass', fs=3000, output='sos')
J16 = np.arange(16)
JT = J16 / 16.0
SEG_START = 6               # hops after the start event (32 ms)
SEG_MIN = 8


def load(row, i):
    z = np.load(CACHE / f'r_{row}_s{i:02d}.npz')
    d = {k: z[k] for k in z.files if k != 'box'}
    boxes = z['box']
    f = OC / f'Eslot_{row}_{i:02d}.npy'
    if f.exists():
        d['_E'] = np.load(f)
    else:
        d['_E'] = A.slot_energy(d)
        np.save(f, d['_E'])
    return d, boxes


# ---------------------------------------------------------------- classes (S19 attribute logic, reproduced)
def classify(d, boxes):
    ih = d['hop'][:, 0].astype(np.int64); H = len(ih)
    tc_hop = (ih - 398 + 8) / 3000.0 + A.T0
    ev, _ = A.events(d)
    w0 = d['_E']
    n = len(boxes); tc = (np.arange(n) + 0.5) * A.BOX / A.FS
    hn = np.clip(np.rint((tc - tc_hop[0]) / A.HOPS).astype(int), 0, H - 1)
    w = w0[hn]; tot = w.sum(1)
    order = np.argsort(-w, axis=1); ws = np.take_along_axis(w, order, 1); cs = np.cumsum(ws, 1)
    keep_sorted = (cs - ws) < A.COVER * tot[:, None]
    sel = np.zeros_like(w, bool); np.put_along_axis(sel, order, keep_sorted, 1)
    sel &= w > 0
    hit = {k: np.zeros(n, bool) for k in TYPES}
    for dd in range(-3, 4):
        h = np.clip(hn + dd, 0, H - 1)
        valid = np.abs(tc_hop[h] - tc) <= A.MATCH
        for k in TYPES:
            hit[k] |= valid & (ev[k][h] & sel).any(1)
    has = tot > 0
    ex = np.full(n, -1)
    ex[has] = NT
    for i in range(NT - 1, -1, -1):
        ex[has & hit[TYPES[i]]] = i
    nc20 = np.zeros(n, bool)
    for dd in range(-6, 7):
        h = np.clip(hn + dd, 0, H - 1)
        valid = np.abs(tc_hop[h] - tc) <= 0.020
        nc20 |= valid & (ev['note_chg'][h] & sel).any(1)
    nc20 &= has
    return dict(hn=hn, tc=tc, ex=ex, nc20=nc20, ev=ev, ih=ih, tc_hop=tc_hop)


def masks(cl, n, sk=None):
    """window mask (pooled windows of this song) / song mask"""
    out = {'song': np.ones(n, bool)}
    if sk is not None:
        m = np.zeros(n, bool)
        for (s, t0, t1) in P.WINDOWS:
            if s == sk:
                m |= (cl['tc'] >= t0) & (cl['tc'] < t1)
        out['win'] = m
    return out


def class_sums(cl, Elo, Emid, ms, render=None):
    """Elo/Emid per-hop block energies (H,). returns {mask: {cls: value}}"""
    hn, ex, nc20 = cl['hn'], cl['ex'], cl['nc20']
    el = Elo[hn]; em = Emid[hn]
    out = {}
    for name, m in ms.items():
        r = dict(noevent=el[m & (ex == NT)].sum(), event=el[m & (ex >= 0) & (ex < NT)].sum(), novoice=el[m & (ex == -1)].sum(), all=el[m].sum(),
                 nc20=el[m & nc20].sum(), mid=em[m].sum())
        for i, k in enumerate(TYPES):
            r['ex_' + k] = el[m & (ex == i)].sum()
        if render is not None:
            r.update(rnoevent=render[m & (ex == NT)].sum(), revent=render[m & (ex >= 0) & (ex < NT)].sum(), rnovoice=render[m & (ex == -1)].sum(), rall=render[m].sum(),
                     rnc20=render[m & nc20].sum())
            for i, k in enumerate(TYPES):
                r['rex_' + k] = render[m & (ex == i)].sum()
        out[name] = {k: float(v) for k, v in r.items()}
    return out


# ---------------------------------------------------------------- runs, segments
def make_runs(d, cl):
    """list of run dicts: slot s, hop rows idx (j-i >= 2), arrays, event position lists"""
    st, vid, ev = d['state'], d['voice'], cl['ev']
    H, S = st.shape
    ih = cl['ih']
    runs = []
    for s in range(S):
        act = st[:, s] >= 1; i = 0
        while i < H:
            if not act[i]:
                i += 1; continue
            j = i + 1
            while j < H and act[j] and vid[j, s] == vid[i, s]:
                j += 1
            if j - i >= 2:
                idx = np.arange(i, j)
                r = dict(s=s, idx=idx, th=d['theta_hat'][idx, s].astype(np.float64), ps2=d['psi_2'][idx, s].astype(np.float64), ps3=d['psi_3'][idx, s].astype(np.float64),
                         a2=d['a_2'][idx, s].astype(np.float64), a3=d['a_3'][idx, s].astype(np.float64), state=st[idx, s],
                         pos=(ih[idx[1:]][:, None] + J16[None, :]).ravel())
                n = len(idx)
                birth = np.flatnonzero(ev['birth'][idx, s]); relon = np.flatnonzero(ev['REL>ON'][idx, s])
                onrel = np.flatnonzero(ev['ON>REL'][idx, s]); nc = np.flatnonzero(ev['note_chg'][idx, s])
                groups = []
                if len(nc):
                    g0 = nc[0]; gp = nc[0]
                    for p in nc[1:]:
                        if p - gp <= 2:
                            gp = p
                        else:
                            groups.append((g0, gp)); g0 = p; gp = p
                    groups.append((g0, gp))
                evs = [(int(p), int(p) + SEG_START, 'birth') for p in birth] + [(int(p), int(p) + SEG_START, 'relon') for p in relon]
                evs += [(max(g0 - 2, 0), g1 + SEG_START, 'note') for (g0, g1) in groups]
                evs.sort()
                cut_pts = [e for (e, _, _) in evs] + [int(p) for p in onrel]
                cut_pts = np.array(sorted(cut_pts), int)
                segs = []
                for (e, sS, kind) in evs:
                    nxt = cut_pts[cut_pts > e]
                    # segment ends before the next start event / ON>REL (an event inside the warm-up kills this segment)
                    lim = n - 1
                    if len(nxt):
                        lim = min(n - 1, int(nxt[0]) - 1)
                    q = sS
                    if q < 1 or q > lim:
                        continue
                    end = q
                    while end + 1 <= lim and r['state'][end + 1] == 2:
                        end += 1
                    if r['state'][q] != 2:
                        continue
                    if end - q + 1 >= SEG_MIN:
                        segs.append((q, end))
                r['segs'] = segs
                r['xf'] = [e for (e, _, k) in evs if k == 'note' and e >= 2 and r['state'][e] == 2 and r['state'][e - 1] == 2]
                runs.append(r)
            i = j
    return runs


# ---------------------------------------------------------------- smoothing
_SOS_CACHE = {}


def _sos(fc):
    if fc not in _SOS_CACHE:
        _SOS_CACHE[fc] = butter(2, fc / (FSH / 2), 'low', output='sos')
    return _SOS_CACHE[fc]


def smooth(x, fc, causal=False):
    n = len(x)
    line = np.linspace(x[0], x[-1], n)
    r = x - line
    pad = int(min(700, 3 * FSH / fc)) + 4
    rp = np.concatenate([np.zeros(pad), r, np.zeros(pad)])
    sos = _sos(fc)
    y = (sosfilt(sos, rp) if causal else sosfiltfilt(sos, rp, padtype=None))[pad:pad + n]
    y = y - np.linspace(y[0], y[-1], n)
    return line + y


def apply_sustain(r, fc, do_f, do_a, causal, dev=None):
    th, a2, a3 = r['th'].copy(), r['a2'].copy(), r['a3'].copy()
    for (s0, s1) in r['segs']:
        if do_f:
            qs = np.arange(s0, s1 + 1)
            F = (th[qs] - th[qs - 1]) / (2 * np.pi * HOPS)
            Fs = smooth(F, fc, causal)
            dd = Fs - F
            dd = dd - dd.mean()
            Fn = F + dd
            if dev is not None:
                dev['cent'].append(1200 * np.log2(np.maximum(Fn, 1e-6) / np.maximum(F, 1e-6)))
            th[qs] = th[s0 - 1] + np.cumsum(Fn * 2 * np.pi * HOPS)
        if do_a:
            for arr, nm in ((a2, 'a2'), (a3, 'a3')):
                seg = arr[s0:s1 + 1].copy()
                new = np.maximum(smooth(seg, fc, causal), 0.0)
                if dev is not None and nm == 'a2':
                    ok = (seg > 1e-7) & (new > 1e-7)
                    dev['db'].append(20 * np.log10(np.where(ok, new, 1.0) / np.where(ok, seg, 1.0))[ok])
                arr[s0:s1 + 1] = new
    return th, a2, a3


def synth_run(r, th, a2, a3):
    t0 = np.remainder(th[:-1] + np.pi, 2 * np.pi) - np.pi
    dth = (th[1:] - th[:-1]) / 16.0
    ph = t0[:, None] + dth[:, None] * J16[None, :]
    out = np.zeros_like(ph)
    for kk, ps, a in ((2, r['ps2'], a2), (3, r['ps3'], a3)):
        aa = a[:-1, None] + (a[1:] - a[:-1])[:, None] * JT[None, :]
        pp = ps[:-1, None] + (ps[1:] - ps[:-1])[:, None] * JT[None, :]
        out += aa * np.cos(kk * ph + pp)
    return out.ravel()


def apply_xf(r, th, a2, a3, of, T_ms):
    N = int(round(T_ms * CFS / 1000.0))
    n_ = np.arange(N)
    g_new = 0.5 * (1 - np.cos(np.pi * n_ / N)); g_old = 1 - g_new
    for e in r['xf']:
        s = 16 * (e - 1)
        ne = min(N, len(of) - s)
        if ne <= 0:
            continue
        Fold = (th[e - 1] - th[e - 2]) / (2 * np.pi * HOPS)
        ph = th[e - 1] + 2 * np.pi * Fold * n_[:ne] / CFS
        old = a2[e - 1] * np.cos(2 * ph + r['ps2'][e - 1]) + a3[e - 1] * np.cos(3 * ph + r['ps3'][e - 1])
        of[s:s + ne] = of[s:s + ne] * g_new[:ne] + old * g_old[:ne]


def recon_bands(d, cl, runs, variant, slots=None, dev=None):
    """variant: ('base',), ('sus', fc, do_f, do_a, causal), ('xf', T). returns (Elo, Emid) per hop"""
    ih = cl['ih']
    y = np.zeros(int(ih.max()) + 64)
    for r in runs:
        if slots is not None and r['s'] not in slots:
            continue
        if variant[0] == 'sus':
            th, a2, a3 = apply_sustain(r, variant[1], variant[2], variant[3], variant[4], dev)
        else:
            th, a2, a3 = r['th'], r['a2'], r['a3']
        of = synth_run(r, th, a2, a3)
        if variant[0] == 'xf':
            apply_xf(r, th, a2, a3, of, variant[1])
        y[r['pos']] += of
    yl = sosfiltfilt(SOS_LO, y); ym = sosfiltfilt(SOS_MID, y)
    ix = ih[:, None] + J16[None, :]
    return (yl[ix] ** 2).sum(1), (ym[ix] ** 2).sum(1)
