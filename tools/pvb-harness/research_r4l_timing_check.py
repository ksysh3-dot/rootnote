"""User: "no noise, but the timing does not match". For each pair file sent lately: (1) left vs right channel lag and
correlation per half (earphones expose an inter-channel offset), (2) A vs B lag: cross-correlation of the full-band
and the 150-600 Hz envelopes (5 ms) and of the waveforms, (3) onset times of the first notes in each half.
Usage: timing_check.py <file> ..."""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, correlate
FS = 48000
def lag(a, b, maxlag):
    c = correlate(a - a.mean(), b - b.mean(), 'full', method='fft'); mid = len(b) - 1
    seg = c[mid - maxlag:mid + maxlag + 1]; k = np.argmax(seg) - maxlag
    return k, seg.max() / (np.linalg.norm(a - a.mean()) * np.linalg.norm(b - b.mean()) + 1e-20)
bl = butter(4, [150, 600], btype='band', fs=FS, output='sos')
env = lambda y: np.sqrt(np.convolve(y ** 2, np.ones(240) / 240, 'same'))[::240]
for fn in sys.argv[1:]:
    x, fs = sf.read(fn); assert fs == FS
    A, B = x[:8 * FS], x[9 * FS:17 * FS]
    lr = [lag(h[:, 0], h[:, 1], FS // 100) for h in (A, B)]
    wa, wb = A.mean(axis=1), B.mean(axis=1)
    kw, cw = lag(wa, wb, FS // 10)
    ke, ce = lag(env(sosfiltfilt(bl, wa)), env(sosfiltfilt(bl, wb)), 40)
    def onsets(y):
        e = env(y); th = .3 * e.max(); on = np.flatnonzero((e[1:] > th) & (e[:-1] <= th)) + 1
        return [round(float(i * 240 / FS), 3) for i in on[:4]]
    print(f'{fn.split("/")[-1]:22s} L/R lag A {lr[0][0] / FS * 1000:+.2f} ms (r {lr[0][1]:.3f}) B {lr[1][0] / FS * 1000:+.2f} ms (r {lr[1][1]:.3f}) | '
          f'A vs B wave lag {kw / FS * 1000:+.2f} ms (r {cw:.3f}), env lag {ke * 5:+d} ms (r {ce:.3f}) | onsets A {onsets(wa)} B {onsets(wb)}')
