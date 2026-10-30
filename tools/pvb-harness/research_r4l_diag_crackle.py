"""Where does the R4-L 9 dB crackle come from? Pair files r4l_1 (LOGOFF p1/r4l9), r4l_5 (synth p1/r4l9) and the clean
control r4l_3 (T60 r4l9/p1). (1) Digital file: d = r4l9 - p1 per band re p1 in that band; impulsiveness of d above 1 kHz;
sample peaks. (2) Phone model: low-band (oct 4) and all-band gain reduction of each half (max, p95, and the largest
50 ms GR rise = how fast the limiter clamps); the phone output difference above 1 kHz re p1 (limiter modulation).
(3) Per 50 ms: when d (150-600 Hz) is largest, and the phone low-band GR there. Usage: diag_crackle.py <pair dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, firwin2, fftconvolve
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000; D = sys.argv[1]
files = {'LOGOFF': ('r4l_1_LOGOFF.wav', 'A'), 'synth': ('r4l_5_synth.wav', 'A'), 'T60 (clean)': ('r4l_3_T60.wav', 'B')}
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
bp = lambda lo, hi: butter(4, [lo, hi], btype='band', fs=FS, output='sos')
E = lambda y: np.sum(y ** 2) + 1e-30
for nm, (fn, p1side) in files.items():
    x, _ = sf.read(f'{D}/{fn}'); halves = dict(A=x[:8 * FS], B=x[9 * FS:17 * FS])
    p = halves[p1side]; r = halves['B' if p1side == 'A' else 'A']
    pm, rm = p.mean(axis=1), r.mean(axis=1); d = rm - pm
    bands = ((30, 150), (150, 600), (600, 2000), (2000, 8000))
    rel = {f'{lo}-{hi}': round(float(10 * np.log10(E(sosfiltfilt(bp(lo, hi), d)) / E(sosfiltfilt(bp(lo, hi), pm)))), 1) for lo, hi in bands}
    hf = sosfiltfilt(bp(1000, 8000), d); env = np.sqrt(np.convolve(hf ** 2, np.ones(48) / 48, 'same'))
    print(f'== {nm}: digital (r4l9 - p1) re p1 by band dB {rel}; d>1 kHz peak/rms {env.max() / (env.mean() + 1e-30):.1f}; '
          f'sample peak p1 {np.abs(p).max():.3f} r4l9 {np.abs(r).max():.3f}')
    out = {}
    for v, y in (('p1', pm), ('r4l9', rm)):
        z, inf = PM.drc(np.stack([y, y], 1), FS); g = np.asarray(inf['gr_bands'], float); gl = np.asarray(inf['gr_low'], float)
        hop = len(y) / g.shape[-1]; k50 = max(1, int(round(.05 * FS / hop)))
        rise = np.max(gl[k50:] - gl[:-k50]) if len(gl) > k50 else 0
        out[v] = (fftconvolve(z.mean(axis=1), FIR, 'same'), gl, hop)
        print(f'  {v}: phone GR low max {gl.max():.1f} p95 {np.percentile(gl, 95):.1f} dB, fastest 50 ms rise {rise:.1f} dB; '
              f'all-band GR max {g.max():.1f}, bands max {np.round(g.max(axis=-1), 1).tolist()}')
    zp, zr = out['p1'][0], out['r4l9'][0]
    for lo, hi in ((1000, 4000), (4000, 8000)):
        print(f'  phone output (r4l9 - p1) {lo}-{hi} Hz re p1: {10 * np.log10(E(sosfiltfilt(bp(lo, hi), zr - zp)) / E(sosfiltfilt(bp(lo, hi), zp))):.1f} dB')
    B = FS // 20; dl = sosfiltfilt(bp(150, 600), d); en = np.array([E(dl[i:i + B]) for i in range(0, len(dl) - B + 1, B)])
    top = np.argsort(en)[::-1][:5]; gl, hop = out['r4l9'][1], out['r4l9'][2]
    print('  largest (r4l9 - p1) 150-600 Hz, 50 ms bins:', ', '.join(
        f'{i * .05:.2f} s ({10 * np.log10(en[i] / en.mean()):+.0f} dB, GR low {gl[min(len(gl) - 1, int(i * B / hop))]:.1f})' for i in sorted(top)))
