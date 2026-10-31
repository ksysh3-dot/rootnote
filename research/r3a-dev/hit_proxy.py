"""Blind-safe proxy at the biggest hit near 4 s of each half of the R4 noise pair files (LOGOFF 40-48 s, layer +6 dB).
The user's listening criterion (2026-10-30, stated before listening): judge only the change on the biggest hit around 4 s.
The hit is found on (A+B)/2 (30-150 Hz, 10 ms RMS, 3-5 s), so both halves use the same time. Per half: phone model
(S26 Ultra DRC + speaker curve), then the ERB-bank roughness of research_r4_roughness.py in -50..+300 ms around the hit
(total 150-1500 Hz and the 200-600 Hz part) and band energies there. Writes the JSON without printing the values (so the
listener is not primed) and prints its SHA-256 and the hit times. Usage: hit_proxy.py <out.json> <files...>"""
import hashlib, json, sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert, resample_poly, firwin2, fftconvolve
sys.path.insert(0, 'study'); import phone_model as PM
FS = 48000; EF = 1000; N = 350
fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
def phone(y):
    z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
erb = lambda f: 24.7 * (4.37 * f / 1000 + 1)
cams = np.arange(21.4 * np.log10(4.37 * .15 + 1), 21.4 * np.log10(4.37 * 1.5 + 1), 1.0)
fcs = (10 ** (cams / 21.4) - 1) / 4.37 * 1000
banks = [butter(2, [fc - erb(fc) / 2, fc + erb(fc) / 2], btype='band', fs=FS, output='sos') for fc in fcs]
fm = np.fft.rfftfreq(N, 1 / EF); wm = np.where((fm >= 20) & (fm <= 200), 2 * (fm / 70) ** 2 / (1 + (fm / 70) ** 4), 0)
mid = (fcs >= 200) & (fcs <= 600)
low = butter(4, [30, 150], btype='band', fs=FS, output='sos')
def measure(y, t):
    z = phone(y); i0 = int((t - .05) * EF); R = np.zeros(len(fcs))
    for b, sos in enumerate(banks):
        s = resample_poly(np.abs(hilbert(sosfiltfilt(sos, z))), 1, 48)[i0:i0 + N]
        mu = s.mean() + 1e-12; S = np.fft.rfft(s - mu); mod = np.sqrt(np.sum(np.abs(S * wm) ** 2) * 2) / N
        R[b] = (mod / mu) ** 2 * np.mean(s ** 2) ** .3
    w = z[int((t - .05) * FS):int((t + .3) * FS)]; P = np.abs(np.fft.rfft(w)) ** 2; fr = np.fft.rfftfreq(len(w), 1 / FS)
    band = lambda lo, hi: float(10 * np.log10(P[(fr >= lo) & (fr < hi)].sum() + 1e-30))
    return dict(rough_total=float(R.sum()), rough_200_600=float(R[mid].sum()), e150_600_db=band(150, 600),
                e600_2k_db=band(600, 2000), e2k_6k_db=band(2000, 6000))
out = {}
for p in sys.argv[2:]:
    x, fs = sf.read(p); assert fs == FS; x = x.mean(axis=1); a, b = x[:8 * FS], x[9 * FS:17 * FS]
    rms = lambda y: np.sqrt(np.convolve(y ** 2, np.ones(480) / 480, 'same'))
    el, ef = rms(sosfiltfilt(low, (a + b) / 2)), rms((a + b) / 2)
    # the full-band maximum right after the 3.5-4.1 s gap (the entry), and the 30-150 Hz maximum in 3-5 s
    tf = (int(3.8 * FS) + int(np.argmax(ef[int(3.8 * FS):int(4.4 * FS)]))) / FS; tl = (3 * FS + int(np.argmax(el[3 * FS:5 * FS]))) / FS
    rec = {}
    for nm, t in (('entry_full', tf), ('max_low', tl)):
        rec[nm] = dict(hit_t=round(t, 3), A=measure(a, t), B=measure(b, t))
        print(p.split('/')[-1], nm, 'hit at', round(t, 3), 's (B half:', round(t + 9, 3), 's)', flush=True)
    out[p.replace('\\', '/').split('/')[-1]] = rec
blob = json.dumps(out, sort_keys=True).encode(); open(sys.argv[1], 'wb').write(blob)
print('proxy sha256', hashlib.sha256(blob).hexdigest())
