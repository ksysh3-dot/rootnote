"""Test bass signals for the roughness check (16-bit WAV, 48 kHz, 10 s, -12 dBFS bass): a bass note with natural
decay every 0.5 s (8 ms attack, 350 ms decay, 3 partials 1 : -6 : -15 dB) plus a kick on every note, at f0 = 45, 55,
100 and 125 Hz, and a little pink noise as the rest of the mix (-30 dBFS). Usage: make_synth.py <outdir>"""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
FS = 48000; t = np.arange(10 * FS) / FS; out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(1); w = np.fft.irfft(np.fft.rfft(rng.standard_normal(len(t))) / np.sqrt(np.maximum(np.fft.rfftfreq(len(t), 1 / FS), 20)))
pink = .03 * w / np.sqrt(np.mean(w ** 2))
u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
kick = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-u / .02)) / FS)
for f0 in (45, 55, 100, 125):
    bass = env * sum(a * np.sin(2 * np.pi * k * f0 * t) for k, a in ((1, 1), (2, .5), (3, .18)))
    x = .25 * bass / np.abs(bass).max() + .2 * kick + pink
    sf.write(str(out / f'bass{f0}.wav'), np.stack([x, x], 1).astype(np.float32), FS, subtype='PCM_16')
