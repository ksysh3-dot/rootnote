"""R4-L blind set (local only, phone speaker with Rootnote off), app chain at the default level. Each file = A (8 s) +
1 s silence + B (8 s). Sources: Slakh train Track00060 (bass ~104 Hz; the 8 s window in 30-60 s where R4-L 9 dB changes
the phone-model 150-600 Hz band most), LOGOFF 40-48 s, synthetic 100 Hz bass with kicks (0-8 s). Pairs, each in a random
order, files shuffled: T60 p1/r4l9, T60 p1/r4l6, T60 r4l9/r4l9 (null), LOGOFF p1/r4l9, synth p1/r4l9.
Question: which half has the stronger bass, and noise (fizz, buzz, the level dipping on hits) in either.
Listening spots per source (the same for every pair of that source, so they say nothing about the key): the three
250 ms bins (not the first or last 0.5 s) where the energy of (r4l9 - p1) after the phone model in 150-600 Hz is largest.
Key JSON SHA-256 printed.
Usage: render_r4l_pairs.py <lib> <track00060 mix> <logoff> <synth bass100> <outdir> <keyfile> <seed>"""
import ctypes as C, hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt, firwin2, fftconvolve
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
sys.path.insert(0, 'study'); import phone_model as PM
libp, t60, logoff, synth, outdir, keyfile, seed = sys.argv[1:8]; seed = int(seed); outdir = Path(outdir)
FS = 48000; lib = RP.api(libp); lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]; RL = 16777216 | 67108864
def load(p):
    x, fs = sf.read(p, always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    return np.clip(resample_poly(x, FS // np.gcd(fs, FS), fs // np.gcd(fs, FS), axis=0) if fs != FS else x, -1, 1).astype(np.float32)
def render(x, level=None):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6)
    if level is not None: assert lib.pvb_set_r4_level(e.h, level) == 1
    cap = StageCapture(lib, e.h, RL, int(len(x) / FS * 3000) + 16) if level is not None else None
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close()
    return y[lat:].astype(np.float32)
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20)); band = butter(4, [150, 600], btype='band', fs=FS, output='sos')
def phone_band(y):
    m = y.astype(float).mean(axis=1); z, _ = PM.drc(np.stack([m, m], 1), FS); return sosfiltfilt(band, fftconvolve(z.mean(axis=1), FIR, 'same'))
def bins(p, r, B=FS // 4):
    """per 250 ms: energy of (r - p) and of p"""
    d = r - p; return (np.array([np.sum(d[i:i + B] ** 2) for i in range(0, len(p) - B + 1, B)]),
                       np.array([np.sum(p[i:i + B] ** 2) for i in range(0, len(p) - B + 1, B)]))
# Track00060: render 27-63 s once, pick the 8 s window (whole seconds, 30-52 s start) where (r4l9 - p1) is largest
# re p1 over the window (ratio of sums, so quiet moments do not dominate)
x60 = load(t60)[27 * FS:63 * FS]; p60, r60 = render(x60), render(x60, 9.)
d60, e60 = bins(phone_band(p60), phone_band(r60))
starts = range(3, 26); best = max(starts, key=lambda s: d60[4 * s:4 * s + 32].sum() / e60[4 * s:4 * s + 32].sum()); t0 = 27 + best
print('Track00060 window', t0, '-', t0 + 8, 's')
cut = lambda y, s: y[s * FS:(s + 8) * FS]
xl = load(logoff)[37 * FS:49 * FS]; xs = load(synth)[:8 * FS + FS // 2]
S = {'T60': {'p1': cut(p60, best), 'r4l9': cut(r60, best), 'r4l6': cut(render(x60, 6.), best)},
     'LOGOFF': {'p1': cut(render(xl), 3), 'r4l9': cut(render(xl, 9.), 3)},
     'synth': {'p1': render(xs)[:8 * FS], 'r4l9': render(xs, 9.)[:8 * FS]}}
guide = {}
for src, V in S.items():
    # the absolute size of the change (not re the moment's own level), away from the first and last 0.5 s
    d, e = bins(phone_band(V['p1']), phone_band(V['r4l9'])); d[:2] = d[-2:] = 0; top = sorted(np.argsort(d)[::-1][:3])
    guide[src] = [f'{i * .25:.2f}-{i * .25 + .25:.2f} s (B {9 + i * .25:.2f} s), {10 * np.log10(d[i] / e.mean()):+.0f} dB re mean' for i in top]
    print('spots', src, guide[src])
pairs = [('T60', 'p1', 'r4l9'), ('T60', 'p1', 'r4l6'), ('T60', 'r4l9', 'r4l9'), ('LOGOFF', 'p1', 'r4l9'), ('synth', 'p1', 'r4l9')]
rng = np.random.default_rng(seed); outdir.mkdir(parents=True, exist_ok=True); key = {}
fade = np.minimum(1, np.minimum(np.arange(8 * FS), np.arange(8 * FS)[::-1]) / 480)[:, None]
for n, j in enumerate(rng.permutation(len(pairs)), 1):
    src, a, b = pairs[j]
    if rng.random() < .5: a, b = b, a
    key[f'r4l_{n}'] = dict(src=src, A=a, B=b)
    sf.write(str(outdir / f'r4l_{n}_{src}.wav'), np.r_[S[src][a] * fade, np.zeros((FS, 2), np.float32), S[src][b] * fade], FS, subtype='PCM_16')
blob = json.dumps(dict(key=key, seed=seed, t60=t0, lib=T.source_commit(libp)), sort_keys=True).encode()
Path(keyfile).write_bytes(blob); print('key sha256', hashlib.sha256(blob).hexdigest())
print('files', sorted(p.name for p in outdir.glob('r4l_*.wav')))
