"""Score the R4 noise pairs only (the bass entries of the key are not printed). Checks both hashes, prints the noise key,
the fixed hit proxy per half, and (post hoc, after the answers) where in time r4c and p1 differ after each hit:
phone model, 150-600 Hz and 600-2000 Hz, energy of (r4c - p1) re p1 in 0-40 / 40-90 / 90-150 ms after the hits
4.12 4.29 4.45 4.57 4.70 4.87 s, and the 150-600 Hz level of each variant in those bins re its own 0-40 ms.
Usage: score_noise.py <key.json> <proxy.json> <pair dir>"""
import hashlib, json, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, firwin2, fftconvolve
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000
kb, pb = open(sys.argv[1], 'rb').read(), open(sys.argv[2], 'rb').read()
assert hashlib.sha256(kb).hexdigest().startswith('60e6a6216fe832c5'), 'key hash mismatch'
assert hashlib.sha256(pb).hexdigest().startswith('e9695ed91ac9ee1e'), 'proxy hash mismatch'
key = {k: v for k, v in json.loads(kb)['key'].items() if k.startswith('noise')}; prox = json.loads(pb)
print('hashes ok; noise key', key)
for n in (1, 2, 3):
    k = key[f'noise_{n}']; pr = prox[f'r4_noise_{n}.wav']
    for h, r in pr.items():
        print(f'noise_{n} {h} t={r["hit_t"]}', ' '.join(f'{m}: {k["A"]} {r["A"][m]:.4g} / {k["B"]} {r["B"][m]:.4g}' for m in r['A']))
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
for n in (1, 2, 3):
    k = key[f'noise_{n}']
    if k['A'] == k['B']: continue
    x, _ = sf.read(f'{sys.argv[3]}/r4_noise_{n}.wav'); x = x.mean(axis=1)
    h = dict(A=x[:8 * FS], B=x[9 * FS:17 * FS]); v = {k['A']: phone(h['A']), k['B']: phone(h['B'])}
    for lo, hi in ((150, 600), (600, 2000)):
        sos = butter(4, [lo, hi], btype='band', fs=FS, output='sos')
        p, r = sosfiltfilt(sos, v['p1']), sosfiltfilt(sos, v['r4c']); d = r - p
        bins = ((0, .04), (.04, .09), (.09, .15)); E = lambda y, t, a, b: np.sum(y[int((t + a) * FS):int((t + b) * FS)] ** 2)
        hits = (4.124, 4.29, 4.45, 4.57, 4.726, 4.87)
        diff = [10 * np.log10(sum(E(d, t, a, b) for t in hits) / sum(E(p, t, a, b) for t in hits)) for a, b in bins]
        dec = {nm: [10 * np.log10(sum(E(y, t, a, b) / (b - a) for t in hits) / sum(E(y, t, 0, .04) / .04 for t in hits)) for a, b in bins[1:]]
               for nm, y in (('p1', p), ('r4c', r))}
        print(f'noise_{n} {lo}-{hi} Hz: (r4c-p1) re p1 by bin 0-40/40-90/90-150 ms', [round(q, 1) for q in diff],
              '| level re own 0-40 ms at 40-90/90-150 ms', {nm: [round(q, 1) for q in s] for nm, s in dec.items()})
