"""Pulse-excess series, window ranking, 14-song table. Needs only cache/ envelopes (no audio)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
import numpy as np
from pathlib import Path
import glob, os
B1 = Path('/home/ksysh/r3a-dev/plan16/B1'); C = B1 / 'cache'
MUSIC = sorted(glob.glob('/mnt/c/Users/ksysh/Music/vanila/*.flac'))
ER = 200.0
WIN = 400; HOP = 100
NFFT = 2048
w = np.hanning(WIN)
freqs = np.fft.rfftfreq(NFFT, 1 / ER)
band = (freqs >= 2) & (freqs <= 12)
df = freqs[1] - freqs[0]
ENG = ('P1', 'v15', 'v16a')


def mod_series(env):
    """returns starts(s), M (dB rms), peakHz, meanpow_dBFS per window"""
    n = (len(env) - WIN) // HOP + 1
    M = np.zeros(n); pk = np.zeros(n); lev = np.zeros(n)
    for k in range(n):
        s = env[k * HOP:k * HOP + WIN].astype(np.float64)
        lev[k] = 10 * np.log10(np.mean(10 ** (s / 10)) + 1e-30)
        x = (s - s.mean()) * w
        P = np.abs(np.fft.rfft(x, NFFT)) ** 2
        # variance units: sum |X|^2 over all bins (Parseval) = N * sum x^2 ; windowed power normalised by sum(w^2)
        Pn = P / (NFFT * np.sum(w ** 2)) * 2 * 1.0    # one-sided density per bin so that sum over bins ~ variance*? (see below)
        # one-sided: sum_k Pn_k ~ variance of the windowed signal normalised by window energy
        M[k] = np.sqrt(np.sum(Pn[band]) )
        pk[k] = freqs[band][np.argmax(P[band])]
    return np.arange(n) * HOP / ER, M, pk, lev


def sine_check():
    t = np.arange(WIN * 3) / ER
    e = 3.0 * np.sin(2 * np.pi * 5.0 * t)
    _, M, _, _ = mod_series(e)
    return float(M.mean())


if __name__ == '__main__':
    print('sine amplitude 3 dB at 5 Hz -> M =', sine_check(), '(target 3/sqrt2 = 2.12)')
