"""Pick Slakh train tracks (outside BabySlakh ids) whose bass MIDI (octave from the stem, midi_octave) has a median
f0 of 95-130 Hz and dense notes in 30-60 s. Prints the top candidates. Usage: pick_track.py <train dir>"""
import re, sys
from pathlib import Path
import numpy as np
import research_gt_bass as G
root = Path(sys.argv[1]); out = []
for name, mix, bass, fs, midis, _ in G.items(root):
    if re.search(r'Track000[01][0-9]|Track00020', name) or not midis: continue
    sl = slice(30 * fs, 60 * fs); b = bass[sl]
    if len(b) < 20 * fs: continue
    from scipy.signal import sosfiltfilt
    bz = sosfiltfilt(G.LP, G.to_rate(b, fs, G.CORE)); tt = G.grid(len(bz))
    notes = [n for m in midis for n in G.midi_notes(m)]
    tr, agree = G.midi_octave(tt, notes, 30., bz)
    if tr is None: continue
    f0 = G.midi_f0(tt, notes, 30., tr); ok = np.isfinite(f0)
    if ok.mean() < .6: continue
    med = float(np.median(f0[ok])); out.append((med, float(ok.mean()), name))
    if 95 <= med <= 130: print(f'{name} median {med:.0f} Hz voiced {ok.mean():.2f}', flush=True)
    if sum(95 <= m <= 130 for m, _, _ in out) >= 6: break
