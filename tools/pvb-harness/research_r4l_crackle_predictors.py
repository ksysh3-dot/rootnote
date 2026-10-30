"""Which measurable quantity separates the halves heard as crackling on the phone speaker from the clean ones? Labels
from the blind answers (key hashes verified): crackle = LOGOFF L9, synth L9, synth L6, synth L6p; clean = P1 on all
three inputs, T60 L6/L9, LOGOFF R4c +6 dB strength (r4 noise set). Per half (mono mean): absolute 150-400 and
150-600 Hz level (whole half RMS dBFS, 50 ms max and p95), sample peak, full-band RMS, low-mid share, and the phone
model gain reduction (low band max/p95, all bands max). Usage: crackle_predictors.py <listen dir>"""
import json, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000; L = sys.argv[1]
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
# (file, half, variant, label)
items = [('r4l/r4l_1_LOGOFF.wav', 'A', 'LOGOFF p1', 'clean'), ('r4l/r4l_1_LOGOFF.wav', 'B', 'LOGOFF L9', 'CRACKLE'),
         ('r4l/r4l_5_synth.wav', 'A', 'synth p1', 'clean'), ('r4l/r4l_5_synth.wav', 'B', 'synth L9', 'CRACKLE'),
         ('r4l/r4l_3_T60.wav', 'A', 'T60 L9', 'clean'), ('r4l/r4l_3_T60.wav', 'B', 'T60 p1', 'clean'),
         ('r4l/r4l_4_T60.wav', 'A', 'T60 L6', 'clean'),
         ('r4l6/r4l6_1_synth.wav', 'A', 'synth L6', 'CRACKLE'), ('r4l6/r4l6_4_synth.wav', 'A', 'synth L6p', 'CRACKLE'),
         ('r4l6/r4l6_4_synth.wav', 'B', 'synth p1', 'clean'),
         ('r4l6/r4l6_2_LOGOFF.wav', 'A', 'LOGOFF L6 (nm)', 'clean'), ('r4l6/r4l6_3_LOGOFF.wav', 'B', 'LOGOFF L6p (nm)', 'clean'),
         ('r4/r4_noise_1.wav', 'A', 'LOGOFF p1 (+6)', 'clean'), ('r4/r4_noise_1.wav', 'B', 'LOGOFF r4c (+6)', 'clean')]
bp = lambda lo, hi: butter(4, [lo, hi], btype='band', fs=FS, output='sos')
db = lambda e: 10 * np.log10(e + 1e-20)
def win(y, n=FS // 20):
    m = len(y) // n; return y[:m * n].reshape(m, n)
rows = []
for fn, h, var, lab in items:
    try: x, fs = sf.read(f'{L}/{fn}')
    except Exception as e:
        print('skip', fn, e); continue
    y = x[H[h]].mean(axis=1); r = dict(var=var, label=lab)
    for lo, hi in ((150, 400), (150, 600)):
        b = sosfiltfilt(bp(lo, hi), y); w = (win(b) ** 2).mean(axis=1)
        r[f'{lo}-{hi} rms'] = db((b ** 2).mean()); r[f'{lo}-{hi} max50'] = db(w.max()); r[f'{lo}-{hi} p95'] = db(np.percentile(w, 95))
    r['full rms'] = db((y ** 2).mean()); r['peak'] = 20 * np.log10(np.abs(y).max())
    r['lowmid share'] = r['150-600 rms'] - r['full rms']
    z, inf = PM.drc(np.stack([y, y], 1), FS); gl = np.asarray(inf['gr_low'], float); g = np.asarray(inf['gr_bands'], float)
    r['GR low max'] = gl.max(); r['GR low p95'] = np.percentile(gl, 95); r['GR all max'] = g.max()
    rows.append(r)
keys = [k for k in rows[0] if k not in ('var', 'label')]
print(f'{"variant":18s} {"label":7s} ' + ' '.join(f'{k[:13]:>13s}' for k in keys))
for r in sorted(rows, key=lambda r: (r['label'], r['var'])):
    print(f'{r["var"]:18s} {r["label"]:7s} ' + ' '.join(f'{r[k]:13.1f}' for k in keys))
print('\nseparation (min crackle - max clean; > 0 = a threshold separates them):')
for k in keys:
    c = [r[k] for r in rows if r['label'] == 'CRACKLE']; n = [r[k] for r in rows if r['label'] == 'clean']
    print(f'  {k:16s} crackle {min(c):6.1f}..{max(c):6.1f}  clean {min(n):6.1f}..{max(n):6.1f}  gap {min(c) - max(n):+.1f}')
json.dump(rows, open('/tmp/crackle_rows.json', 'w'), indent=1)
