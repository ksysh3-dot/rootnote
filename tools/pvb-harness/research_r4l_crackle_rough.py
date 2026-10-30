"""Second explanation for the crackle: roughness (fast envelope modulation, 20-200 Hz) of the boosted 150-600 Hz
harmonics, e.g. generated partials beating with the input's own. Per heard half after the phone model: the
roughness proxy of research_r4_roughness (1-ERB bands 150-1500 Hz, modulation weighted around 70 Hz, r = m^2 P^0.3)
total and its 150-600 Hz part, the median modulation depth m in 150-600 Hz bands, and the change re that input's P1.
Also the input's own partials: for the synthetic bass, the spectrum of P1 vs variant around k*f0 (k = 2..5), peak
and +-30 Hz side energy (beating shows as side lines). Usage: crackle_rough.py <listen dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert, resample_poly, firwin2, fftconvolve
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000; L = sys.argv[1]
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
erb = lambda f: 24.7 * (4.37 * f / 1000 + 1)
cams = np.arange(21.4 * np.log10(4.37 * .15 + 1), 21.4 * np.log10(4.37 * 1.5 + 1), 1.0)
fcs = (10 ** (cams / 21.4) - 1) / 4.37 * 1000
banks = [butter(2, [fc - erb(fc) / 2, fc + erb(fc) / 2], btype='band', fs=FS, output='sos') for fc in fcs]
EF = 1000; fm = np.fft.rfftfreq(200, 1 / EF); wm = np.where((fm >= 20) & (fm <= 200), 2 * (fm / 70) ** 2 / (1 + (fm / 70) ** 4), 0)
def rough(y):
    nf = len(y) // (FS // 5); R = np.zeros((nf, len(fcs))); M = np.zeros((nf, len(fcs)))
    for b, sos in enumerate(banks):
        env = resample_poly(np.abs(hilbert(sosfiltfilt(sos, y))), 1, 48)
        for f in range(nf):
            s = env[f * 200:(f + 1) * 200]
            if len(s) < 200: break
            mu = s.mean() + 1e-12; S = np.fft.rfft(s - mu); mod = np.sqrt(np.sum(np.abs(S * wm) ** 2) * 2) / 200
            M[f, b] = mod / mu; R[f, b] = (mod / mu) ** 2 * (np.mean(s ** 2)) ** .3
    return R, M
lm = (fcs >= 150) & (fcs <= 600)
cases = [('T60', 'r4l/r4l_3_T60.wav', {'p1': 'B', 'L9': 'A'}, {'L9': 'clean'}),
         ('T60', 'r4l/r4l_4_T60.wav', {'p1': 'B', 'L6': 'A'}, {'L6': 'clean'}),
         ('LOGOFF', 'r4l/r4l_1_LOGOFF.wav', {'p1': 'A', 'L9': 'B'}, {'L9': 'CRACKLE'}),
         ('LOGOFF', 'r4l6/r4l6_2_LOGOFF.wav', {'p1': 'B', 'L6': 'A'}, {'L6': 'clean (nm)'}),
         ('LOGOFF', 'r4l6/r4l6_3_LOGOFF.wav', {'p1': 'A', 'L6p': 'B'}, {'L6p': 'clean (nm)'}),
         ('synth', 'r4l/r4l_5_synth.wav', {'p1': 'A', 'L9': 'B'}, {'L9': 'CRACKLE'}),
         ('synth', 'r4l6/r4l6_5_synth.wav', {'p1': 'B', 'L6': 'A'}, {'L6': 'CRACKLE'}),
         ('synth', 'r4l6/r4l6_4_synth.wav', {'p1': 'B', 'L6p': 'A'}, {'L6p': 'CRACKLE'})]
for src, fn, halves, lab in cases:
    x, _ = sf.read(f'{L}/{fn}'); y = {v: x[H[h]].mean(axis=1) for v, h in halves.items()}
    z = {v: phone(s) for v, s in y.items()}; RM = {v: rough(s) for v, s in z.items()}
    tot = {v: RM[v][0].sum(axis=1).mean() for v in z}; low = {v: RM[v][0][:, lm].sum(axis=1).mean() for v in z}
    md = {v: np.median(RM[v][1][:, lm]) for v in z}; p90 = {v: np.percentile(RM[v][0][:, lm].sum(axis=1), 90) for v in z}
    for v, l in lab.items():
        print(f'{src:6s} {v:4s} {l:11s} | rough total {100 * (tot[v] / tot["p1"] - 1):+5.0f} % | 150-600 mean {100 * (low[v] / low["p1"] - 1):+5.0f} % '
              f'p90 {100 * (p90[v] / p90["p1"] - 1):+5.0f} % | median mod depth 150-600 p1 {md["p1"]:.3f} -> {md[v]:.3f}')
    if src == 'synth':
        v = next(iter(lab)); n = 2 ** 19; w = np.hanning(len(y['p1']))
        sp = {k: np.abs(np.fft.rfft(s * w, n)) ** 2 for k, s in y.items()}; f = np.fft.rfftfreq(n, 1 / FS)
        lo = (f > 80) & (f < 130); f0 = f[lo][np.argmax(sp['p1'][lo])]
        print(f'   synth f0 {f0:.2f} Hz; per k: P1 / {v} peak dB, side (+-3..30 Hz) re peak dB')
        for k in range(2, 6):
            for nm in ('p1', v):
                s = sp[nm]; c = (np.abs(f - k * f0) < 1.5); sd = (np.abs(f - k * f0) > 3) & (np.abs(f - k * f0) < 30)
                print(f'     k{k} {nm:4s} peak {10 * np.log10(s[c].sum()):6.1f} side {10 * np.log10(s[sd].sum() / s[c].sum()):6.1f}', end='')
            print()
