"""Time-local check of the "phone protection" explanation. Per 50 ms frame of each heard variant vs its P1: the boost
(variant re P1, 150-600 Hz), the phone-model low-band GR of P1 there, the GR added by the variant, the absolute
variant 150-600 Hz level, and how much of the frame energy lies outside 150-600 Hz (masking room). Summaries over the
frames where the boost exceeds 1 dB. If the clean T60 boosts sit at the same or higher P1 GR and level than the
crackling synthetic ones, the protection alone does not explain the crackle. Usage: crackle_local.py <listen dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000; L = sys.argv[1]; N = FS // 20
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
cases = [('T60 L9 (clean)', 'r4l/r4l_3_T60.wav', 'A', 'B'), ('T60 L6 (clean)', 'r4l/r4l_4_T60.wav', 'A', 'B'),
         ('LOGOFF L6 (clean)', 'r4l6/r4l6_2_LOGOFF.wav', 'A', 'B'), ('LOGOFF L9 (CRACKLE)', 'r4l/r4l_1_LOGOFF.wav', 'B', 'A'),
         ('synth L6p (CRACKLE)', 'r4l6/r4l6_4_synth.wav', 'A', 'B'), ('synth L6 (CRACKLE)', 'r4l6/r4l6_5_synth.wav', 'A', 'B'),
         ('synth L9 (CRACKLE)', 'r4l/r4l_5_synth.wav', 'B', 'A')]
bp = lambda lo, hi: butter(4, [lo, hi], btype='band', fs=FS, output='sos')
fr = lambda y: (y[:len(y) // N * N].reshape(-1, N) ** 2).mean(axis=1) + 1e-20
def gr(y):
    _, inf = PM.drc(np.stack([y, y], 1), FS); g = np.asarray(inf['gr_low'], float)
    idx = np.minimum(len(g) - 1, (np.arange(len(y) // N) * N + N // 2) * len(g) // len(y)); return g[idx]
for nm, fn, hv, hp in cases:
    x, _ = sf.read(f'{L}/{fn}'); v, p = x[H[hv]].mean(axis=1), x[H[hp]].mean(axis=1)
    bv, bpp = fr(sosfiltfilt(bp(150, 600), v)), fr(sosfiltfilt(bp(150, 600), p))
    boost = 10 * np.log10(bv / bpp); gp, gv = gr(p), gr(v)
    out = 10 * np.log10(fr(v) / bv)  # full-band re 150-600 Hz: > 0 dB means other content to mask
    m = boost > 1
    q = lambda a: f'{np.median(a):5.1f}/{np.percentile(a, 90):5.1f}/{a.max():5.1f}' if len(a) else '   --'
    print(f'{nm:20s} frames boost>1 dB {m.mean() * 100:4.0f} % | boost med/p90/max {q(boost[m])} | P1 GR there {q(gp[m])} | '
          f'added GR {q((gv - gp)[m])} | level 150-600 dBFS {q(10 * np.log10(bv[m]))} | full re 150-600 {q(out[m])}')
