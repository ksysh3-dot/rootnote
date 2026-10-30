"""Does the kick (90 -> 50 Hz sweep, f0/2 of the 100 Hz bass) switch the R4-L boost off and on inside every note? Build
bass100 as make_synth.py does, with the kick, without it, and with a kick that settles at 60 Hz (kick60: the same energy
and onset, never near f0/2); render P1 and R4-L 6 dB (app chain, defaults); per version:
the cycle-averaged k3 (300 Hz) boost in 20 ms steps, the number of cycle steps where it is below 1 dB (off), and the
share of the added layer d = L6 - P1 on the partial lines (150-1000 Hz, 0.5 s windows).
Usage: crackle_nokick.py <lib> <outdir>"""
import ctypes as C, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
FS = 48000; lib = RP.api(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
t = np.arange(10 * FS) / FS
rng = np.random.default_rng(1); w = np.fft.irfft(np.fft.rfft(rng.standard_normal(len(t))) / np.sqrt(np.maximum(np.fft.rfftfreq(len(t), 1 / FS), 20)))
pink = .03 * w / np.sqrt(np.mean(w ** 2))
u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
kick = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-u / .02)) / FS)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18)))
kick60 = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(60 + 30 * np.exp(-u / .02)) / FS)   # same start, floor off f0/2
X = {'kick': .25 * bass / np.abs(bass).max() + .2 * kick + pink, 'nokick': .25 * bass / np.abs(bass).max() + pink,
     'kick60': .25 * bass / np.abs(bass).max() + .2 * kick60 + pink}
def render(x, level=None):
    x = np.stack([x, x], 1).astype(np.float32); e = T.Engine(lib, FS, vb_on=1, vb_algo=6)
    cap = None
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:lat + 8 * FS].mean(axis=1)
f0 = 100.
def share(y):
    n = len(y); S = np.abs(np.fft.rfft(y * np.hanning(n), 8 * n)) ** 2; f = np.fft.rfftfreq(8 * n, 1 / FS)
    band = (f > 150) & (f < 1000); lines = band & (np.abs(f / f0 - np.round(f / f0)) * f0 < 1.5)
    return S[lines].sum() / S[band].sum()
sos = butter(4, [285, 315], btype='band', fs=FS, output='sos'); Cy = FS // 2; S = FS // 50
for nm, x in X.items():
    p, v = render(x), render(x, 6.); d = v - p
    ev, ep = (np.abs(hilbert(sosfiltfilt(sos, s))) ** 2 for s in (v, p))
    cv = ev[:16 * Cy].reshape(16, Cy)[1:].mean(axis=0).reshape(-1, S).mean(axis=1)
    cp = ep[:16 * Cy].reshape(16, Cy)[1:].mean(axis=0).reshape(-1, S).mean(axis=1)
    r = 10 * np.log10(cv / cp)
    sd = [share(d[i:i + Cy]) for i in range(0, len(d) - Cy + 1, Cy)]
    print(f'{nm:7s} k3 boost per 20 ms of the cycle: ' + ' '.join(f'{z:+.1f}' for z in r))
    print(f'        steps below +1 dB: {int(np.sum(r < 1))}/25 | d on partial lines median {100 * np.median(sd):.0f} % | '
          f'boost median {np.median(r):+.1f} dB')
    sf.write(str(out / f'bass100_{nm}_src.wav'), np.stack([x, x], 1).astype(np.float32), FS, subtype='PCM_16')
