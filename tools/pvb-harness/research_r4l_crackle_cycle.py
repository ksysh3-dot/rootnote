"""The synthetic bass repeats every 0.5 s (bass note + a kick sweeping 90 -> 50 Hz). Averaged over the 16 cycles of the
excerpt: variant re P1 at k2 (200 Hz) and k3 (300 Hz), in 10 ms steps of the cycle, plus the P1 level there. A step
from ~0 to the full R4-L gain partway through the note (e.g. when a kick track near 50 Hz = f0/2 dies and the
"twice a lower track" exclusion releases) would be gain switching. Usage: crackle_cycle.py <listen dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert
FS = 48000; L = sys.argv[1]
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
cases = [('L6p', 'r4l6/r4l6_4_synth.wav', 'A', 'B'), ('L6', 'r4l6/r4l6_5_synth.wav', 'A', 'B'), ('L9', 'r4l/r4l_5_synth.wav', 'B', 'A')]
C = FS // 2; S = FS // 100
res = {}
for nm, fn, hv, hp in cases:
    x, _ = sf.read(f'{L}/{fn}'); v, p = x[H[hv]].mean(axis=1), x[H[hp]].mean(axis=1)
    for k, (lo, hi) in ((2, (185, 215)), (3, (285, 315))):
        sos = butter(4, [lo, hi], btype='band', fs=FS, output='sos')
        ev, ep = (np.abs(hilbert(sosfiltfilt(sos, s))) ** 2 for s in (v, p))
        cv = ev[:16 * C].reshape(16, C)[1:].mean(axis=0); cp = ep[:16 * C].reshape(16, C)[1:].mean(axis=0)
        bv = cv.reshape(-1, S).mean(axis=1); bpp = cp.reshape(-1, S).mean(axis=1)
        res[(nm, k)] = (10 * np.log10(bv / bpp), 10 * np.log10(bpp / bpp.max()))
print('cycle ms | ' + ' | '.join(f'{nm} k{k} re P1' for nm in ('L6p', 'L6', 'L9') for k in (2, 3)) + ' | P1 k2 level, k3 level (re max)')
for i in range(0, 50):
    print(f'{i * 10:4d}     | ' + ' | '.join(f'{res[(nm, k)][0][i]:+11.1f}' for nm in ('L6p', 'L6', 'L9') for k in (2, 3)) +
          f' | {res[("L6", 2)][1][i]:+6.1f} {res[("L6", 3)][1][i]:+6.1f}')
