"""Plan16 K common code (readings: CHOICES.md).  Hit detector, K1-K3 evidence, event planner (gain curves), song context with V-style cause tags, renderer."""
import sys, os, re, time, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/K')
import dsig                                  # noqa: patches data.audio / cache (side effect: D cache copies already exist)
import numpy as np
from scipy.signal import butter, sosfilt
from dcommon import *
import dcommon as DC

K_DIR = HOME / 'r3a-dev/plan16/K'
K_CACHE = K_DIR / 'cache'; K_CACHE.mkdir(exist_ok=True)
for _p in list(DC.D_CACHE.glob('*.npz')):                 # read-only links to the existing caches; new K signals are cached in K/cache only
    if not (K_CACHE / _p.name).exists():
        os.symlink(_p, K_CACHE / _p.name)
DATA.CACHE = K_CACHE

FSA = 48000
HOPS = HOP_S
BLK = 128
SOS_LO = butter(2, [40, 200], 'bandpass', fs=FSA, output='sos')       # order-4 band-pass
SOS_HI = butter(2, [1000, 8000], 'bandpass', fs=FSA, output='sos')
HSET = (35, 36, 38, 40, 41, 43, 45, 47, 48, 50)
R3R = r3_right(SONGS)


# ------------------------------------------------------------------------------------------ audio, detector
def mono(key):
    x = np.asarray(DATA.audio(key), float)
    return x.mean(1) if x.ndim == 2 else x


def block_energies(x):
    lo = sosfilt(SOS_LO, x); hi = sosfilt(SOS_HI, x)
    nb = len(x) // BLK
    e = lambda y: 10 * np.log10((y[:nb * BLK].reshape(nb, BLK) ** 2).sum(1) + 1e-12)
    return e(lo), e(hi)


def detect_hits(x, thr_db=9.0, el_eh=None):
    """16.10.1 M3: returns array of block indices b of the triggers (t_d = b*128/48000)"""
    el, eh = block_energies(x) if el_eh is None else el_eh
    nb = len(el); out = []; nxt = 0
    ref = int(np.ceil(0.060 * FSA / BLK))                               # 23 blocks: re-trigger no earlier than t_d + 60 ms
    for b in range(19, nb):
        if b < nxt:
            continue
        if el[b] > np.median(el[b - 19:b]) + thr_db and eh[b] > np.median(eh[b - 19:b]) + thr_db:
            out.append(b); nxt = b + ref
    return np.array(out, int)


# ------------------------------------------------------------------------------------------ drum MIDI per pitch (same drum-stem rule as common16.ref)
def drum_hits(name):
    C._guard(X.SLAKH / name)
    mdir = X.SLAKH_MIDI / name
    meta = (mdir / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    drum_ids = {parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'is_drum:\s*true', parts[i + 1])}
    on, pit = [], []
    for m in sorted((mdir / 'MIDI').glob('*.mid')):
        if m.stem in drum_ids:
            for n in X.read_midi(m):
                on.append(n[0]); pit.append(n[2])
    return np.array(on, float), np.array(pit, float)


# ------------------------------------------------------------------------------------------ K2: src peaks (vectorised q4.src_peaks)
NFFT, NFR = 2048, 384
BIN = 3000.0 / NFFT
HANN = np.hanning(NFR + 1)[:-1]


def sm_at(det, ih, off):
    s0 = ih - (NFR - 1)
    idx = s0 + np.arange(NFR) - off
    fr = np.where((idx >= 0) & (idx < len(det)), det[np.clip(idx, 0, len(det) - 1)], 0.0) * HANN
    return np.abs(np.fft.rfft(fr, NFFT))


def _off(a, b, c):
    den = a - 2 * b + c
    return np.where(np.abs(den) > 1e-12, np.clip(0.5 * (a - c) / np.where(np.abs(den) > 1e-12, den, 1.0), -1, 1), 0.0)


