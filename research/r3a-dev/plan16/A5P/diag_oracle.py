"""Fidelity check of the offline rebuild (oracle_p.py): in the window Apparition 52-54 s (row b0p0), compare rendered layer vs rebuilt layer (k=2,3 from the trace through x16 + output filter):
alignment by xcorr in the 150-600 band (+-20 ms), gain by least squares in 150-600, then lo (20-150) and mid energies of rendered, rebuilt*g and residual."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
import oracle_p as O
import p_primary as P
from scipy.signal import sosfiltfilt
label = sys.argv[1]; sk = 'app'
lay, tr = P.render_song(P.read_song(P.SONG_IDX[sk]), label)
y = O.rebuild(tr, 'raw', 1)
import os
if os.environ.get('NOFILT'):
    O.to_layer = lambda y: O.resample_poly(y, 16, 1)
y48 = O.to_layer(y)
ts = O.CA.hop_time(tr['hop'][:, 0])[1]; ih = tr['hop'][:, 0].astype(np.int64)
for (s, t0, t1) in [w for w in P.WINDOWS if w[0] == sk][:3]:
    sel = np.where((ts >= t0) & (ts < t1))[0]
    n0 = 16 * ih[sel.min()]; n1 = 16 * (ih[sel.max()] + 16)
    r = lay[int(t0 * P.FS):int(t1 * P.FS)]
    rec = y48[n0:n1][:len(r)]
    rm = sosfiltfilt(P.SOS_MID, lay)[int(t0 * P.FS) - 2000:int(t1 * P.FS) + 2000]
    cm = sosfiltfilt(P.SOS_MID, y48)
    best = None
    for lag in range(-960, 961, 8):
        a = cm[n0 + lag:n0 + lag + len(r)]
        c = np.dot(a, rm[2000:2000 + len(r)]) / np.sqrt(np.dot(a, a) * np.dot(rm[2000:2000 + len(r)], rm[2000:2000 + len(r)]) + 1e-30)
        if best is None or c > best[0]:
            best = (c, lag)
    c, lag = best
    rec = y48[n0 + lag:n0 + lag + len(r)]
    rmid = sosfiltfilt(P.SOS_MID, lay)[int(t0 * P.FS):int(t1 * P.FS)]; rlo = sosfiltfilt(P.SOS_LO, lay)[int(t0 * P.FS):int(t1 * P.FS)]
    cmid = cm[n0 + lag:n0 + lag + len(r)]; clo = sosfiltfilt(P.SOS_LO, y48)[n0 + lag:n0 + lag + len(r)]
    g = np.dot(rmid, cmid) / np.dot(cmid, cmid)
    db = lambda x: 10 * np.log10(np.mean(x ** 2) + 1e-30)
    print(f'{s}{t0:g}: mid xcorr {c:.3f} lag {lag/48:.1f} ms gain {g:.3f} | mid: rendered {db(rmid):.1f} rebuilt*g {db(g*cmid):.1f} resid {db(rmid-g*cmid):.1f} | lo: rendered {db(rlo):.1f} rebuilt*g {db(g*clo):.1f} resid {db(rlo-g*clo):.1f}', flush=True)
