"""Score the R4 bass pairs (key hash checked). Per pair, after the phone model: the level of each half in 150-300 /
300-600 / 600-1200 Hz and the difference signal (A - B) re A in 150-600 Hz. Usage: score_bass.py <key.json> <pair dir>"""
import hashlib, json, sys
import numpy as np
import soundfile as sf
from scipy.signal import firwin2, fftconvolve
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000
kb = open(sys.argv[1], 'rb').read(); assert hashlib.sha256(kb).hexdigest().startswith('60e6a6216fe832c5'), 'key hash mismatch'
key = {k: v for k, v in json.loads(kb)['key'].items() if k.startswith('bass')}; print('hash ok; bass key', key)
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
for n in (1, 2, 3, 4):
    k = key[f'bass_{n}']; x, _ = sf.read(f'{sys.argv[2]}/r4_bass_{n}.wav'); x = x.mean(axis=1)
    a, b = phone(x[:8 * FS]), phone(x[9 * FS:17 * FS]); fr = np.fft.rfftfreq(len(a), 1 / FS)
    P = lambda y, lo, hi: np.sum(np.abs(np.fft.rfft(y))[(fr >= lo) & (fr < hi)] ** 2)
    lv = {f'{lo}-{hi}': round(float(10 * np.log10(P(a, lo, hi) / P(b, lo, hi))), 2) for lo, hi in ((150, 300), (300, 600), (600, 1200))}
    d = 10 * np.log10(P(a - b, 150, 600) / P(a, 150, 600) + 1e-30)
    print(f'bass_{n} A={k["A"]} B={k["B"]} | A re B (dB, phone) {lv} | (A-B) re A 150-600 Hz {d:.1f} dB')
