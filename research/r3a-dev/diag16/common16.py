"""Shared helpers for the diag16 measurements (Resultant core, vb_algo 15). Measurement only.
Reuses research_core_xcheck (X): render, hop_time, read_midi, read_excerpt, bass_stems_and_notes, p1_harmonic."""
import json, os, re
from pathlib import Path
import numpy as np
import research_core_xcheck as X

HOME = Path.home()
D16 = HOME / 'r3a-dev/diag16'
CACHE = D16 / 'cache'; CACHE.mkdir(exist_ok=True)
FS = X.FS
_s = json.load(open(HOME / 'r3a-dev/core_results/verify_A/results.json'))['metrics']['V6']
TRACKS = [t['name'] for t in _s['per_track']]
TP = {t['name']: t['tp'] for t in _s['per_track']}
HOPMS = 16 / 3000 * 1000


def _guard(p):
    assert not re.search(r'slakh2100/(validation|test)(/|$)', str(p).replace('\\', '/')), 'forbidden path'


def ref(name):
    """Reference material for one track: bass notes (+tp), all-MIDI notes (drums included), drum onsets, kick onsets."""
    _guard(X.SLAKH / name)
    bz, bnotes = X.bass_stems_and_notes(name)
    mdir = X.SLAKH_MIDI / name
    meta = (mdir / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    drum_ids = {parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'is_drum:\s*true', parts[i + 1])}
    allnotes, nodrum, drums = [], [], []
    for m in sorted((mdir / 'MIDI').glob('*.mid')):
        nl = X.read_midi(m)
        allnotes += nl
        if m.stem in drum_ids:
            drums += nl
        else:
            nodrum += nl
    drums = sorted(drums)
    don = np.array([n[0] for n in drums]); dp = np.array([n[2] for n in drums])
    kick = don[(dp == 35) | (dp == 36)] if len(don) else np.array([])
    A = lambda nl, k: np.array([n[k] for n in nl], float)
    return dict(name=name, tp=TP[name], bz=bz,
                ps=A(bnotes, 2), ss=A(bnotes, 0), es=A(bnotes, 1),
                ap=A(allnotes, 2), as_=A(allnotes, 0), ae=A(allnotes, 1),
                nd_p=A(nodrum, 2), nd_s=A(nodrum, 0), nd_e=A(nodrum, 1),
                drum_on=np.unique(np.round(don, 4)), kick_on=np.unique(np.round(kick, 4)), drum_ids=sorted(drum_ids),
                drum_pitch_counts={int(p): int((dp == p).sum()) for p in np.unique(dp)} if len(dp) else {})


def targets_at(rf, t, variant='a'):
    """frequencies (0.5,1,2,3 x every sounding MIDI note) at time t, the V6b definition (variant 'c' = drum MIDI excluded)."""
    if variant == 'a':
        pa = np.r_[rf['ap'][(rf['as_'] <= t) & (t < rf['ae'])], rf['ps'][(rf['ss'] <= t) & (t < rf['es'])] + rf['tp']]
    else:
        pa = np.r_[rf['nd_p'][(rf['nd_s'] <= t) & (t < rf['nd_e'])], rf['ps'][(rf['ss'] <= t) & (t < rf['es'])] + rf['tp']]
    fn = 440 * 2 ** ((pa - 69) / 12)
    return fn


def cents(f, g):
    return np.abs(1200 * np.log2(np.maximum(f, 1e-9) / g))


def get_core(name, cfg='A'):
    p = CACHE / f'{name}_core{cfg}.npz'
    if p.exists():
        z = np.load(p); return z['trace']
    _guard(X.SLAKH / name)
    x = X.read_excerpt(X.SLAKH / name / 'mix.flac', 0.0, 30.0)
    cand = X.open_lib(X.CAND)
    r = X.render(cand, x, 15, 0.0, out_db=-5.0, cfg=X.CFG[cfg], trace=True)
    np.savez_compressed(p, trace=r['trace'])
    return r['trace']


def get_p1(name):
    p = CACHE / f'{name}_p1.npz'
    if p.exists():
        z = np.load(p); return z['tc1'], z['ts']
    x = X.read_excerpt(X.SLAKH / name / 'mix.flac', 0.0, 30.0)
    ref_ = X.open_lib(X.REF)
    tc1, ts = X.p1_harmonic(ref_, x)
    np.savez_compressed(p, tc1=tc1, ts=ts)
    return tc1, ts


def wquant(v, w, qs=(.1, .25, .5, .75, .9)):
    """weighted quantiles"""
    v = np.asarray(v, float); w = np.asarray(w, float)
    m = np.isfinite(v) & (w > 0)
    if not m.any():
        return [np.nan] * len(qs)
    v, w = v[m], w[m]
    o = np.argsort(v); v, w = v[o], w[o]
    c = (np.cumsum(w) - 0.5 * w) / w.sum()
    return [float(np.interp(q, c, v)) for q in qs]
