"""Data access for the stage-0 lookahead experiment (LA).
Streams (bh = bhRing_ 'selected_h', det = detailRing52_ 'band_delayed191') and the core-v1.5 voice trace come from the candidate lib capture
(config A; section 4.3: the front end is unchanged, V0 proves the tracker state identical), the P1 tracker tracks from the P1 REFERENCE build's
harmonic trace (all tracks with state > 0).  Everything is cached under la0/cache.  Slakh TRAIN only."""
import os, sys, re
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
for p in ('/home/ksysh/r3-work/tools/pvb-harness', '/home/ksysh/r3-work/tools/pvb-harness/study', '/home/ksysh/r3a-dev/diag16', '/home/ksysh/r3a-dev/verify_core'):
    if p not in sys.path:
        sys.path.insert(0, p)
import research_core_xcheck as X
import common16 as C
import proxy16 as PX

FS = 48000
HOME = Path.home()
LA0 = HOME / 'r3a-dev/la0'
CACHE = LA0 / 'cache'; CACHE.mkdir(exist_ok=True)
HOP = 16                       # core samples per tracker hop
HOP_S = HOP / 3000.0
FSC = 3000.0                   # core rate
STREAM_DELAY_S = 0.00104       # phase delay of the 3 kHz streams at 100 Hz relative to the (j-191)/3000+1359/48000 map, measured on bare100 (t_delay.py)
TRAIN = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012']
EVAL = ['Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']


def guard(p):
    assert not re.search(r'slakh2100/(validation|test)(/|$)', str(p).replace('\\', '/')), 'forbidden path'


def stream_time(j):
    """input time (s) of the 3 kHz stream sample with index j (ring axis: slot j <-> input time j-191 core samples, section 3)"""
    return (np.asarray(j, float) - 191.0) / FSC + 1359.0 / FS - STREAM_DELAY_S


def stream_index(t):
    return (np.asarray(t, float) + STREAM_DELAY_S - 1359.0 / FS) * FSC + 191.0


# ---------------------------------------------------------------- audio for the keys
def audio(key):
    if key in TRAIN + EVAL:
        p = X.SLAKH / key / 'mix.flac'; guard(p)
        return X.read_excerpt(p, 0.0, 30.0)
    if key == 'bare100':
        return PX.sig_bare()[0]
    if key == 'step25':
        return PX.sig_step_line(25.0)[0]
    if key == 'bkp_0':
        return PX.sig_bass_kick_pink(0.0)[0]
    if key == 'steady8':
        return PX.sig_steady(8.0, 10.0)[0]
    if key == 't60_36_48':
        p = X.SLAKH / 'Track00060' / 'mix.flac'; guard(p)
        return X.read_excerpt(p, 36.0, 12.0)
    if key == 'bass9':
        return X.bass_sig(9.0)[0]
    if key == 'bass8c':
        return X.bass_sig(8.0)[0]
    if key == 'pink10':
        return X.pink_gf(10.0, rms=10 ** (-30 / 20))
    if key == 'logoff_37_49':
        return X.read_excerpt(X.LOGOFF, 37.0, 12.0)
    raise KeyError(key)


def _stereo(x):
    x = np.asarray(x, np.float32)
    return np.stack([x, x], 1) if x.ndim == 1 else x


_ctx = None


def streams(key):
    """dict(trace, bh, det): cached diag16 file if it exists, else rendered once and cached in la0/cache (same recipe as diag16/streams16.get)"""
    p16 = C.CACHE / f's_{key}.npz'
    if p16.exists():
        z = np.load(p16); return dict(trace=z['trace'], bh=z['bh'], det=z['det'])
    p = CACHE / f's_{key}.npz'
    if p.exists():
        z = np.load(p); return dict(trace=z['trace'], bh=z['bh'], det=z['det'])
    import research_core_metrics as M
    from vb_quality.stage_capture import INDEX as SI
    global _ctx
    ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
    x2 = _stereo(audio(key))
    r = ctx.render(key, x2, 0.0, voice=True, stage=True)
    st = r['stage']
    core = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
    bh = np.zeros(core.max() + 1); det = np.zeros_like(bh)
    bh[core] = st[:, SI['selected_h']]; det[core] = st[:, SI['band_delayed191']]
    np.savez_compressed(p, trace=np.asarray(r['voice'], float), bh=bh, det=det)
    return dict(trace=np.asarray(r['voice'], float), bh=bh, det=det)


def p1_trace(key):
    """(tc1 (hops,), ts (hops, 12, 56)) from the P1 reference build, harmonic diagnostic capture"""
    if key in TRAIN + EVAL:
        return C.get_p1(key)
    p = CACHE / f'p1_{key}.npz'
    if p.exists():
        z = np.load(p); return z['tc1'], z['ts']
    lib = X.open_lib(X.REF)
    tc1, ts = X.p1_harmonic(lib, _stereo(audio(key)))
    np.savez_compressed(p, tc1=tc1, ts=ts)
    return tc1, ts


class Sig:
    """everything about one signal"""
    def __init__(self, key):
        self.key = key
        s = streams(key)
        self.bh, self.det, self.trace = s['bh'], s['det'], s['trace']
        self.tc1, self.ts = p1_trace(key)
        d, hop, tc = X.hops_of(self.trace)
        self.core_d, self.core_hop, self.core_tc = d, hop, tc
        self.core_raw = np.asarray(self.trace).reshape(-1, 8, 22)
        n = min(len(tc), len(self.tc1))
        # the two hop grids are the same tracker grid (checked)
        assert np.allclose(tc[:n], self.tc1[:n], atol=1e-6), (key, tc[:3], self.tc1[:3])
        self.nhop = n

    def stream(self, name):
        return self.bh if name == 'bh' else self.det

    def j_of(self, t):
        return stream_index(t)
