"""Score the R4-L 6 dB noise follow-up pairs (key hash checked). Per pair, after the phone model: A re B in 150-300 /
300-600 Hz (whole half), the 150-600 Hz difference at the listening spots, and the phone-model low-band gain reduction
of each half (max, p95). Usage: score_r4l6.py <key.json> <pair dir>"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import firwin2, fftconvolve, butter, sosfiltfilt
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000
kb = open(sys.argv[1], 'rb').read(); assert hashlib.sha256(kb).hexdigest().startswith('83b988487c4d5dad'), 'key hash mismatch'
key = json.loads(kb)['key']; print('hash ok; key', key)
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, inf = PM.drc(np.stack([y, y], 1), FS); gl = np.asarray(inf['gr_low'], float)
    return fftconvolve(z.mean(axis=1), FIR, 'same'), gl
bp = lambda lo, hi: butter(4, [lo, hi], btype='band', fs=FS, output='sos')
SPOTS = {'LOGOFF': ((4.0, 4.25), (4.5, 4.75), (5.0, 5.25)), 'synth': ((2.75, 3.0), (4.75, 5.0), (7.25, 7.5))}
for n in range(1, 6):
    k = key[f'r4l6_{n}']; p = next(Path(sys.argv[2]).glob(f'r4l6_{n}_*.wav')); x, _ = sf.read(p); x = x.mean(axis=1)
    (a, ga), (b, gb) = phone(x[:8 * FS]), phone(x[9 * FS:17 * FS])
    rel = lambda y1, y2, s=slice(None): round(float(10 * np.log10(np.sum(y1[s] ** 2) / np.sum(y2[s] ** 2))), 2)
    whole = {f'{lo}-{hi}': rel(sosfiltfilt(bp(lo, hi), a), sosfiltfilt(bp(lo, hi), b)) for lo, hi in ((150, 300), (300, 600))}
    fa, fb = sosfiltfilt(bp(150, 600), a), sosfiltfilt(bp(150, 600), b)
    sp = {f'{s0}': rel(fa, fb, slice(int(s0 * FS), int(s1 * FS))) for s0, s1 in SPOTS[k['src']]}
    print(f'r4l6_{n} {k["src"]} A={k["A"]} B={k["B"]} | A re B whole {whole} | 150-600 at spots {sp} | '
          f'GR low max A {ga.max():.1f} B {gb.max():.1f}, p95 A {np.percentile(ga, 95):.1f} B {np.percentile(gb, 95):.1f}')
