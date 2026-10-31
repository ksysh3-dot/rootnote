"""Where to listen in the level pairs (does not use the key): the bass notes of Track00040 40-48 s from its MIDI, and per
250 ms the size of (variant - P1) after the phone model in 150-600 Hz re P1, for r4c+12 and p1+12 (same for every pair).
Usage: listen_guide.py <lib> <track dir>"""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import re
import research_gt_bass as GB
from scipy.signal import resample_poly, butter, sosfiltfilt, firwin2, fftconvolve
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
sys.path.insert(0, 'study'); import phone_model as PM
libp, td = sys.argv[1], Path(sys.argv[2]); FS = 48000; lib = RP.api(libp); T0 = 40.
meta = (td / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
NAMES = 'C C# D D# E F F# G G# A A# B'.split()
for i in range(1, len(parts) - 1, 2):
    sid, blk = parts[i], parts[i + 1]
    if not re.search(r'inst_class:\s*Bass\b', blk) or not (td / 'MIDI' / f'{sid}.mid').exists(): continue
    prog = re.search(r'midi_program_name:\s*(.*)', blk)
    notes = sorted(n for n in GB.midi_notes(td / 'MIDI' / f'{sid}.mid') if n[1] > T0 and n[0] < T0 + 8)
    print(f'bass stem {sid} ({prog.group(1).strip() if prog else "?"}): notes in 40-48 s (time in the half, s)')
    for s0, s1, pz in notes:
        print(f'  {max(0, s0 - T0):5.2f}-{min(8, s1 - T0):5.2f} s  {NAMES[int(pz) % 12]}{int(pz) // 12 - 1}  {440 * 2 ** ((pz - 69) / 12):6.1f} Hz')
x, fs = sf.read(td / 'mix.flac', always_2d=True)
if x.shape[1] == 1: x = np.repeat(x, 2, 1)
x = resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x
x = np.clip(x[int((T0 - 3) * FS):int((T0 + 9) * FS)], -1, 1).astype(np.float32)
def render(stage=0, level=0.):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, vb_level_db=level)
    cap = StageCapture(lib, e.h, stage, int(len(x) / FS * 3000) + 16) if stage else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[3 * FS + lat:3 * FS + lat + 8 * FS].astype(float).mean(axis=1)
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
band = butter(4, [150, 600], btype='band', fs=FS, output='sos')
p = sosfiltfilt(band, phone(render()))
for nm, y in (('r4c+12', render(16777216, 12.)), ('p1+12', render(0, 12.))):
    d = sosfiltfilt(band, phone(y)) - p; B = FS // 4
    r = [10 * np.log10(np.sum(d[i:i + B] ** 2) / (np.sum(p[i:i + B] ** 2) + 1e-30) + 1e-30) for i in range(0, 8 * FS, B)]
    print(nm, '(variant - P1) re P1, 150-600 Hz after the phone model, per 250 ms:')
    print('  ' + ' '.join(f'{i * .25:.2f}:{v:+.0f}' for i, v in enumerate(r)))
