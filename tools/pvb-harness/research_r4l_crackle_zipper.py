"""Third explanation: gain switching ("zipper"). The R4-L gain is all or nothing per track (2x/3x-of-a-lower-track test,
onset blend); if it flips block by block, the boosted partials step by up to 6-9 dB. Per case: narrow bands around the
synthetic bass partials (k = 2, 3, 4 at f0 = 100 Hz) or, for songs, 150-300 / 300-600 Hz; 2 ms Hilbert envelopes of
variant and P1, their ratio in dB over time (where P1 is within 30 dB of its max): spread (p10..p90), the share of
2 ms steps where the ratio jumps more than 1.5 dB within 4 ms, and the strongest 50 ms modulation of the ratio.
Usage: crackle_zipper.py <listen dir>"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, hilbert
FS = 48000; L = sys.argv[1]
H = dict(A=slice(0, 8 * FS), B=slice(9 * FS, 17 * FS))
cases = [('T60 L9 clean', 'r4l/r4l_3_T60.wav', 'A', 'B', ((150, 300), (300, 600))),
         ('T60 L6 clean', 'r4l/r4l_4_T60.wav', 'A', 'B', ((150, 300), (300, 600))),
         ('LOGOFF L6 clean', 'r4l6/r4l6_2_LOGOFF.wav', 'A', 'B', ((150, 300), (300, 600))),
         ('LOGOFF L9 CRACKLE', 'r4l/r4l_1_LOGOFF.wav', 'B', 'A', ((150, 300), (300, 600))),
         ('synth L6p CRACKLE', 'r4l6/r4l6_4_synth.wav', 'A', 'B', ((185, 215), (285, 315), (385, 415))),
         ('synth L6 CRACKLE', 'r4l6/r4l6_5_synth.wav', 'A', 'B', ((185, 215), (285, 315), (385, 415))),
         ('synth L9 CRACKLE', 'r4l/r4l_5_synth.wav', 'B', 'A', ((185, 215), (285, 315), (385, 415)))]
D = 96  # 2 ms
for nm, fn, hv, hp, bands in cases:
    x, _ = sf.read(f'{L}/{fn}'); v, p = x[H[hv]].mean(axis=1), x[H[hp]].mean(axis=1)
    out = []
    for lo, hi in bands:
        sos = butter(4, [lo, hi], btype='band', fs=FS, output='sos')
        ev = np.abs(hilbert(sosfiltfilt(sos, v)))[::D]; ep = np.abs(hilbert(sosfiltfilt(sos, p)))[::D]
        ok = ep > ep.max() * 10 ** (-30 / 20); r = 20 * np.log10((ev + 1e-12) / (ep + 1e-12))
        jump = np.abs(r[2:] - r[:-2]) > 1.5; okj = ok[2:] & ok[:-2]
        w = 25; rr = np.where(ok, r, np.nan); seg = [rr[i:i + w] for i in range(0, len(rr) - w, w)]
        mod = max((np.nanmax(s) - np.nanmin(s)) for s in seg if np.sum(~np.isnan(s)) > w // 2)
        out.append(f'{lo}-{hi}: ratio p10/50/90 {np.percentile(r[ok], 10):+5.1f}/{np.percentile(r[ok], 50):+5.1f}/{np.percentile(r[ok], 90):+5.1f} '
                   f'jumps {100 * jump[okj].mean():4.1f} % max50ms {mod:4.1f}')
    print(f'{nm:18s} ' + ' | '.join(out))
