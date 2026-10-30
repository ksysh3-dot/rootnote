"""P1 anatomy for bass f0 80-150 Hz (development sets only). Over 128 ms frames with a steady reference f0 (spread
< 1.5 %), split 55-80 (contrast) / 80-100 / 100-125 / 125-150 Hz:
- tracked: a strong P1 track within 50 cents of f0 (frame centre).
- layer harmonic profile: layer energy within max(3 Hz, 1.5 %) of k f0, k = 1..8, as a share of the layer's 120-1450 Hz
  energy; 'bass_share' = k 2..8 sum (as research_gt_bass.py).
- the same for the layer rendered from the bass stem alone: the drop from bass-alone to mix share is layer energy
  driven by the other instruments.
- native harmonics: the mix's own level at k f0 (k = 1..8, dB re the mix's 120-1450 Hz energy in the frame) and the
  layer-to-native ratio there; 'added_db' = 10 log10(1 + L_k / N_k), what the layer adds on top of each harmonic the
  track already has (layer at its rendered level; the app adds it at VB_LEVEL around 0 dB).
- bass stem's own k f0 levels relative to its fundamental: how much natural harmonic structure the bass already has.
Usage: band_anatomy.py <root> <lib> --reference midi|yin [--midi-transpose auto|N] [--crop s0,dur] [--skip RE]
       [--limit N] [--out json]"""
import argparse, json, re
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly, sosfiltfilt
import research_gt_bass as G
import research_p1plus as P
import test_harmonic_continuity as H

p = argparse.ArgumentParser(); p.add_argument('root', type=Path); p.add_argument('lib', type=Path)
p.add_argument('--reference', default='yin'); p.add_argument('--midi-transpose', default='0')
p.add_argument('--crop', default=''); p.add_argument('--skip', default=''); p.add_argument('--limit', type=int, default=0)
p.add_argument('--out', type=Path)
a = p.parse_args(); lib = P.api(a.lib.resolve()); CORE = G.CORE
BANDS = ((55, 80), (80, 100), (100, 125), (125, 150)); K = np.arange(1, 9)
n, hop = 384, 96; win = np.hanning(n); FR = np.fft.rfftfreq(n * 8, 1 / CORE); BM = (FR >= 120) & (FR <= 1450)
acc = {b: dict(frames=0, tracked=0, lay=np.zeros(8), lay_b=np.zeros(8), lay_tot=0., layb_tot=0., nat=[], ratio=[], added=[], bassprof=[])
       for b in BANDS}
def render(x48):
    r = P.render(lib, x48, G.FS, 0, stage_flags=0)
    lat = r['latency']; lay = resample_poly(r['stem'][lat:, :].astype(float).mean(axis=1), 1, 16)
    return lay, H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / CORE
def harm(S, f):
    return np.array([S[np.abs(FR - k * f) <= max(3., .015 * k * f)].sum() for k in K])
