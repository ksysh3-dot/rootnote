"""Window data: voice-trace components for v15 / v16b, harmonic-trace (P1/v15) gain and tracks, measured layer band powers."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12model import *

_cache = {}


def load(sk, eng):
    key = (sk, eng)
    if key not in _cache:
        d = {}
        d['layer'] = np.load(TMP / f'{sk}_{eng}_layer.npy').astype(np.float64)
        tf = TMP / f'{sk}_{eng}_trace.npz'
        d['tr'] = {k: v.astype(np.float64) for k, v in np.load(tf).items()} if tf.exists() else None
        h = np.load(TMP / f'{sk}_{eng}_harm.npz')['rows']
        L = h[:, 3:7].astype(np.int64)
        d['hci'] = L[:, 0] + (L[:, 1] << 16) + (L[:, 2] << 32) + (L[:, 3] << 48)
        d['h'] = h
        _cache[key] = d
    return _cache[key]


_bands = {}


def band_signal(sk, eng, which):
    key = (sk, eng, which)
    if key not in _bands:
        sos = SOS_LO if which == 'lo' else SOS_MID
        _bands[key] = sosfiltfilt(sos, load(sk, eng)['layer'])
    return _bands[key]


def hop_power(sig, tstart):
    """mean square of sig over the 256 output samples that hop span starting at input time tstart (s)"""
    s0 = np.round(np.asarray(tstart) * FS).astype(int)
    c = np.concatenate([[0.0], np.cumsum(sig ** 2)])
    s1 = np.minimum(s0 + 256, len(sig)); s0 = np.clip(s0, 0, len(sig))
    return (c[s1] - c[s0]) / 256.0


def comps(sk, eng, t0, t1, gain=False):
    """Per-hop, per-slot, per-k component table for the hops whose output span starts inside [t0, t1).
    Returns dict with arrays: hop(H,), tstart(H,), vid(H,8), st(H,8), f(H,8), A(H,8), a(7,H,8) (incl. gain), g(H,)"""
    d = load(sk, eng); tr = d['tr']
    hop = tr['hop'][:, 0]
    ts = CA.hop_time(hop)[1]
    idx = np.where((ts >= t0) & (ts < t1))[0]
    st = tr['state'][idx]; fo = tr['f_osc'][idx]
    base = tr['A'][idx] * tr['c'][idx] * tr['sigma'][idx]
    a = amplitudes(fo, np.where(st >= 1, base, 0.0), True, 1.0)
    # envelope/level gain of the harmonic header (index 17), joined on the core index
    pos = {int(c): i for i, c in enumerate(d['hci'])}
    g = np.array([d['h'][pos[int(h)], 17] if int(h) in pos else np.nan for h in hop[idx]])
    if gain:
        a = a * np.nan_to_num(g, nan=1.0)[None, :, None]
    return dict(hop=hop[idx], ts=ts[idx], vid=tr['voice'][idx], trk=tr['track'][idx], st=st, f=fo, ft=tr['f_track'][idx],
                A=tr['A'][idx], c=tr['c'][idx], sg=tr['sigma'][idx], coast=tr['coasting'][idx], a=a, g=g, idx=idx)


def model_band_power(cp, which):
    sos = SOS_LO if which == 'lo' else SOS_MID
    P = np.zeros(cp['f'].shape)
    for kk in range(2, 9):
        fk = kk * cp['f']
        P += np.where(cp['a'][kk - 2] > 0, band_pow(cp['a'][kk - 2], np.where(fk > 0, fk, 100.0), sos), 0.0)
    return P      # (H, 8)


def db(p):
    return 10 * np.log10(np.maximum(p, 1e-30))
