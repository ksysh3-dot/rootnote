"""Where does the layer lose the first ~30 ms after a kick that coincides with a bass note change? Stage capture
(3 kHz, layer time axis) around the change for 'same_48_kick' (no lag) and 'change_55_45_kick' (30 ms lag): per 10 ms,
RMS of selected_h, raw_grain, tonal_after_gain and mean of nominal_amplitude, env_a, env_p, applied_gain; plus the
number of live tracks and births in the trace rows. Usage: synth_stage.py <lib>"""
import sys
import numpy as np
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
for name, one in (('same_48_kick', .7 * bass(48, 48) + .7 * kick), ('change_55_45_kick', .7 * bass(55, 45) + .7 * kick),
                  ('change_55_45', bass(55, 45))):
    x = np.tile(one, 6); x = (10 ** (-12 / 20) * x / np.abs(x).max()).astype(np.float32); x = np.stack([x, x], 1)
    r = P.render(lib, x, FS, 0, capture=True, stage_flags=0)
    S = r['stages']; lat = r['latency'] / FS
    rows = r['rows']; tr = H.tracks(rows); th = (H.core_indices(rows).astype(float) - 383) / 3000
    live = (tr[:, :, 0] > 0).sum(axis=1) if tr.ndim == 3 else None
    births = (tr[:, :, 1] == 1).sum(axis=1)
    c0 = 4.5 + lat                                   # change at 4.5 s of the input, on the layer axis
    print(f'== {name}  (ms from change: selH rawG tonal | nomA envA envP gain | tracks births)')
    for ms in range(-20, 120, 10):
        s = slice(int((c0 + ms / 1000) * 3000), int((c0 + (ms + 10) / 1000) * 3000))
        rms = lambda c: 20 * np.log10(np.sqrt(np.mean(S[s, SI[c]] ** 2)) + 1e-12)
        mean = lambda c: float(np.mean(S[s, SI[c]]))
        h = (th >= c0 + ms / 1000) & (th < c0 + (ms + 10) / 1000)
        print(f'{ms:5d} {rms("selected_h"):7.1f} {rms("raw_grain"):7.1f} {rms("tonal_after_gain"):7.1f} | '
              f'{mean("nominal_amplitude"):.4f} {mean("env_a"):.4f} {mean("env_p"):.4f} {mean("applied_gain"):6.3f} | '
              f'{(live[h].mean() if live is not None and h.any() else -1):4.1f} {int(births[h].sum())}')
