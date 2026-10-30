"""Perceived timing: the files are sample-aligned, but the R4-L layer has its own envelope. On the bare 100 Hz bass
(the input's attack is 8 ms, decay 350 ms), cycle-averaged 1 ms envelopes per band (full, 150-600 Hz, and the 400 Hz
partial alone) for P1, L6 and P1eq (P1 EQ-matched to L6): 50 % rise time, peak time, time to fall 10 dB below the
peak. A later peak or a slower fall of the 150-600 Hz part in L6 would shift where the note seems to land.
Usage: timing_layer.py <lib>"""
import ctypes as C, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, hilbert
import research_p1plus as RP
import test_engine as T
from vb_quality.stage_capture import StageCapture
FS = 48000; lib = RP.api(sys.argv[1]); lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
t = np.arange(9 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
def render(x, level=None, vb=1):
    x = np.stack([x, x], 1).astype(np.float32); e = T.Engine(lib, FS, vb_on=vb, vb_algo=6); cap = None
    if level is not None:
        assert lib.pvb_set_r4_level(e.h, level) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
    y = e.process(x.copy(), block=256); lat = e.latency(); e.close(); return y[lat:lat + 8 * FS].mean(axis=1)
S = {'p1': render(bass), 'l6': render(bass, 6.)}
n = len(S['p1']); f = np.fft.rfftfreq(n, 1 / FS); P, V = np.fft.rfft(S['p1']), np.fft.rfft(S['l6'])
kk = np.arange(1, 9); g = np.array([10 * np.log10(np.sum(np.abs(V[np.abs(f - 100 * k) < 3]) ** 2) / np.sum(np.abs(P[np.abs(f - 100 * k) < 3]) ** 2)) for k in kk]); g[0] = 0
S['p1eq'] = np.fft.irfft(P * 10 ** (np.interp(f, 100 * kk, g, left=0, right=g[-1]) / 20), n)
dry = render(bass, vb=0); S['layer p1'] = S['p1'] - dry; S['layer l6'] = S['l6'] - dry
# the layer re the input partial at 300 Hz over the cycle (10 ms steps): where the layer overtakes the input
sos3 = butter(4, (285, 315), btype='band', fs=FS, output='sos')
cyc = lambda y: (np.abs(hilbert(sosfiltfilt(sos3, y))) ** 2)[:16 * FS // 2].reshape(16, -1)[1:].mean(axis=0).reshape(-1, 480).mean(axis=1)
cd, c1, c6 = cyc(dry), cyc(S['layer p1']), cyc(S['layer l6'])
print('300 Hz, layer re input partial (dB) per 20 ms of the note: P1 ' + ' '.join(f'{10 * np.log10(c1[i:i + 2].sum() / cd[i:i + 2].sum()):+.0f}' for i in range(0, 50, 2)))
print('                                                           L6 ' + ' '.join(f'{10 * np.log10(c6[i:i + 2].sum() / cd[i:i + 2].sum()):+.0f}' for i in range(0, 50, 2)))
bands = {'full': None, '150-600': (150, 600), '400 Hz': (385, 415), '300 Hz': (285, 315)}
Cy = FS // 2
for bn, b in bands.items():
    row = []
    for v, y in S.items():
        z = y if b is None else sosfiltfilt(butter(4, b, btype='band', fs=FS, output='sos'), y)
        e = np.abs(hilbert(z)) ** 2; c = e[:16 * Cy].reshape(16, Cy)[1:].mean(axis=0)
        c = np.convolve(c, np.ones(48) / 48, 'same')[::48]  # 1 ms
        pk = int(np.argmax(c[:400])); r50 = int(np.argmax(c >= .5 * c[pk])); fall = pk + int(np.argmax(c[pk:] <= c[pk] * .1))
        row.append(f'{v} rise50 {r50:3d} ms peak {pk:3d} ms fall-10dB {fall:3d} ms')
    print(f'{bn:8s} | ' + ' | '.join(row))
