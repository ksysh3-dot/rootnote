"""Score the R4 level pairs (key hash checked). Per pair, after the phone model: A re B level in 150-300 / 300-600 Hz over
the whole half and in the listening spots 3.7-4.0, 7.3-7.8, 0.3-0.9, 5.2-5.8 s (150-600 Hz).
Usage: score_level.py <key.json> <pair dir>"""
import hashlib, json, sys
import numpy as np
import soundfile as sf
from scipy.signal import firwin2, fftconvolve, butter, sosfiltfilt
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000
kb = open(sys.argv[1], 'rb').read(); assert hashlib.sha256(kb).hexdigest().startswith('76f8ca4aebc05a64'), 'key hash mismatch'
key = json.loads(kb)['key']; print('hash ok; key', key)
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
bp = lambda lo, hi: butter(4, [lo, hi], btype='band', fs=FS, output='sos')
spots = ((3.7, 4.0), (7.3, 7.8), (.3, .9), (5.2, 5.8))
for n in range(1, 5):
    k = key[f'level_{n}']; x, _ = sf.read(f'{sys.argv[2]}/r4_level_{n}.wav'); x = x.mean(axis=1)
    a, b = phone(x[:8 * FS]), phone(x[9 * FS:17 * FS])
    rel = lambda y1, y2, s=slice(None): 10 * np.log10(np.sum(y1[s] ** 2) / np.sum(y2[s] ** 2))
    whole = {f'{lo}-{hi}': round(float(rel(sosfiltfilt(bp(lo, hi), a), sosfiltfilt(bp(lo, hi), b))), 2) for lo, hi in ((150, 300), (300, 600))}
    fa, fb = sosfiltfilt(bp(150, 600), a), sosfiltfilt(bp(150, 600), b)
    sp = {f'{s0}-{s1}': round(float(rel(fa, fb, slice(int(s0 * FS), int(s1 * FS)))), 2) for s0, s1 in spots}
    print(f'level_{n} A={k["A"]} B={k["B"]} | A re B whole {whole} | 150-600 Hz at spots {sp}')
