"""Plan16 L step 1: time series of core v1.5 silence-voice wrong energy (all causes, stem-aware) for T25 and T26.
Re-uses plan16/V/v_run.one_song unchanged; only captures the component layers that render_multi returns.
usage: ../D/runpy.sh ../L/score.py  -> L/sil_series.npz   (3 kHz series y_sil(t)^2, input-time axis i/3000)"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V')
import numpy as np
import v_run as V
import dcommon as DC

CAP = {}
_orig = V.render_multi


def patched(voices, dur_s, fn, ncomp):
    Y = _orig(voices, dur_s, fn, ncomp)
    CAP['Y'] = Y.copy()
    return Y


V.render_multi = patched
out = {}
for key in ('Track00025', 'Track00026'):
    CAP.clear()
    k, o, _ = V.one_song(key)
    Y = CAP['Y']
    ysil = Y[3:].sum(0)
    out[key + '_ysil'] = ysil.astype(np.float64)
    out[key + '_ytotal_wrong'] = Y[2:].sum(0).astype(np.float64)
    print(key, 'E_sil (this file)', float(np.sum(ysil[DC.I_MIN:] ** 2)), 'one_song E_sil', o['E_sil'], 'nobass', o['nobass'], flush=True)
np.savez_compressed('/home/ksysh/r3a-dev/plan16/L/sil_series.npz', **out)
print('saved')
