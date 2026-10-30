"""R4-L 6 dB crackles on the synthetic 100 Hz bass with or without the kick ("white noise with pops, tone and noise
mixed"). Hypothesis: the boost also lifts layers of short tracks born from the -30 dBFS pink noise (any track between
73 and 220 Hz gets it), which a bare bass leaves unmasked. Inputs: bass alone, pink alone, bass + pink (the heard
no-kick case), bass + kick60 + pink. Per input, P1 and L6 (app chain, defaults, 8 s): d = L6 - P1 energy re P1 in
150-1000 Hz, the share of d on the 100 Hz partial lines, d above 1 kHz re P1 there, the 10 ms envelope crest of the
off-line part of d (pops), and per cycle phase (0-0.25 s note body / 0.25-0.5 s tail) the off-line d energy.
Usage: crackle_noise_tracks.py <lib>"""
import ctypes as C, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
FS = 48000; lib = RP.api(sys.argv[1]); lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
t = np.arange(10 * FS) / FS
rng = np.random.default_rng(1); w = np.fft.irfft(np.fft.rfft(rng.standard_normal(len(t))) / np.sqrt(np.maximum(np.fft.rfftfreq(len(t), 1 / FS), 20)))
pink = .03 * w / np.sqrt(np.mean(w ** 2))
u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
kick60 = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(60 + 30 * np.exp(-u / .02)) / FS)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
X = {'bass only': bass, 'pink only': pink, 'bass+pink (heard)': bass + pink, 'bass+kick60+pink (heard)': bass + .2 * kick60 + pink}
def render(x, level=None):
    x = np.stack([x, x], 1).astype(np.float32); e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:lat + 8 * FS].mean(axis=1)
E = lambda y: np.sum(y ** 2) + 1e-30
b1 = butter(4, [150, 1000], btype='band', fs=FS, output='sos'); hf = butter(4, 1000, btype='high', fs=FS, output='sos')
def lines_split(y):
    """split y (150-1000 Hz) into on-line (100 Hz partials +-1.5 Hz) and off-line parts, by 0.5 s FFT frames"""
    on = np.zeros_like(y); n = FS // 2
    for i in range(0, len(y) - n + 1, n):
        S = np.fft.rfft(y[i:i + n]); f = np.fft.rfftfreq(n, 1 / FS)
        m = (f > 150) & (f < 1000) & (np.abs(f - np.round(f / 100) * 100) < 3); on[i:i + n] = np.fft.irfft(S * m, n)
    return on, y - on
for nm, x in X.items():
    p, v = render(x), render(x, 6.); d = v - p; db = sosfiltfilt(b1, d); pb = sosfiltfilt(b1, p)
    on, off = lines_split(db)
    e10 = np.convolve(off ** 2, np.ones(480) / 480, 'same')[::480]
    cyc = off[:16 * FS // 2].reshape(16, 2, FS // 4) ** 2
    vb = sosfiltfilt(b1, v); _, offp = lines_split(pb); _, offv = lines_split(vb)
    print(f'{nm:24s} off-line (noise-like) 150-1000 Hz: P1 {10 * np.log10(E(offp) / E(pb)):+6.1f} dB re P1 band, '
          f'L6 {10 * np.log10(E(offv) / E(pb)):+6.1f} dB -> {10 * np.log10(E(offv) / E(offp)):+5.1f} dB more')
    print(f'{nm:24s} d re P1 150-1000 {10 * np.log10(E(db) / E(pb)):+6.1f} dB | on lines {100 * E(on) / E(db):3.0f} % | '
          f'd>1k re P1>1k {10 * np.log10(E(sosfiltfilt(hf, d)) / E(sosfiltfilt(hf, p))):+6.1f} dB | off-line crest {10 * np.log10(e10.max() / e10.mean()):4.1f} dB | '
          f'off-line body/tail {10 * np.log10(cyc[:, 0].sum() / cyc[:, 1].sum()):+5.1f} dB | P1 150-600 vs L6: '
          f'{10 * np.log10(E(sosfiltfilt(butter(4, [150, 600], btype="band", fs=FS, output="sos"), v)) / E(sosfiltfilt(butter(4, [150, 600], btype="band", fs=FS, output="sos"), p))):+5.1f} dB')
