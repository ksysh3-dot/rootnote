"""Locate the layer dip after a bass note change (55 -> 45 Hz, with and without a kick): 20 ms moving RMS (dB) of the
stage columns raw_grain, tonal_after_gain, pre_filter, post_filter, every 5 ms around the change, and the layer stem's
150-400 Hz band on the same axis. Also the traced track frequency. Usage: synth_stage2.py <lib>"""
import sys
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as P
import test_harmonic_continuity as H
from vb_quality.stage_capture import INDEX as SI

FS = 48000; lib = P.api(sys.argv[1])
t = np.arange(FS) / FS
def bass(fa, fb):
    f = np.where(t < .5, fa, fb).astype(float)
    a = np.minimum(t / .005, 1) * np.minimum(1, np.maximum(0, (.98 - t) / .02))
    return a * np.sin(2 * np.pi * np.cumsum(f) / FS)
tk = np.maximum(t - .5, 0)
kick = (t >= .5) * np.exp(-tk / .12) * np.sin(2 * np.pi * np.cumsum(45 + 15 * np.exp(-tk / .03)) / FS)
k = 60
mrms = lambda v: 10 * np.log10(np.convolve(v ** 2, np.ones(k) / k, 'same') + 1e-24)
for name, one in (('change_55_45', bass(55, 45)), ('change_55_45_kick', .7 * bass(55, 45) + .7 * kick)):
    x = np.tile(one, 6); x = (10 ** (-12 / 20) * x / np.abs(x).max()).astype(np.float32); x = np.stack([x, x], 1)
    r = P.render(lib, x, FS, 0, capture=True, stage_flags=0)
    S = r['stages']; lat = r['latency'] / FS
    lay = r['stem'].astype(float).mean(axis=1)
    bandE = 10 * np.log10(np.convolve(sosfiltfilt(butter(4, [150, 400], btype='band', fs=FS, output='sos'), lay) ** 2,
                                      np.ones(960) / 960, 'same') + 1e-24)
    cols = {c: mrms(S[:, SI[c]]) for c in ('raw_grain', 'tonal_after_gain', 'pre_filter', 'post_filter')}
    rows = r['rows']; tr = H.tracks(rows); th = (H.core_indices(rows).astype(float) - 383) / 3000
    c0 = 4.5 + lat
    print(f'== {name}: ms  rawG tonal pre post | stem150-400 | track f0 (Hz) per row')
    for ms in range(-30, 125, 5):
        i = int((c0 + ms / 1000) * 3000); j = int((c0 + ms / 1000) * FS)
        h = np.where(np.abs(th - (c0 + ms / 1000)) < .0025)[0]
        f0 = '' if not len(h) else ' '.join(f'{v:.1f}' for v in np.atleast_1d(tr[h[0], :, 2] if tr.ndim == 3 and tr.shape[2] > 2 else []) if v > 0)
        print(f'{ms:5d} ' + ' '.join(f'{cols[c][i]:6.1f}' for c in cols) + f' | {bandE[j]:6.1f} | {f0}')
