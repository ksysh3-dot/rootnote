"""Plan16 D common helpers (readings: CHOICES.md).  Stem activity -15 dB, stem-aware truth, voice annotation (B2 classes), multi-component layer renderer."""
import sys, json
for p in ('/home/ksysh/r3a-dev/plan16/D', '/home/ksysh/r3a-dev/plan16/S', '/home/ksysh/r3a-dev/plan16/A', '/home/ksysh/r3a-dev/la0'):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np
from scipy.signal import sosfilt
import ladder as LD
import s_run as SR
import synth16 as SY
from data import *
import data as DATA
import labels, rows as R, la, tables as T, evaluate as E, metrics as MT

D_DIR = HOME / 'r3a-dev/plan16/D'
D_CACHE = D_DIR / 'cache'; D_CACHE.mkdir(exist_ok=True)
SONGS = LD.SONGS
LAGS = LD.LAGS
LAG = LAGS['core']
I_MIN = LD.I_MIN
L_RS = LD.L_RS
RAW_A = SR.RAW_A
TOL = 50.0
CLS = {'m': 0, 'x': 1, 's': 2}          # matched / mismatch / silence
NCOMP = 2 + 12


def cents(f, f0):
    return 1200 * np.log2(np.maximum(f, 1e-9) / f0)


def r3_right(keys=SONGS):
    return float(sum(RAW_A['res'][k]['R3']['v6b']['E_right'] for k in keys))


# ------------------------------------------------------------------------------------------ stem activity -15 dB (B1)
def act15(segs, bz, dur=30.0):
    band = X.band_fft(np.asarray(bz[:int((dur + 1.0) * FS)], float), 40, 220)
    env = np.sqrt(np.convolve(band ** 2, np.ones(480) / 480, 'same'))[::16]
    tj = np.arange(len(env)) * 16.0 / FS
    p95 = float(np.percentile(env[tj > 0.5], 95)) if (tj > 0.5).any() else 1.0
    out = []
    thr = 10 ** (-15 / 20)
    for k, sg in enumerate(segs):
        prev_e = segs[k - 1]['e'] if k else -1e9
        next_s = segs[k + 1]['s'] if k + 1 < len(segs) else 1e9
        lo = max(sg['s'] - 0.150, prev_e, 0.0); hi = min(sg['e'] + 0.500, next_s, dur)      # clipped to the excerpt [0, dur]
        w_in = (tj >= sg['s']) & (tj <= sg['e'])
        if not w_in.any():
            out.append(dict(on=sg['s'], off=sg['e'], peak=0.0, active=False)); continue
        i_pk = np.flatnonzero(w_in)[np.argmax(env[w_in])]
        P_ = env[i_pk]
        w = np.flatnonzero((tj >= lo) & (tj <= hi))
        if not len(w) or not (w[0] <= i_pk <= w[-1]):
            out.append(dict(on=sg['s'], off=sg['e'], peak=float(P_), active=False)); continue
        ok = env[w] >= P_ * thr
        pos = int(np.flatnonzero(w == i_pk)[0])
        a = pos
        while a > 0 and ok[a - 1]:
            a -= 1
        b = pos
        while b < len(w) - 1 and ok[b + 1]:
            b += 1
        out.append(dict(on=float(tj[w[a]]), off=float(tj[w[b]]), peak=float(P_), active=bool(P_ >= p95 * 1e-2)))
    return out


# ------------------------------------------------------------------------------------------ stem-aware truth
class SATruth(labels.Truth):
    """V6b wrong, plus the stem-aware excuse (only AFTER the MIDI end of a truth segment, inside its -15 dB stem activity)"""
    def __init__(self, key, tc, segs, act):
        super().__init__(key, tc)
        self.E_ = np.array([s['e'] for s in segs]); self.F_ = np.array([s['f'] for s in segs])
        self.O_ = np.array([(a['off'] if a['active'] else s['e']) for a, s in zip(act, segs)])

    def wrong2(self, h, f):
        f = np.asarray(f, float); h = np.asarray(h)
        base = labels.Truth.wrong(self, h, f)
        sa = base.copy()
        if len(self.F_) and base.any():
            t = self.tc[h]
            for k in range(len(self.F_)):
                m = sa & (t >= self.E_[k]) & (t < self.O_[k])
                if m.any():
                    ok = np.zeros(int(m.sum()), bool)
                    for kk in (.5, 1.0, 2.0, 3.0):
                        ok |= np.abs(cents(f[m], kk * self.F_[k])) <= TOL
                    idx = np.flatnonzero(m); sa[idx[ok]] = False
        return base, sa