def src_peaks_vec(sm):
    """returns (f, rel) arrays of the accepted peaks of band 0 and band 1 concatenated"""
    pf, pr = [], []
    for band in range(2):
        lb = int(np.ceil((140 if band else 20) / BIN)); hb = int(np.floor((620 if band else 200) / BIN))
        maxmag = sm[lb:hb + 1].max()
        b = np.arange(lb + 1, hb)
        v = sm[b]
        c = (v >= sm[b - 1]) & (v > sm[b + 1])
        b, v = b[c], v[c]
        if not len(b):
            continue
        ix = np.clip(b[:, None] + np.arange(-27, 28)[None, :], lb, hb)
        med = np.median(sm[ix], axis=1)
        rel = 20 * np.log10(v / maxmag + 1e-30)
        off = _off(np.log(sm[b - 1] + 1e-30), np.log(v + 1e-30), np.log(sm[b + 1] + 1e-30))
        f = (b + off) * BIN
        floor_db = -60. if band else -50.
        ok = (rel >= floor_db) & (v >= (med + 1e-20) * np.sqrt(10.))
        pf.append(f[ok]); pr.append(rel[ok])
    if not pf:
        return np.zeros(0), np.zeros(0)
    return np.concatenate(pf), np.concatenate(pr)


def evid_any(pf, f):
    """engine-like 'prominent': any accepted peak within max(4 Hz, 3 % k f) of k f, k = 1..4"""
    for k in range(1, 5):
        fk = k * f; tol = max(4.0, .03 * fk)
        if len(pf) and np.any(np.abs(pf - fk) <= tol):
            return True
    return False


def k2_test(pf, pr, f, mult=1.0):
    f = f * mult
    if f <= 0 or not len(pf):
        return False
    c1 = np.abs(cents(pf, f)) <= 30.0
    if not c1.any():
        return False
    i = np.flatnonzero(c1)[np.argmin(np.abs(cents(pf[c1], f)))]
    r1 = pr[i]
    for k in (2, 3):
        m = (np.abs(cents(pf, k * f)) <= 30.0) & (pr >= r1 - 20.0)
        if m.any():
            return True
    return False


# ------------------------------------------------------------------------------------------ voices with extras
def voices_ext(sig):
    """same voices as R.voices_core (order, t, f, amp) plus per-hop arrays: hs (core hop), js (slot), ftr (tracker f), state"""
    d = sig.core_d; tc = sig.core_tc; st = d['state']
    out = []
    for v in np.unique(d['voice'][st > 0]):
        hs, js = np.nonzero((d['voice'] == v) & (st > 0))
        o = np.argsort(hs); hs, js = hs[o], js[o]
        for a, b in R._runs(hs):
            h, j = hs[a:b], js[a:b]
            f = d['fosc'][h, j]; amp = d['A'][h, j] * d['c'][h, j] * d['sig'][h, j]
            w = R._voice(tc, h, f, amp, kind='core', vid=int(v), state=st[h, j].astype(int))
            w['js'] = j; w['ftr'] = d['ftr'][h, j].copy()
            out.append(w)
    return out


