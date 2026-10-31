"""Plan16 T library: stems/mix spectra, MIDI per stem, per-hop note lists, (a)-(e) classification (readings: CHOICES.md)."""
import sys, os, re, math
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/T')
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import dcommon as DC
from dcommon import *
import tmeta

FS3 = 3000.0
NFFT = 4096
DF = FS3 / NFFT
FMAXB = 1000.0
NB = int(FMAXB / DF) + 2
FRAME_S = 0.01
HOPF = 30
M_RULE_B = [2, 3, 4, 5, 6, 7, 8, 0.5]
M_REL = [1, 2, 3, 4, 5, 6, 7, 8, 0.5]              # pitch relation set for (c)
M_ALL = [1, 2, 3, 4, 5, 6, 7, 8, 0.5, 1 / 3, 0.25]  # coverage table (last two informational)
CATS = ['a', 'b', 'c', 'd', 'e']
FULL = tmeta.FULL


def guard(p):
    assert not re.search(r'slakh2100/(validation|test)(/|$)', str(p).replace('\\', '/')), 'forbidden path'


def load3k(path, secs=31.0):
    guard(path)
    info = sf.info(str(path)); fs = info.samplerate
    x, _ = sf.read(str(path), frames=int(secs * fs), always_2d=True, dtype='float64')
    x = x.mean(1)
    g = math.gcd(fs, 3000)
    y = resample_poly(x, 3000 // g, fs // g)
    return y[:int(secs * 3000)], fs


def stft_db(x, N=768):
    nfr = int(30.6 / FRAME_S) + 1
    pad = N // 2
    xp = np.concatenate([np.zeros(pad), x, np.zeros(N + HOPF * nfr)])
    win = np.hanning(N + 1)[:-1]
    out = np.empty((nfr, NB), np.float32)
    idx = np.arange(N)
    for m0 in range(0, nfr, 256):
        m1 = min(nfr, m0 + 256)
        fr = np.stack([xp[m * HOPF: m * HOPF + N] for m in range(m0, m1)]) * win
        out[m0:m1] = 20 * np.log10(np.abs(np.fft.rfft(fr, NFFT, axis=1))[:, :NB] + 1e-12)
    return out


def bins_of(f, cents=50.0):
    lo = int(math.ceil(f * 2 ** (-cents / 1200) / DF)); hi = int(math.floor(f * 2 ** (cents / 1200) / DF))
    if hi < lo:
        lo = hi = int(round(f / DF))
    return max(lo, 1), min(hi, NB - 2)


def bandmax(Srow, f):
    lo, hi = bins_of(f)
    return float(Srow[lo:hi + 1].max())


# ------------------------------------------------------------------------------------ engine-recipe peaks (copied unchanged from diag16/q4.py src_peaks/evid; q4 cannot be imported)
Q_N, Q_NFFT = 384, 2048
Q_BIN = 3000.0 / Q_NFFT
Q_WIN = np.hanning(Q_N + 1)[:-1]


def q_offset(a, b, c):
    den = a - 2 * b + c
    return float(np.clip(0.5 * (a - c) / den, -1, 1)) if abs(den) > 1e-12 else 0.0


def src_peaks(sm):
    res = [[], []]
    for band in range(2):
        lb = int(np.ceil((140 if band else 20) / Q_BIN)); hb = int(np.floor((620 if band else 200) / Q_BIN))
        maxmag = sm[lb:hb + 1].max()
        for b in range(lb + 1, hb):
            v = sm[b]
            if not (v >= sm[b - 1] and v > sm[b + 1]):
                continue
            med = np.median(sm[np.clip(np.arange(b - 27, b + 28), lb, hb)])
            rel = 20 * np.log10(v / maxmag + 1e-30); over = 20 * np.log10(v / (med + 1e-20))
            f = (b + q_offset(np.log(sm[b - 1] + 1e-30), np.log(v + 1e-30), np.log(sm[b + 1] + 1e-30))) * Q_BIN
            floor_db = -60. if band else -50.
            ok = rel >= floor_db and v >= (med + 1e-20) * np.sqrt(10.)
            if ok:
                res[band].append((f, rel, over))
    return res


def q_evid(res, f):
    tol = max(4.0, .03 * f)
    return any(abs(pf - f) <= tol for band in range(2) for (pf, _, _) in res[band])


# ------------------------------------------------------------------------------------ per-song context
class Ctx:
    def __init__(self, key, tc, N=768):
        self.key = key; self.tc = np.asarray(tc); self.nh = len(tc)
        meta = tmeta.stems_meta(key)
        self.meta = meta
        self.sids = [s for s in sorted(meta) if meta[s]['disk'] and meta[s]['rendered']]
        self.nd = [s for s in self.sids if not meta[s]['drum']]                    # non-drum stems with audio
        self.notes = {}
        for s in self.sids:
            p = X.SLAKH_MIDI / key / 'MIDI' / f'{s}.mid'; guard(p)
            nl = X.read_midi(p) if p.exists() else []
            a = np.array(sorted(nl), float).reshape(-1, 3)
            self.notes[s] = dict(s=a[:, 0], e=a[:, 1], p=a[:, 2], f0=440 * 2 ** ((a[:, 2] - 69) / 12))
        self.S = {}
        for s in self.sids:
            x, fs = load3k(f'{FULL}/{key}/stems/{s}.flac'); self.S[s] = stft_db(x, N)
        xm, _ = load3k(X.SLAKH / key / 'mix.flac')
        self.xm = xm; self.Smix = stft_db(xm, N)
        self._qcache = {}
        self.N = N

    def build_lists(self, slack=0.0, tailwin=1.0):
        tc = self.tc
        snd = [[] for _ in range(self.nh)]; tail = [[] for _ in range(self.nh)]
        for si, s in enumerate(self.nd):
            n = self.notes[s]
            for j in range(len(n['s'])):
                h0 = np.searchsorted(tc, n['s'][j] - slack, 'left'); h1 = np.searchsorted(tc, n['e'][j] + slack, 'left')
                for h in range(h0, h1):
                    snd[h].append((si, n['f0'][j], j))
                t0 = np.searchsorted(tc, n['e'][j], 'right'); t1 = np.searchsorted(tc, n['e'][j] + tailwin, 'right')
                for h in range(t0, t1):
                    tail[h].append((si, n['f0'][j], j))
        return snd, tail

    def mix_excess(self, t, f):
        m = int(round(t / FRAME_S)); row = self.Smix[m]
        lo, hi = bins_of(f)
        b = lo + int(np.argmax(row[lo:hi + 1]))
        if b - 1 < 0 or b + 1 >= NB or not (row[b] >= row[b - 1] and row[b] >= row[b + 1]):
            return -99.0
        W = max(30.0, 0.5 * f); fb = np.arange(NB) * DF
        sel = (np.abs(fb - f) <= W) & (np.abs(fb - b * DF) >= 10.0) & (fb >= DF)
        return float(row[b] - np.median(row[sel]))

    def mix_nearest(self, t, f, span=300.0):
        """cents from f to the nearest mix local maximum (excess >= 6 dB, same median rule) within +-span cent; nan if none"""
        m = int(round(t / FRAME_S)); row = self.Smix[m]
        lo, hi = bins_of(f, span)
        fb = np.arange(NB) * DF; W = max(30.0, 0.5 * f)
        best = np.nan
        for b in range(max(lo, 1), min(hi, NB - 2) + 1):
            if row[b] >= row[b - 1] and row[b] >= row[b + 1]:
                sel = (np.abs(fb - f) <= W) & (np.abs(fb - b * DF) >= 10.0) & (fb >= DF)
                if row[b] - np.median(row[sel]) >= 6.0:
                    c = abs(1200 * math.log2(b * DF / f))
                    best = c if not np.isfinite(best) else min(best, c)
        return float(best)

    def eng_peak(self, h, t, f):
        if h not in self._qcache:
            c = int(round(t * FS3))
            fr = np.zeros(Q_N)
            a0 = c - Q_N // 2
            lo, hi = max(a0, 0), min(a0 + Q_N, len(self.xm))
            fr[lo - a0: hi - a0] = self.xm[lo:hi]
            sm = np.abs(np.fft.rfft(fr * Q_WIN, Q_NFFT))
            self._qcache[h] = src_peaks(sm)
        return q_evid(self._qcache[h], f)

    def classify(self, h, t, f, snd, tail, P):
        """returns dict(cat, k, stems, + diagnostics)"""
        m = int(round(t / FRAME_S))
        out = dict(cat='e', k=None, stems=[], hit_k={})
        # (a)/(b) and coverage by every ratio
        cov = {}
        for (si, f0, j) in snd[h]:
            for mm in M_ALL:
                if abs(cents(f, mm * f0)) <= 50.0:
                    cov.setdefault(mm, set()).add(si)
        out['hit_k'] = {mm: sorted(v) for mm, v in cov.items()}
        if 1 in cov:
            out['cat'] = 'a'; out['stems'] = sorted(cov[1]); return self._diag(out, h, t, f, m, P)
        for mm in M_RULE_B:
            if mm in cov:
                out['cat'] = 'b'; out['k'] = mm; out['stems'] = sorted(cov[mm]); return self._diag(out, h, t, f, m, P)
        # (c) tail
        cst = set()
        for (si, f0, j) in tail[h]:
            if not any(abs(cents(f, mm * f0)) <= 50.0 for mm in M_REL):
                continue
            s = self.nd[si]; n = self.notes[s]
            ms, me = int(round(n['s'][j] / FRAME_S)), int(round(n['e'][j] / FRAME_S))
            S = self.S[s]
            if P['tailref'] == 'f':
                lo, hi = bins_of(f)
            else:
                lo, hi = bins_of(f0)
            ref = float(S[ms:me + 1, lo:hi + 1].max())
            lv = bandmax(S[m], f)
            if lv >= ref - 30.0:
                cst.add(si)
        if cst:
            out['cat'] = 'c'; out['stems'] = sorted(cst); return self._diag(out, h, t, f, m, P)
        ex = self.mix_excess(t, f)
        out['excess'] = ex
        if ex >= P['mixthr']:
            out['cat'] = 'd'
        return self._diag(out, h, t, f, m, P)

    def _diag(self, out, h, t, f, m, P):
        if 'excess' not in out:
            out['excess'] = self.mix_excess(t, f)
        lv = {s: bandmax(self.S[s][m], f) for s in self.sids}
        out['dom'] = max(lv, key=lv.get)
        out['dom_db'] = lv[out['dom']]
        out['nearpk'] = self.mix_nearest(t, f)
        out['eng'] = bool(self.eng_peak(h, t, f)) if P.get('eng', True) else False
        return out