done = 0
for name, mix, bass, fs, midis, _ in G.items(a.root):
    if a.skip and re.search(a.skip, name): continue
    s0 = 0.
    if a.crop:
        s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs)); mix, bass = mix[sl], bass[sl]
        if len(bass) < 5 * fs: continue
    bz = sosfiltfilt(G.LP, G.to_rate(bass, fs, CORE))
    if a.reference == 'midi':
        if not midis: continue
        notes = [x for m in midis for x in G.midi_notes(m)]; tt = G.grid(len(bz))
        tr_ = G.midi_octave(tt, notes, s0, bz)[0] if a.midi_transpose == 'auto' else int(a.midi_transpose)
        if tr_ is None: continue
        f0 = G.midi_f0(tt, notes, s0, tr_)
    else: tt, f0 = G.yin(bz)
    if np.sum(np.isfinite(f0)) < 20: continue
    st = lambda x: x if x.ndim == 2 and x.shape[1] == 2 else np.repeat(x.reshape(len(x), -1)[:, :1], 2, axis=1)
    mix48 = st(G.to_rate(mix, fs, G.FS)).astype(np.float32); bass48 = st(G.to_rate(bass, fs, G.FS)).astype(np.float32)
    lay, tr, tin = render(mix48); layb, _, _ = render(bass48)
    zm = G.to_rate(mix.mean(axis=1), fs, CORE); zb = G.to_rate(bass, fs, CORE)
    t_end = len(bz) / CORE - .2
    for s in range(int(1.0 * CORE), min(len(lay), len(layb), len(zm), int(t_end * CORE)) - n, hop):
        sel = (tt >= s / CORE) & (tt <= (s + n) / CORE); fs_ = f0[sel]; good = fs_[np.isfinite(fs_)]
        if len(good) < max(3, .8 * sel.sum()) or np.ptp(good) > .015 * np.median(good): continue
        fm = float(np.median(good)); b = next((x for x in BANDS if x[0] <= fm < x[1]), None)
        if b is None: continue
        d = acc[b]; d['frames'] += 1
        t = (s + n / 2) / CORE; k = min(max(np.searchsorted(tin, t), 0), len(tin) - 1)
        fr, am, stt = tr[k, :, 2], tr[k, :, 4], tr[k, :, 1]; live = (stt > 0) & (stt < 5) & (am > 0)
        if live.any():
            live &= am >= .1 * am[live].max()
            d['tracked'] += int(np.min(1200 * np.abs(np.log2(fr[live] / fm))) <= 50)
        SL = np.abs(np.fft.rfft(lay[s:s + n] * win, n * 8)) ** 2; SB = np.abs(np.fft.rfft(layb[s:s + n] * win, n * 8)) ** 2
        SM = np.abs(np.fft.rfft(zm[s:s + n] * win, n * 8)) ** 2; SS = np.abs(np.fft.rfft(zb[s:s + n] * win, n * 8)) ** 2
        hl, hb, hm, hs = harm(SL, fm), harm(SB, fm), harm(SM, fm), harm(SS, fm)
        d['lay'] += hl; d['lay_tot'] += SL[BM].sum(); d['lay_b'] += hb; d['layb_tot'] += SB[BM].sum()
        mt = SM[BM].sum() + 1e-30
        d['nat'].append(10 * np.log10(hm / mt + 1e-12)); d['ratio'].append(10 * np.log10((hl + 1e-30) / (hm + 1e-30)))
        d['added'].append(10 * np.log10(1 + hl / (hm + 1e-30))); d['bassprof'].append(10 * np.log10((hs + 1e-30) / (hs[0] + 1e-30)))
    done += 1; print('ITEM', done, name, flush=True)
    if a.limit and done >= a.limit: break
out = dict(items=done)
for b, d in acc.items():
    if not d['frames']: continue
    med = lambda v: [round(float(x), 1) for x in np.median(np.array(v), axis=0)]
    out[f'{b[0]}-{b[1]}'] = dict(frames=d['frames'], tracked=round(d['tracked'] / d['frames'], 3),
        layer_share_k1_8=[round(float(x), 3) for x in d['lay'] / d['lay_tot']], bass_share=round(float(d['lay'][1:].sum() / d['lay_tot']), 3),
        bass_alone_share_k1_8=[round(float(x), 3) for x in d['lay_b'] / d['layb_tot']], bass_alone_bass_share=round(float(d['lay_b'][1:].sum() / d['layb_tot']), 3),
        layer_mix_over_bass_alone_db=round(float(10 * np.log10(d['lay_tot'] / d['layb_tot'])), 2),
        native_db_k1_8=med(d['nat']), layer_over_native_db_k1_8=med(d['ratio']), added_db_k1_8=med(d['added']),
        bass_stem_k_over_k1_db=med(d['bassprof']))
print(json.dumps(out, indent=1))
if a.out: a.out.write_text(json.dumps(out, indent=1))
