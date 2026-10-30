"""R3-c feasibility (development sets only): would deciding the octave per note / segment instead of per frame help?
Per 10 ms frame (reference f0 f): P1 strong tracks b (lowest = T) and R3-a strong tracks c; R3-a 'halves' the frame
when its lowest track sits near T/2. Two counterfactual outcomes per frame: tracked if halved (R3-a's own result when
it halved; else b with T replaced by T/2) and tracked if not halved (P1's b). A segment rule then makes one decision
per segment: halve all frames when the share of R3-a halved frames in it is >= X, else none. Segments: (a) P1 track
runs (same lowest-track id in consecutive frames; usable in the engine), (b) MIDI notes (oracle, Slakh only).
Reports tracked share for P1, R3-a, segment rules, and the per-frame oracle, for all frames and f >= 82 Hz.
Usage: note_level.py <root> <lib> --reference midi|yin [--midi-transpose -12] [--crop s0,dur] [--out json]"""
import argparse, json
from pathlib import Path
import numpy as np
from scipy.signal import sosfiltfilt
import research_gt_bass as G
import research_p1plus as P
import test_harmonic_continuity as H

p = argparse.ArgumentParser(); p.add_argument('root', type=Path); p.add_argument('lib', type=Path)
p.add_argument('--reference', default='yin'); p.add_argument('--midi-transpose', type=int, default=0)
p.add_argument('--crop', default=''); p.add_argument('--out', type=Path)
a = p.parse_args(); lib = P.api(a.lib.resolve())
def near(fl, f):
    if not len(fl): return False
    return bool(np.min(1200 * np.abs(np.log2(np.asarray(fl) / f))) <= 50)
def strong(tr, tin, t):
    k = min(max(np.searchsorted(tin, t), 0), len(tin) - 1)
    fr, am, st, ids = tr[k, :, 2], tr[k, :, 4], tr[k, :, 1], tr[k, :, 0]; live = (st > 0) & (st < 5) & (am > 0)
    if not live.any(): return np.array([]), -1
    live &= am >= .1 * am[live].max(); i = np.where(live)[0]; j = i[np.argmin(fr[i])]
    return fr[live], int(ids[j])
XS = (0.2, 0.35, 0.5, 0.65, 0.8)
acc = {k: np.zeros(2) for k in ['frames', 'p1', 'r3a', 'oracle'] + [f'run{x}' for x in XS] + [f'note{x}' for x in XS]}
hi = {k: np.zeros(2) for k in acc}
per = []
for name, mix, bass, fs, midis, _ in G.items(a.root):
    s0 = 0.
    if a.crop:
        s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs)); mix, bass = mix[sl], bass[sl]
        if len(bass) < 5 * fs: continue
    bz = sosfiltfilt(G.LP, G.to_rate(bass, fs, G.CORE))
    notes = []
    if a.reference == 'midi':
        if not midis: continue
        notes = [n for m in midis for n in G.midi_notes(m)]; tt = G.grid(len(bz)); f0 = G.midi_f0(tt, notes, s0, a.midi_transpose)
    else: tt, f0 = G.yin(bz)
    if np.sum(np.isfinite(f0)) < 20: continue
    mix48 = G.to_rate(mix, fs, G.FS).astype(np.float32); mix48 = mix48 if mix48.shape[1] == 2 else np.repeat(mix48, 2, axis=1)
    tk = {}
    for m in ('p1', 'p1_r3a'):
        fl, st = G.MODELS[m]; r = P.render(lib, mix48, G.FS, fl, stage_flags=st)
        tk[m] = (H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / G.CORE)
    t_end = len(bz) / G.CORE - .2
    R = []                                          # t, f, halved, ok_halve, ok_keep, run id, note id
    for t, f in zip(tt, f0):
        if not (1.0 <= t <= t_end) or not np.isfinite(f): continue
        b, rid = strong(*tk['p1'], t); c, _ = strong(*tk['p1_r3a'], t)
        if not len(b): R.append((t, f, 0, 0, 0, -1, -1)); continue
        T = b.min(); h = len(c) and near([c.min()], T / 2)
        ok_h = near(c, f) if h else near(np.r_[b[b != T], T / 2], f)
        nid = -1
        if notes:
            for k, n in enumerate(notes):
                if n[0] - s0 <= t < n[1] - s0: nid = k; break
        R.append((t, f, int(bool(h)), int(ok_h), int(near(b, f)), rid, nid))
    R = np.array(R, float)
    if not len(R): continue
    def tally(dst, mask, decide):
        ok = np.where(decide, R[:, 3], R[:, 4]); dst += [ok[mask].sum(), mask.sum()]
    for dst, mask in ((acc, np.ones(len(R), bool)), (hi, R[:, 1] >= 82)):
        dst['frames'] += [mask.sum(), mask.sum()]
        tally(dst['p1'], mask, np.zeros(len(R), bool)); tally(dst['r3a'], mask, R[:, 2] > 0)
        dst['oracle'] += [np.maximum(R[:, 3], R[:, 4])[mask].sum(), mask.sum()]
        for col, key in ((5, 'run'), (6, 'note')):
            if key == 'note' and not notes: continue
            seg = R[:, col].copy()
            if key == 'run':                       # consecutive frames with the same lowest-track id form one run
                brk = np.r_[True, (seg[1:] != seg[:-1]) | (np.diff(R[:, 0]) > .05)]; seg = np.cumsum(brk) * (R[:, 5] >= 0) - (R[:, 5] < 0)
            share = np.zeros(len(R))
            for s in np.unique(seg):
                m = seg == s; share[m] = R[m, 2].mean() if s >= 0 else 0
            for x in XS:
                d = np.where(seg >= 0, share >= x, R[:, 2] > 0); tally(dst[f'{key}{x}'], mask, d)
    per.append(name); print('ITEM', len(per), name, flush=True)
fmt = lambda d: {k: (round(100 * v[0] / v[1], 2) if v[1] else None) for k, v in d.items() if k != 'frames'}
res = dict(items=len(per), frames=int(acc['frames'][0]), hi_frames=int(hi['frames'][0]), all=fmt(acc), hi=fmt(hi))
print(json.dumps(res, indent=1))
if a.out: a.out.write_text(json.dumps(res, indent=1))