# ------------------------------------------------------------------------------------------ song context
class SongCtx:
    """one song: core voices (shifted), per-sample tag arrays (V cause logic, fixed from the core), K features, rendering"""
    def __init__(self, key, probe_nobass=True):
        t0 = time.time()
        self.key = key; self.sig = sig = Sig(key); self.dur = dur = LD.dur_of(key)
        self.segs, self.rf = segs, rf = LD.segments(key)
        self.act = act15(segs, rf['bz'], dur)
        self.truth = SATruth(key, sig.tc1, segs, self.act)
        self.nobass = len(segs) == 0
        cv = voices_ext(sig)
        ref = R.voices_core(sig)
        assert len(ref) == len(cv) and all(np.array_equal(a['amp'], b['amp']) for a, b in zip(ref, cv))
        annotate(cv, segs)
        self.voices = E.shift(cv, LAG)
        self.n = int(np.ceil((dur + 0.3) * FSC)) + 8
        self.tc = sig.tc1
        self.det_stream = sig.det; self.bh = sig.bh
        self._prep(probe_nobass)
        self.k2off = 0                      # det (band_delayed191) is already delayed: matches the engine 'prominent' flag at ~95 % (k2check.py), det[j-191] only ~73-88 %
        self._peaks = {}; self._sm_idx_log = []
        self.secs_init = time.time() - t0

    # ---- per-voice sample grids and tags (copy of the V logic)
    def _prep(self, probe_nobass):
        voices, segs, rf, truth, tc, dur = self.voices, self.segs, self.rf, self.truth, self.tc, self.dur
        nobass = self.nobass
        S_ = np.array([s['s'] for s in segs]); E_ = np.array([s['e'] for s in segs])
        FSR = 3000.0
        ss, es, ps = rf['ss'], rf['es'], rf['ps']
        bn = np.flatnonzero((es > 0) & (ss < dur)) if len(ss) else np.zeros(0, int)
        bs, be, bf = ss[bn], es[bn], 440 * 2 ** ((ps[bn] + rf['tp'] - 69) / 12)
        env = None
        if len(bn):
            band = X.band_fft(np.asarray(rf['bz'][:int((dur + 1.0) * FS)], float), 40, 220)
            env = np.sqrt(np.convolve(band ** 2, np.ones(480) / 480, 'same'))[::16]
        bpk = np.zeros(len(bn))
        for i in range(len(bn)):
            a_, b_ = max(0, int(round(bs[i] * FSR))), min(len(env) - 1, int(round(be[i] * FSR)))
            bpk[i] = env[a_:b_ + 1].max() if b_ >= a_ else 0.0
        bkeys = set(zip(np.round(rf['ss'], 3), np.round(rf['es'], 3), np.round(rf['ps'], 3)))
        ns_, ne_, npch = rf['nd_s'], rf['nd_e'], rf['nd_p']
        isb = np.array([(round(a, 3), round(b, 3), round(c, 3)) in bkeys for a, b, c in zip(ns_, ne_, npch)], bool) if len(ns_) else np.zeros(0, bool)
        os_, oe_, of0 = ns_[~isb], ne_[~isb], 440 * 2 ** ((npch[~isb] - 69) / 12)
        dh = np.asarray(rf['drum_on'], float)
        self.dh = dh
        compat_any = lambda f, f0: np.any([np.abs(cents(f, k * f0)) <= 50.0 for k in (0.5, 1.0, 2.0, 3.0)], axis=0)

        def causes(v, tt, f, a, m, nob):
            """m = silence-class sa-wrong mask -> cause array (1..5) per sample (V tests 1-5)"""
            cause = np.full(len(tt), 5, int)
            remaining = m.copy()
            if nob:
                cause[remaining] = 1; remaining[:] = False
            if remaining.any() and len(dh):
                t_, amp_ = v['t'], v['amp']
                nz = np.flatnonzero(amp_ > 0)
                if len(nz):
                    birth = float(t_[nz[0]]); t_off = float(t_[nz[-1]])
                    cand = dh[(dh >= birth - 0.3) & (dh <= t_off + 0.3)]
                    Q = []
                    for d in cand:
                        ad = float(np.interp(d, t_, amp_, left=0.0, right=0.0))
                        g = d + np.arange(1, 61) * 1e-3
                        am = float(np.max(np.interp(g, t_, amp_, left=0.0, right=0.0)))
                        if (d <= birth <= d + 0.06) or (ad > 0 and am > 2 * ad) or (ad <= 0 and am > 0):
                            Q.append(d)
                    if Q:
                        Q = np.array(Q)
                        i0 = np.searchsorted(Q, tt - 0.15, 'left'); j0 = np.searchsorted(Q, tt + 0.02, 'right')
                        md = (j0 > i0) & remaining
                        cause[md] = 2; remaining &= ~md
            if remaining.any() and len(bn):
                ie = np.clip(np.rint(tt * FSR).astype(int), 0, len(env) - 1)
                ie2 = np.clip(ie - 90, 0, len(env) - 1)
                for i in np.flatnonzero((be > tt.min() - 0.0) & (be <= tt.max())):
                    win = remaining & (tt >= be[i]) & (tt < be[i] + 0.4)
                    if not win.any():
                        continue
                    pm = np.zeros(len(tt), bool); pm[win] = compat_any(f[win], bf[i])
                    ok = pm & (env[ie] < bpk[i] * 10 ** (-15 / 20)) & (env[ie] >= bpk[i] * 10 ** (-50 / 20)) & (env[ie] <= env[ie2])
                    cause[ok & remaining] = 3; remaining &= ~ok
            if remaining.any() and len(os_):
                for i in np.flatnonzero((os_ <= tt.max()) & (oe_ > tt.min())):
                    win = remaining & (tt >= os_[i]) & (tt < oe_[i])
                    if not win.any():
                        continue
                    ok = np.zeros(len(tt), bool)
                    for k in (1, 2, 3):
                        fk = f[win] / k
                        ok[win] |= (np.abs(cents(fk, of0[i])) <= 100) | (np.abs(cents(fk, 2 * of0[i])) <= 100)
                    cause[ok] = 4; remaining &= ~ok
            cause[remaining & m] = 5
            return cause

        for v in voices:
            t = v['t']
            i0 = max(0, int(np.floor(t[0] * FSC))); i1 = min(self.n, int(np.ceil(t[-1] * FSC)) + 1)
            v['i0'], v['i1'] = i0, i1
            if i1 <= i0 + 1:
                v['ok'] = False; continue
            v['ok'] = True
            tt = np.arange(i0, i1) / FSC
            f = np.interp(tt, t, v['f']); a = np.interp(tt, t, v['amp'], left=0.0, right=0.0)
            ph = 2 * np.pi * np.cumsum(f) / FSC
            G = SY.engine_gains(f, 8)
            s = np.zeros(len(tt))
            for k in range(2, 9):
                s += G[k - 2] * np.cos(k * ph)
            t0_ = tt - LAG
            h = np.clip(np.rint((t0_ - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
            uh, inv = np.unique(h, return_inverse=True)
            fh = np.interp(tc[uh], v['t'], v['f'])
            wb, ws = truth.wrong2(uh, fh)
            wb, ws = wb[inv], ws[inv]
            comp = np.zeros(len(tt), np.int8)
            comp[wb & ~ws] = 1
            cls = v.get('cls', 2)
            comp[ws & (cls != 2)] = 2
            if cls == 2 and ws.any():
                cause = causes(v, tt, f, a, ws, nobass)
                comp[ws] = (2 + cause[ws]).astype(np.int8)
                if nobass and probe_nobass:
                    c2 = causes(v, tt, f, a, ws, False)
                    v['probe_drum'] = (ws & (c2 == 2))
            v['tt'] = tt; v['s'] = s; v['a0'] = a; v['comp'] = comp
            # hop arrays for the planner
            v['T'] = v['t'][1:-1]; v['A'] = v['amp'][1:-1]

    # ---- rendering
    def gain_for(self, v, events_by_voice, vi, tt):
        evs = events_by_voice.get(vi)
        if not evs:
            return None
        g = np.ones(len(tt))
        for e in evs:
            g *= np.interp(tt, e['tk'], e['gk'])
        return g

    def render(self, events=None, ncomp=NCOMP + 0, comp_override=None, only_comp=None):
        """events: dict voice index -> list of event dicts (with knots tk, gk).  Returns filtered layers (ncomp, n).  comp_override: dict vi -> comp array"""
        n = self.n; Y = np.zeros((max(ncomp, 9), n))
        for vi, v in enumerate(self.voices):
            if not v['ok']:
                continue
            a = v['a0']
            g = self.gain_for(v, events or {}, vi, v['tt'])
            if g is not None:
                a = a * g
            x = a * v['s']
            c = v['comp'] if comp_override is None or vi not in comp_override else comp_override[vi]
            for cc in np.unique(c):
                Y[cc, v['i0']:v['i1']] += np.where(c == cc, x, 0.0)
        return sosfilt(T.OUT_SOS, Y, axis=1)

    # ---- K features
    def peaks_at(self, h):
        """accepted src peaks at core hop h (cached)"""
        if h not in self._peaks:
            ih = int(self.sig.core_hop[h])
            sm = sm_at(self.det_stream, ih, self.k2off)
            self._peaks[h] = src_peaks_vec(sm)
            self._sm_idx_log.append((h, ih - self.k2off))
        return self._peaks[h]

    def k_arrays(self, v):
        if 'K1' not in v:
            n = len(v['T'])
            v['K1'] = np.full(n, -1, np.int8); v['K2'] = np.full(n, -1, np.int8); v['K3'] = np.full(n, -1, np.int8)
            v['K2c'] = np.full(n, -1, np.int8); v['rate'] = np.full(n, np.nan)
        return v


def k1_at(v, i):
    """tracker f stable: range over hops i-3..i <= 30 cent; all four hops must be in the run"""
    if v['K1'][i] >= 0:
        return bool(v['K1'][i])
    if i < 3:
        r = False
    else:
        f = v['ftr'][i - 3:i + 1]
        r = bool(np.all(f > 0) and abs(1200 * np.log2(f.max() / f.min())) <= 30.0)
    v['K1'][i] = int(r); return r


def k3_at(v, i, rate_lim=120.0):
    if v['K3'][i] >= 0:
        return bool(v['K3'][i])
    A = v['A']; a0 = max(0, i - 19)
    seg = A[a0:i + 1]; ip = a0 + int(np.argmax(seg))
    dt = (i - ip) * HOPS
    if dt < 0.015 or A[ip] <= 0:
        r = False; rate = np.nan
    elif A[i] <= 0:
        r = False; rate = np.inf
    else:
        rate = 20 * np.log10(A[ip] / A[i]) / dt
        r = bool(rate <= rate_lim)
    v['rate'][i] = rate
    v['K3'][i] = int(r); return r


def k2_at(ctx, v, i, control=False):
    arr = v['K2c'] if control else v['K2']
    if arr[i] >= 0:
        return bool(arr[i])
    h = int(v['hs'][i])
    pf, pr = ctx.peaks_at(h)
    f = float(v['ftr'][i])
    r = k2_test(pf, pr, f, 1.06 if control else 1.0)
    arr[i] = int(r); return r


def conf_flags(ctx, v, i, with_control=False):
    k1 = k1_at(v, i); k2 = k2_at(ctx, v, i); k3 = k3_at(v, i)
    return k1, k2, k3


# ------------------------------------------------------------------------------------------ event planner
def build_knots(ev, v, P, te):
    """gain knots of an event (CHOICES section 3)"""
    T, A = v['T'], v['A']
    ts = ev['ts']; kind = ev['kind']; g0 = P['g0']; ret = P['ret']
    tk = []; gk = []

    def add(t, g):
        tk.append(float(t)); gk.append(float(g))
    pre = ev['amp_pre']; cap = ev['cap']
    first = ev['first']; hi = ev['hi']
    gcap = lambda i: min(1.0, cap / A[i]) if A[i] > 0 else 1.0
    hpull = lambda i: min(1.0, pre / A[i]) if A[i] > 0 else 1.0
    tc_ = ev['tc']
    if kind == 'rise' and P.get('hard'):                    # bracket oracle only: the whole rising voice at the birth gain during the window
        add(ts, 1.0); add(ts + 0.005, g0)
        if tc_ is not None:
            add(tc_, g0); add(tc_ + 0.010, 1.0)
        else:
            add(te, g0); add(te + 0.015, 1.0)
        tk = np.array(tk); gk = np.array(gk); o = np.argsort(tk, kind='stable'); tk, gk = tk[o], gk[o]
        keep = np.r_[True, np.diff(tk) > 1e-9]
        return tk[keep], gk[keep]
    if kind == 'birth':
        add(ts - HOPS, g0)                                  # amplitude ramps from the pad hop with the gain already applied (continuity)
        if tc_ is not None:
            add(tc_, g0); add(tc_ + 0.010, 1.0)
        else:
            add(te, g0); add(te + 0.015, 0.0)
            if ret == 'B':
                add(te + 0.040, 0.0); add(te + 0.050, 1.0)
    else:
        add(ts, 1.0); add(ts + 0.005, min(1.0, cap / max(np.interp(ts + 0.005, T, A), 1e-30)))
        stop = tc_ if tc_ is not None else te
        for i in range(first + 1, hi):
            if T[i] > ts + 0.005 and T[i] <= stop:
                add(T[i], gcap(i))
        if tc_ is not None:
            ic = ev['ic']
            add(tc_, gcap(ic) if ic >= first else 1.0); add(tc_ + 0.010, 1.0)
        else:
            gte = gcap(hi - 1)
            add(te, gte)
            at = lambda t: min(1.0, pre / max(np.interp(t, T, A), 1e-30))
            add(te + 0.015, at(te + 0.015))
            if ret == 'B':
                for i in range(hi, len(T)):
                    if T[i] > te + 0.015 and T[i] <= te + 0.040:
                        add(T[i], hpull(i))
                add(te + 0.040, at(te + 0.040)); add(te + 0.050, 1.0)
            else:
                for i in range(hi, len(T)):
                    if T[i] > te + 0.015:
                        add(T[i], hpull(i))
    tk = np.array(tk); gk = np.array(gk)
    o = np.argsort(tk, kind='stable'); tk, gk = tk[o], gk[o]
    keep = np.r_[True, np.diff(tk) > 1e-9]
    return tk[keep], gk[keep]


def plan_events(ctx, wins_td, W, P, mode, stats=False):
    """all events of one song.  wins_td: array of window start times t_d (audio = layer time); W window length (s).
    P: dict(g0=linear initial gain, cap_db=3, ret='B'|'A').  mode: 'evid' | 'oracle' | ('delay', L_s) | 'stats' (evidence flags, still gain via evidence).
    returns (events_by_voice, event_list); each event carries bookkeeping for the stage-0 stats"""
    by = {}; lst = []
    wins_td = np.asarray(wins_td, float)
    for vi, v in enumerate(ctx.voices):
        if not v['ok'] or len(v['T']) == 0:
            continue
        T, A = v['T'], v['A']
        wi = np.flatnonzero((wins_td + W > T[0]) & (wins_td <= T[-1]))
        for w in wi:
            td = wins_td[w]; te = td + W
            lo = int(np.searchsorted(T, td, 'left')); hi = int(np.searchsorted(T, te, 'left'))
            if hi <= lo:
                continue
            alive = lo + np.flatnonzero(A[lo:hi] > 0)
            if not len(alive):
                continue
            pre_i = lo - 1
            amp_pre = float(A[pre_i]) if pre_i >= 0 else 0.0
            runmax = float(A[:pre_i + 1].max()) if pre_i >= 0 else 0.0
            birth = (pre_i < 0) or amp_pre <= 0 or amp_pre < 0.01 * runmax
            cap = amp_pre * 10 ** (P['cap_db'] / 20) if not birth else None
            if birth:
                first = int(alive[0])
            else:
                aff = lo + np.flatnonzero(A[lo:hi] > cap)
                if not len(aff):
                    continue
                first = int(aff[0])
            ev = dict(vi=vi, w=int(w), td=float(td), te=float(te), kind='birth' if birth else 'rise', first=first, lo=lo, hi=hi, ts=float(T[first]),
                      amp_pre=amp_pre, cap=cap, tc=None, ic=None, cons=None, anyk=False, endk=False, nk=0)
            # evidence over hops first..hi-1
            ctx.k_arrays(v)
            fl = []
            for i in range(first, hi):
                k1, k2, k3 = conf_flags(ctx, v, i)
                fl.append((k1, k2, k3, (int(k1) + int(k2) + int(k3)) >= 2))
            ev['flags'] = fl
            c = [f[3] for f in fl]
            ev['anyk'] = bool(any(c)); ev['endk'] = bool(c[-1])
            cons = None
            for j in range(1, len(c)):
                if c[j - 1] and c[j]:
                    cons = first + j; break
            ev['cons'] = cons
            if mode in ('evid', 'stats'):
                if cons is not None:
                    ev['ic'] = cons; ev['tc'] = float(T[cons])
            elif isinstance(mode, tuple) and mode[0] == 'delay':
                tcv = float(T[first]) + mode[1]
                if tcv < te:
                    ev['tc'] = tcv; ev['ic'] = int(np.searchsorted(T, tcv, 'right') - 1)
            elif mode == 'oracle':
                pass
            ev['tk'], ev['gk'] = build_knots(ev, v, P, te)
            by.setdefault(vi, []).append(ev); lst.append(ev)
    return by, lst


def params(gain_db=-12.0, cap_db=3.0, ret='B', hard=False):
    return dict(g0=10 ** (gain_db / 20), cap_db=cap_db, ret=ret, hard=hard)


# ------------------------------------------------------------------------------------------ co-hit attack, helpers
def cohit_notes(ctx, name=None):
    """returns (starts of bass-MIDI notes inside the excerpt, mask of 'co-hit' notes (some H hit within 30 ms))"""
    rf = ctx.rf
    s = np.sort(np.asarray(rf['ss'], float))
    s = s[(s >= 0.5) & (s <= ctx.dur - 0.1)]
    on, pit = drum_hits(ctx.key)
    hh = np.sort(on[np.isin(pit, HSET)])
    if len(hh) and len(s):
        j = np.clip(np.searchsorted(hh, s), 1, len(hh) - 1) if len(hh) > 1 else np.zeros(len(s), int)
        near = np.minimum(np.abs(hh[np.clip(j, 0, len(hh) - 1)] - s), np.abs(hh[np.clip(j - 1, 0, len(hh) - 1)] - s))
        co = near <= 0.030
    else:
        co = np.zeros(len(s), bool)
    return s, co, hh


def note_energy(yr, s, dur_s=0.060):
    i0 = np.rint(s * FSC).astype(int); i1 = np.rint((s + dur_s) * FSC).astype(int)
    c = np.concatenate([[0.0], np.cumsum(yr ** 2)])
    return c[np.clip(i1, 0, len(yr))] - c[np.clip(i0, 0, len(yr))]
