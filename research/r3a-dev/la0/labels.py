"""Right / wrong labels (V6b definition: a voice frequency is RIGHT iff within 50 cent of 0.5, 1, 2 or 3 x any sounding MIDI note of the song,
drum MIDI included, bass MIDI shifted by the octave tp) for songs, the T60 excerpt (song time = excerpt + 36 s) and the synthetic signals."""
import numpy as np
from data import C, X, HOP_S
import proxy16 as PX

_REF = {}


def song_ref(name):
    if name not in _REF:
        _REF[name] = C.ref(name)
    return _REF[name]


def fn_func(key):
    """sounding fundamentals at excerpt time t, or None when no ground truth exists (LOGOFF)"""
    if key.startswith('Track'):
        rf = song_ref(key)
        return lambda t: C.targets_at(rf, t, 'a')
    if key == 't60_36_48':
        rf = song_ref('Track00060')
        return lambda t: C.targets_at(rf, t + 36.0, 'a')
    if key == 'bare100':
        return lambda t: np.array([100.0]) if 0.5 <= t < 1.5 else np.zeros(0)
    if key == 'step25':
        def fs(t):
            i = int(t // PX.PER)
            if 0 <= i < len(PX.STEP_NOTES) and (t - i * PX.PER) < PX.STEP_DUR:
                return np.array([PX.STEP_NOTES[i]])
            return np.zeros(0)
        return fs
    if key in ('bass9', 'bass8c', 'bkp_0', 'steady8'):
        return lambda t: np.array([100.0])
    if key == 'pink10':
        return lambda t: np.zeros(0)
    return None


class Truth:
    def __init__(self, key, tc):
        self.fn_at = fn_func(key); self.tc = np.asarray(tc); self.cache = {}
        self.ok = self.fn_at is not None

    def tg(self, h):
        if h not in self.cache:
            fn = self.fn_at(float(self.tc[h]))
            self.cache[h] = np.sort(np.log2(np.outer(fn, [.5, 1, 2, 3]).ravel())) if len(fn) else np.zeros(0)
        return self.cache[h]

    def hop_of(self, t):
        return np.clip(np.rint((np.asarray(t) - self.tc[0]) / HOP_S).astype(int), 0, len(self.tc) - 1)

    def wrong(self, h, f):
        """bool array: True where the frequency is 'wrong' (hop index array h, frequency array f)"""
        h = np.asarray(h); f = np.asarray(f, float)
        out = np.ones(len(f), bool)
        if not len(f):
            return out
        order = np.argsort(h, kind='stable'); hs = h[order]
        cuts = np.flatnonzero(np.diff(hs)) + 1
        for seg in np.split(order, cuts):
            tg = self.tg(int(h[seg[0]]))
            if not len(tg):
                continue
            lf = np.log2(np.maximum(f[seg], 1e-9))
            i = np.searchsorted(tg, lf)
            lo = tg[np.clip(i - 1, 0, len(tg) - 1)]; hi = tg[np.clip(i, 0, len(tg) - 1)]
            out[seg] = np.minimum(np.abs(lf - lo), np.abs(lf - hi)) * 1200 > 50
        return out
