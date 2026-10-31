"""Energy of (A - B) re A for each pair file (does not reveal which variant is which; a null pair gives -inf).
Also the A-B difference in 250-700 Hz. Usage: pair_diff.py <files...>"""
import sys
import numpy as np
import soundfile as sf
FS = 48000
for p in sys.argv[1:]:
    z, _ = sf.read(p); z = z.mean(axis=1); a, b = z[:8 * FS], z[9 * FS:17 * FS]
    d = a - b; S = np.abs(np.fft.rfft(d)) ** 2; fr = np.fft.rfftfreq(len(d), 1 / FS); SA = np.abs(np.fft.rfft(a)) ** 2
    band = (fr >= 250) & (fr < 700)
    print(p.split('/')[-1], 'diff re A', round(float(10 * np.log10(np.sum(d ** 2) / np.sum(a ** 2) + 1e-30)), 1), 'dB;',
          '250-700 Hz', round(float(10 * np.log10(S[band].sum() / (SA[band].sum() + 1e-30) + 1e-30)), 1), 'dB')
