"""Fourth explanation: the added layer itself is not clean on the synthetic bass (inharmonic or modulated), and a bare
bass leaves it unmasked. d = variant - P1 (same chain, so d is the extra layer). Per synthetic case: the share of d
energy (150-1000 Hz) on the partial lines k*f0 +-1.5 Hz, per 0.5 s, and the 50 ms envelope crest of d; the same share
for P1 itself. For the songs, the d energy re the rest of the mix in 150-600 Hz (masking). Usage: <listen dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
FS = 48000; L = sys.argv[1]
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
syn = [('synth L6p CRACKLE', 'r4l6/r4l6_4_synth.wav', 'A', 'B'), ('synth L6 CRACKLE', 'r4l6/r4l6_5_synth.wav', 'A', 'B'),
       ('synth L9 CRACKLE', 'r4l/r4l_5_synth.wav', 'B', 'A')]
songs = [('T60 L9 clean', 'r4l/r4l_3_T60.wav', 'A', 'B'), ('T60 L6 clean', 'r4l/r4l_4_T60.wav', 'A', 'B'),
         ('LOGOFF L6 clean', 'r4l6/r4l6_2_LOGOFF.wav', 'A', 'B'), ('LOGOFF L9 CRACKLE', 'r4l/r4l_1_LOGOFF.wav', 'B', 'A')]
bp = butter(4, [150, 1000], btype='band', fs=FS, output='sos'); bl = butter(4, [150, 600], btype='band', fs=FS, output='sos')
f0 = 99.98
def share(y):
    n = len(y); w = np.hanning(n); S = np.abs(np.fft.rfft(y * w, 8 * n)) ** 2; f = np.fft.rfftfreq(8 * n, 1 / FS)
    band = (f > 150) & (f < 1000); lines = band & (np.abs(f / f0 - np.round(f / f0)) * f0 < 1.5)
    return S[lines].sum() / S[band].sum()
for nm, fn, hv, hp in syn:
    x, _ = sf.read(f'{L}/{fn}'); v, p = x[H[hv]].mean(axis=1), x[H[hp]].mean(axis=1); d = v - p
    seg = FS // 2; sd = [share(d[i:i + seg]) for i in range(0, len(d) - seg + 1, seg)]; spp = [share(p[i:i + seg]) for i in range(0, len(p) - seg + 1, seg)]
    e = sosfiltfilt(bp, d) ** 2; env = np.convolve(e, np.ones(2400) / 2400, 'same')[::480]
    print(f'{nm:18s} d on partial lines: median {100 * np.median(sd):4.0f} % (min {100 * min(sd):3.0f} %) | P1 itself {100 * np.median(spp):4.0f} % | '
          f'd re P1 150-1000 {10 * np.log10(np.sum(sosfiltfilt(bp, d) ** 2) / np.sum(sosfiltfilt(bp, p) ** 2)):+5.1f} dB | d env crest {10 * np.log10(env.max() / env.mean()):4.1f} dB')
for nm, fn, hv, hp in songs:
    x, _ = sf.read(f'{L}/{fn}'); v, p = x[H[hv]].mean(axis=1), x[H[hp]].mean(axis=1); d = v - p
    print(f'{nm:18s} d re P1 150-600 {10 * np.log10(np.sum(sosfiltfilt(bl, d) ** 2) / np.sum(sosfiltfilt(bl, p) ** 2)):+5.1f} dB')
