"""Opus check: what is in the LOGOFF input around the 4.12 s hit (song 44.12 s)? Tonal peaks 40-220 Hz over time."""
import numpy as np
from scipy.signal import find_peaks
import research_core_signals as S

FS = 48000
x = np.asarray(S.load_excerpt(S.LOGOFF, 43.6, 1.2), float)
x = x.mean(1) if x.ndim == 2 else x
N = int(0.12 * FS)                      # 120 ms window: ~8 Hz resolution (zero-padded)
w = np.hanning(N); nfft = 1 << 16
f = np.fft.rfftfreq(nfft, 1 / FS); band = (f >= 35) & (f <= 230)
ref = None
print('song t (centre) | top peaks Hz (dB re frame-max of whole span)')
rows = []
for c in np.arange(0.1, 1.1, 0.02):
    s = int((c - 0.06) * FS)
    X = np.abs(np.fft.rfft(x[s:s + N] * w, nfft))[band]
    rows.append(X)
M = max(r.max() for r in rows)
for c, X in zip(np.arange(0.1, 1.1, 0.02), rows):
    db = 20 * np.log10(X / M + 1e-12)
    pk, _ = find_peaks(db, height=-40, distance=int(6 / (FS / nfft)))
    top = sorted(pk, key=lambda i: -db[i])[:4]
    print(f'{43.6 + c:7.2f} | ' + '  '.join(f'{f[band][i]:6.1f}({db[i]:5.1f})' for i in sorted(top)))
# broadband (kick) energy 40-200 Hz per 10 ms
from scipy.signal import butter, sosfiltfilt
lo = sosfiltfilt(butter(4, [40, 200], btype='band', fs=FS, output='sos'), x)
e = [20 * np.log10(np.sqrt(np.mean(lo[i:i + 480] ** 2)) + 1e-12) for i in range(0, len(lo) - 480, 480)]
print('40-200 Hz level per 10 ms from 43.6 s:', ' '.join(f'{v:.0f}' for v in e))