# ------------------------------------------------------------------------------------------ annotation (B2 classes)
def annotate(voices, segs):
    """adds v['cls'] (0 matched / 1 mismatch / 2 silence) and v['w'] (winner segment index or -1)"""
    for v in voices:
        t, a = v['t'], v['amp']
        nz = np.flatnonzero(a[1:-1] > 0) + 1 if len(a) > 2 else np.zeros(0, int)
        if not len(nz) or not len(segs):
            v['cls'], v['w'] = 2, -1; continue
        t_on = float(t[nz[0]]); t_off = float(t[nz[-1]] + HOP_S)
        if 'state' in v and len(v['state']) == len(a) - 2:
            st = np.asarray(v['state']); fh = v['f'][1:-1][st >= 2]
            fm = float(np.median(fh)) if len(fh) else float(np.median(v['f'][nz]))
        else:
            fm = float(np.median(v['f'][nz]))
        w, occ, bo = SR.occupancy(t_on, t_off, segs)
        if w < 0:
            v['cls'], v['w'] = 2, -1
        elif SR.compat(fm, segs[w]['f']):
            v['cls'], v['w'] = 0, w
        else:
            v['cls'], v['w'] = 1, w
    return voices


def categories(tt, w, S_, E_):
    """0 spans (another bass note sounds), 1 tail, 2 front, 3 other  (fu.py rule)"""
    if w < 0:
        return np.full(len(tt), 3, int)
    idx = np.searchsorted(S_, tt, 'right') - 1
    cont = np.where((idx >= 0) & (tt < E_[np.clip(idx, 0, None)]), idx, -1)
    ca = (cont >= 0) & (cont != w)
    sil = cont < 0
    cb = sil & (tt >= E_[w]); cc = sil & (tt < S_[w])
    cat = np.full(len(tt), 3, int)
    cat[cc] = 2; cat[cb] = 1; cat[ca] = 0
    return cat


def comp_fn_factory(truth, tc, lag, segs):
    S_ = np.array([s['s'] for s in segs]); E_ = np.array([s['e'] for s in segs])

    def fn(v, tt, f, a):
        t0 = tt - lag
        h = np.clip(np.rint((t0 - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
        uh, inv = np.unique(h, return_inverse=True)
        fh = np.interp(tc[uh], v['t'], v['f'])
        wb, ws = truth.wrong2(uh, fh)
        wb, ws = wb[inv], ws[inv]
        comp = np.zeros(len(tt), int)
        comp[wb & ~ws] = 1
        if ws.any():
            cls = v.get('cls', 2); w = v.get('w', -1)
            cat = categories(tt, w, S_, E_) if len(segs) else np.full(len(tt), 3, int)
            comp[ws] = 2 + cls * 4 + cat[ws]
        return comp
    return fn


def render_multi(voices, dur_s, comp_fn, ncomp=NCOMP):
    n = int(np.ceil(dur_s * FSC)) + 8
    Y = np.zeros((ncomp, n))
    for v in voices:
        t = v['t']
        i0 = max(0, int(np.floor(t[0] * FSC))); i1 = min(n, int(np.ceil(t[-1] * FSC)) + 1)
        if i1 <= i0 + 1:
            continue
        tt = np.arange(i0, i1) / FSC
        f = np.interp(tt, t, v['f']); a = np.interp(tt, t, v['amp'], left=0.0, right=0.0)
        ph = 2 * np.pi * np.cumsum(f) / FSC
        G = SY.engine_gains(f, 8)
        s = np.zeros(len(tt))
        for k in range(2, 9):
            s += G[k - 2] * np.cos(k * ph)
        c = comp_fn(v, tt, f, a)
        x = a * s
        for cc in np.unique(c):
            Y[cc, i0:i1] += np.where(c == cc, x, 0.0)
    return sosfilt(T.OUT_SOS, Y, axis=1)


def energies(Y):
    """dict of energies (t > 0.5 s) from the component layers"""
    y = Y[:, I_MIN:]
    e = lambda x: float(np.sum(x ** 2))
    return dict(E_right_v6b=e(y[0]), E_wrong_v6b=e(y[1:].sum(0)), E_right_sa=e(y[0] + y[1]), E_wrong_sa=e(y[2:].sum(0)),
                cells=[e(y[2 + i]) for i in range(12)], E_full=e(y.sum(0)))


def measure_row(voices, lag, sig, truth, dur, segs):
    fn = comp_fn_factory(truth, sig.tc1, lag, segs)
    Y = render_multi(E.shift(voices, lag), dur + 0.3, fn)
    return energies(Y)
