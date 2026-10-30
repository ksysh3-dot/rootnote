"""What actually reaches the speaker: per-harmonic level change of the APP OUTPUT (layer on vs layer off, same chain,
defaults) at k f0 for steady-f0 frames (128 ms, reference f0 spread < 1.5 %), f0 bands 55-80 / 80-100 / 100-125 /
125-150 Hz. Amplitude at k f0 by a least-squares cos/sin fit over the frame (so a phase-locked layer partial adds
coherently, unlike a power sum). Models: P1 and R4 variants via host stage flags (StageCapture attached) and
pvb_set_r4_research. Also the phone-weighted (S26 Ultra speaker curve) sum over k = 1..6.
Usage: coherent_gain.py <root> <lib> --reference midi|yin [--midi-transpose auto] [--crop s0,dur] [--skip RE]
       [--limit N] [--models 'name:stage[:hold,floor,tau];...'] [--out json]"""
import argparse, ctypes as Cty, json, re, sys
from pathlib import Path
import numpy as np
from scipy.signal import sosfiltfilt
import research_gt_bass as G
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
sys.path.insert(0, 'study'); import phone_model as PM
p = argparse.ArgumentParser(); p.add_argument('root', type=Path); p.add_argument('lib')
p.add_argument('--reference', default='yin'); p.add_argument('--midi-transpose', default='0'); p.add_argument('--crop', default='')
p.add_argument('--skip', default=''); p.add_argument('--limit', type=int, default=0); p.add_argument('--out', type=Path)
p.add_argument('--models', default='p1:0;r4c:16777216;p8:50331648:8,0,30')
a = p.parse_args(); FS, CORE = 48000, 3000; lib = RP.api(a.lib)
lib.pvb_set_r4_research.argtypes = [Cty.c_void_p, Cty.c_int, Cty.c_double, Cty.c_double]
MODELS = [m.split(':') for m in a.models.split(';')]
BANDS = ((55, 80), (80, 100), (100, 125), (125, 150)); K = np.arange(1, 7)
def run(x, stage=0, r4=None, on=1):
    e = T.Engine(lib, FS, vb_on=on, vb_algo=6)
    if r4: assert lib.pvb_set_r4_research(e.h, *r4) == 1
    cap = StageCapture(lib, e.h, stage, int(len(x) / FS * 3000) + 16) if stage else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:].astype(float).mean(axis=1)
N = int(.128 * FS); HOP = N // 2; tw = np.arange(N) / FS
acc = {m[0]: {b: [] for b in BANDS} for m in MODELS}; done = 0
for name, mix, bass, fs, midis, _ in G.items(a.root):
    if a.skip and re.search(a.skip, name): continue
    s0 = 0.
    if a.crop:
        s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs)); mix, bass = mix[sl], bass[sl]
        if len(bass) < 5 * fs: continue
    bz = sosfiltfilt(G.LP, G.to_rate(bass, fs, CORE))
    if a.reference == 'midi':
        if not midis: continue
        notes = [n for m in midis for n in G.midi_notes(m)]; tt = G.grid(len(bz))
        tr = G.midi_octave(tt, notes, s0, bz)[0] if a.midi_transpose == 'auto' else int(a.midi_transpose)
        if tr is None: continue
        f0 = G.midi_f0(tt, notes, s0, tr)
    else: tt, f0 = G.yin(bz)
    if np.sum(np.isfinite(f0)) < 20: continue
    x = G.to_rate(mix, fs, FS); x = (x if x.ndim == 2 and x.shape[1] == 2 else np.repeat(x.reshape(len(x), -1)[:, :1], 2, 1))
    x = np.clip(x, -1, 1).astype(np.float32)
    yoff = run(x, on=0)
    ys = {m[0]: run(x, int(m[1]), tuple(float(v) if i else int(v) for i, v in enumerate(m[2].split(','))) if len(m) > 2 else None) for m in MODELS}
    L = min(len(yoff), *(len(v) for v in ys.values()))
    for s in range(int(1.0 * FS), L - N, HOP):
        sel = (tt >= s / FS) & (tt <= (s + N) / FS); fs_ = f0[sel]; good = fs_[np.isfinite(fs_)]
        if len(good) < max(3, .8 * sel.sum()) or np.ptp(good) > .015 * np.median(good): continue
        fm = float(np.median(good)); b = next((q for q in BANDS if q[0] <= fm < q[1]), None)
        if b is None: continue
        A = np.column_stack([g(2 * np.pi * k * fm * tw) for k in K for g in (np.cos, np.sin)])
        amp = lambda y: np.hypot(*np.linalg.lstsq(A, y[s:s + N], rcond=None)[0].reshape(-1, 2).T)
        a0 = amp(yoff) + 1e-12; wdev = 10 ** (PM.speaker_db(K * fm) / 20)
        for m in MODELS:
            a1 = amp(ys[m[0]]) + 1e-12
            acc[m[0]][b].append(np.r_[20 * np.log10(a1 / a0), 10 * np.log10(np.sum((wdev * a1) ** 2) / np.sum((wdev * a0) ** 2))])
    done += 1; print('ITEM', done, name, flush=True)
    if a.limit and done >= a.limit: break
out = dict(items=done)
for m in MODELS:
    for b in BANDS:
        v = np.array(acc[m[0]][b])
        if not len(v): continue
        out[f'{m[0]} {b[0]}-{b[1]}'] = dict(frames=len(v), gain_db_k1_6=[round(float(q), 2) for q in np.median(v[:, :6], axis=0)],
                                             phone_weighted_gain_db=round(float(np.median(v[:, 6])), 2), phone_weighted_p90=round(float(np.percentile(v[:, 6], 90)), 2))
        print(m[0], b, json.dumps(out[f'{m[0]} {b[0]}-{b[1]}']), flush=True)
if a.out: a.out.write_text(json.dumps(out, indent=1))
