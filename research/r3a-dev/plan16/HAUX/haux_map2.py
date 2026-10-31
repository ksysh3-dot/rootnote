"""time-axis check 2 (validation only): average W40 comb energy (k = 2..6 at f_MIDI x tp... = segment f) around MIDI note starts, T = s + delta; the 50 % rise crossing delta shows the audio-vs-MIDI(T axis) offset."""
import os, sys
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
import kcommon as K
from kcommon import *
import haux_lib as H
DEL = np.arange(-48, 81, 5.333) / 1000.0
allc = []
for key in ('Track00060', 'Track00001', 'Track00012', 'Track00005', 'Track00020', 'Track00040'):
    ctx = K.SongCtx(key, probe_nobass=False)
    x = np.asarray(DATA.audio(key), float); x = x.mean(1) if x.ndim == 2 else x
    curves = []
    segs = ctx.segs
    for n, sg in enumerate(segs):
        if sg['s'] < 0.3 or sg['e'] - sg['s'] < 0.25:
            continue
        # isolated onset: previous segment ended >= 80 ms before
        if n > 0 and sg['s'] - segs[n - 1]['e'] < 0.08:
            continue
        w = H.hann(H.WINLEN[40])
        e = []
        for d in DEL:
            seg = H.segment(x, int(round((sg['s'] + d) * H.FS)), H.WINLEN[40])
            E, Ei, a = H.comb_fit(seg, w, sg['f'])
            e.append(np.nanmean(E[:5]))
        e = np.array(e)
        pre = np.median(e[DEL < -0.02]) if (DEL < -0.02).sum() else e[0]
        post = np.median(e[DEL > 0.06])
        if post > 4 * pre and post > 0:
            curves.append((e - pre) / (post - pre))
    if curves:
        c = np.median(np.array(curves), 0)
        cross = DEL[np.argmax(c >= 0.5)]
        print(key, 'notes', len(curves), '50% rise at delta', round(cross * 1000, 1), 'ms')
        allc += curves
c = np.median(np.array(allc), 0)
print('pooled notes', len(allc), '50% rise at delta', round(DEL[np.argmax(c >= 0.5)] * 1000, 1), 'ms; curve', ' '.join(f'{d * 1000:.0f}:{v:.2f}' for d, v in zip(DEL, c)))
