"""Is the layer's non-steady ('dirty') energy made by the generator or by the music? Same frame fit as
noise_anatomy.py (42.7 ms, joint LS at the generator's own k f, residual = dirty), on known signals, default vs flat
roll-off: steady sines 45 / 100 / 125 Hz, a 100 Hz pluck (8 ms attack, 250 ms decay, every 0.5 s), a 100 Hz note with
5 Hz / 20 cent vibrato, and 45 Hz + a kick every 0.5 s. Prints dirty - clean (dB) in 150-250 / 250-400 / 400-600 Hz.
Usage: purity_synth.py <lib>"""
import sys
import numpy as np
from scipy.signal import resample_poly
import research_p1plus as P
import test_engine as T
import test_harmonic_continuity as H
FS, C = 48000, 3000
T.P.update(dict(DEV_ON=33, D_ROLLOFF_DB_OCT=42))
lib = P.api(sys.argv[1]); Orig = T.Engine
t = np.arange(8 * FS) / FS
def sig(name):
    if name.startswith('sine'): return np.sin(2 * np.pi * float(name[4:]) * t)
    if name == 'pluck100':
        u = t % .5; return np.minimum(u / .008, 1) * np.exp(-u / .25) * np.sin(2 * np.pi * 100 * t)
    if name == 'vibrato100':
        f = 100 * 2 ** (20 / 1200 * np.sin(2 * np.pi * 5 * t)); return np.sin(2 * np.pi * np.cumsum(f) / FS)
    if name == 'sub45_kick':
        u = t % .5; kick = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(45 + 15 * np.exp(-u / .03)) / FS)
        return .6 * np.sin(2 * np.pi * 45 * t) + .6 * kick
def render(x, extra):
    P.T.Engine = lambda l, f, **kw: Orig(l, f, **{**kw, **extra})
    try: r = P.render(lib, np.stack([x, x], 1).astype(np.float32), FS, 0, stage_flags=0)
    finally: P.T.Engine = Orig
    return resample_poly(r['stem'][r['latency']:].astype(float).mean(axis=1), 1, 16), H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / C
N, HOP = 128, 64; ta = np.arange(N) / C; win = np.hanning(N); BANDS = ((150, 250), (250, 400), (400, 600))
def bp(s):
    S = np.abs(np.fft.rfft(s * win, 1024)) ** 2; fr = np.fft.rfftfreq(1024, 1 / C); return np.array([S[(fr >= a) & (fr < b)].sum() for a, b in BANDS])
for name in ('sine45', 'sine100', 'sine125', 'pluck100', 'vibrato100', 'sub45_kick'):
    x = 10 ** (-12 / 20) * sig(name) / np.abs(sig(name)).max()
    line = []
    for v, kw in (('default', {}), ('flat', dict(dev_on=1, d_rolloff_db_oct=-24))):
        lay, tr, tin = render(x, kw); cl = np.zeros(3); di = np.zeros(3)
        for s in range(2 * C, len(lay) - N, HOP):
            sel = np.where((tin >= s / C) & (tin < (s + N) / C))[0]
            if not len(sel): continue
            st = tr[sel, :, 1]; am = tr[sel, :, 4]; live = (st > 0) & (st < 5) & (am > 0)
            fj = [float(np.median(tr[sel, c, 2][live[:, c]])) for c in range(tr.shape[1]) if live[:, c].mean() > .5]
            parts = [(f, k) for f in fj for k in range(2, 9) if 150 <= k * f <= 1000]
            if not parts: continue
            A = np.column_stack([g(2 * np.pi * k * f * ta) for f, k in parts for g in (np.cos, np.sin)])
            y = lay[s:s + N]; fit = A @ np.linalg.lstsq(A, y, rcond=None)[0]; cl += bp(fit); di += bp(y - fit)
        line.append(f"{v}: clean {[round(float(10*np.log10(c+1e-30)),1) for c in cl]} dirty-clean {[round(float(10*np.log10((d+1e-30)/(c+1e-30))),1) for d, c in zip(di, cl)]}")
    print(f'{name:11s} ' + ' | '.join(line), flush=True)
