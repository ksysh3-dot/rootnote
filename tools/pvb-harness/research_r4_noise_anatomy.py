"""What made the flat upper roll-off noisy on LOGOFF (listening round 14: '+24 dB/oct = 거울미로 noise')?
Research renders (same tracks, only the harmonic weights differ) at the default 24 dB/oct and with developer values
(roll-off offset -24 = flat, -12 = 12 dB/oct). Per 42.7 ms frame (hop 21 ms) on the input time axis:
- each live strong track j (frequency f_j, frame median) and each partial k = 2..8 with k f_j in 150-1000 Hz: joint
  least-squares cos/sin fit of the layer at all k f_j; 'clean' = fitted energy, 'dirty' = residual (energy that is
  not a steady sinusoid at the generator's own partial frequencies: AM/FM sidebands, onsets, grain edges), per band.
- added partial energy (variant - default) by harmonic order k.
- beating: for each partial, the nearest native peak of the input mix within 6 % of k f_j (zero-padded FFT); the
  mismatch |peak - k f_j| (Hz) is the beat rate when both sound; 'rough' = mismatch 15-150 Hz, weighted by the
  smaller of the two amplitudes (layer partial, native peak).
Split into frames within 300 ms after a low-band hit and the rest. Input clipped to +-1.
Usage: noise_anatomy.py <song> <lib> [--start s --dur s]"""
import argparse, json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt
import research_p1plus as P
import test_engine as T
import test_harmonic_continuity as H

ap = argparse.ArgumentParser(); ap.add_argument('song'); ap.add_argument('lib')
ap.add_argument('--start', type=float, default=0); ap.add_argument('--dur', type=float, default=0)
a = ap.parse_args()
FS, C = 48000, 3000
T.P.update(dict(DEV_ON=33, D_ROLLOFF_DB_OCT=42))
x, fs = sf.read(a.song, always_2d=True)
x48 = np.clip(resample_poly(x, 160, 147, axis=0) if fs == 44100 else x, -1, 1).astype(np.float32)
if a.dur: x48 = x48[int(a.start * FS):int((a.start + a.dur) * FS)]
mono = x48.astype(float).mean(axis=1)
lo = sosfiltfilt(butter(4, [30, 150], btype='band', fs=FS, output='sos'), mono)
e = lo ** 2; k5, k150 = int(.005 * FS), int(.15 * FS)
fast = np.convolve(e, np.ones(k5) / k5, 'same'); slow = np.convolve(e, np.ones(k150) / k150, 'same')
ratio = 10 * np.log10((fast + 1e-20) / (np.r_[slow[:k150], slow[:-k150]] + 1e-20))
on = []; i = 0
while i < len(ratio):
    if ratio[i] > 8 and fast[i] > 1e-4 * fast.max(): on.append(i / FS); i += k150
    else: i += 1
on = np.array(on)
zm = resample_poly(mono, 1, 16)
lib = P.api(a.lib)
Orig = T.Engine
def render(extra):
    P.T.Engine = lambda l, f, **kw: Orig(l, f, **{**kw, **extra})
    try: r = P.render(lib, x48, FS, 0, stage_flags=0)
    finally: P.T.Engine = Orig
    lay = resample_poly(r['stem'][r['latency']:].astype(float).mean(axis=1), 1, 16)
    return lay, H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / C
VAR = [('default', {}), ('12dB', dict(dev_on=1, d_rolloff_db_oct=-12)), ('flat', dict(dev_on=1, d_rolloff_db_oct=-24))]
R = {name: render(kw) for name, kw in VAR}
_, tr, tin = R['default']
N, HOP = 128, 64; t_ax = np.arange(N) / C; win = np.hanning(N)
BANDS = ((150, 250), (250, 400), (400, 600), (600, 1000))
def bandpow(sig):
    S = np.abs(np.fft.rfft(sig * win, 1024)) ** 2; fr = np.fft.rfftfreq(1024, 1 / C)
    return np.array([S[(fr >= lo_) & (fr < hi_)].sum() for lo_, hi_ in BANDS])
acc = {(v, h): dict(clean=np.zeros(4), dirty=np.zeros(4), byk=np.zeros(9), frames=0) for v, _ in VAR for h in (0, 1)}
rough = {(v, h): np.zeros(2) for v, _ in VAR for h in (0, 1)}       # rough-weighted amplitude, total weighted amplitude
L = min(len(R[v][0]) for v, _ in VAR)
for s in range(int(1.0 * C), L - N, HOP):
    t0 = s / C; tc = t0 + N / 2 / C
    hit = int(len(on) and np.any((tc - on >= 0) & (tc - on < .3)))
    sel = np.where((tin >= t0) & (tin < t0 + N / C))[0]
    if not len(sel): continue
    fr_ = tr[sel, :, 2]; am = tr[sel, :, 4]; st = tr[sel, :, 1]
    live = (st > 0) & (st < 5) & (am > 0)
    fj = []
    for col in range(tr.shape[1]):
        ok = live[:, col]
        if ok.mean() > .5:
            amax = am[sel - sel[0], :][live].max() if live.any() else 0
            if np.median(am[ok, col]) >= .1 * amax: fj.append(float(np.median(fr_[ok, col])))
    parts = [(f, k) for f in fj for k in range(2, 9) if 150 <= k * f <= 1000]
    if not parts: continue
    A = np.column_stack([g(2 * np.pi * k * f * t_ax) for f, k in parts for g in (np.cos, np.sin)])
    Sm = np.abs(np.fft.rfft(zm[s:s + N] * win, 8192)); frm = np.fft.rfftfreq(8192, 1 / C)
    for v, _ in VAR:
        y = R[v][0][s:s + N]; coef, *_ = np.linalg.lstsq(A, y, rcond=None); fit = A @ coef
        d = acc[(v, hit)]; d['frames'] += 1
        d['clean'] += bandpow(fit); d['dirty'] += bandpow(y - fit)
        amp = np.hypot(coef[0::2], coef[1::2])
        for (f, k), aa in zip(parts, amp):
            d['byk'][k] += aa ** 2
            m = np.abs(frm - k * f) <= .06 * k * f
            if not m.any(): continue
            jj = np.argmax(np.where(m, Sm, 0)); nat = Sm[jj] * 2 / win.sum(); mis = abs(frm[jj] - k * f)
            wgt = min(aa, nat); rough[(v, hit)] += [wgt * (15 <= mis <= 150), wgt]
out = {}
for v, _ in VAR:
    for h in (0, 1):
        d = acc[(v, h)]; key = f'{v}_{"hits" if h else "rest"}'
        db = lambda z: [round(float(10 * np.log10(q / d['frames'] + 1e-30)), 1) for q in z]
        out[key] = dict(frames=d['frames'], clean_db_bands=db(d['clean']), dirty_db_bands=db(d['dirty']),
                        dirty_minus_clean_db=[round(float(10 * np.log10((dd + 1e-30) / (cc + 1e-30))), 1) for dd, cc in zip(d['dirty'], d['clean'])],
                        partial_db_by_k2_8=db(d['byk'][2:]), rough_share=round(float(rough[(v, h)][0] / max(rough[(v, h)][1], 1e-30)), 3))
        print(key, json.dumps(out[key]), flush=True)
