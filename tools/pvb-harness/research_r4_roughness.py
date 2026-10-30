"""Roughness of the app output (simplified, Daniel & Weber style), to test the hypothesis that the round-14 noise of a
flat upper roll-off on LOGOFF is roughness from unresolved high harmonics (spacing f0 < one auditory filter).
Signal: app chain at defaults (input clipped to +-1), optional phone weighting (4th-order high-pass at --phone-hz).
Bank: 1-ERB-wide 4th-order Butterworth band-passes, one per ERB step, centres 150-1500 Hz. Per band: Hilbert envelope
at 1 kHz, modulation 20-200 Hz weighted by w(fm) = 2 (fm/70)^2 / (1 + (fm/70)^4) (peak at 70 Hz), modulation depth m =
rms(weighted envelope modulation) / mean envelope, per 200 ms frame; specific roughness r = m^2 * (band power)^0.3
(relative units). Reports the total over bands (mean over frames) and the 200-600 Hz part, at hits / rest, for each
variant, plus the change re the layer-off output. Usage: roughness.py <song> <lib> [--start --dur --phone-hz]
Variants: off, default, 12dB (dev roll-off -12), flat (-24); --pairs 'name:key=value,...;...' adds others."""
import argparse, json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt, hilbert
import test_engine as T

ap = argparse.ArgumentParser(); ap.add_argument('song'); ap.add_argument('lib')
ap.add_argument('--start', type=float, default=0); ap.add_argument('--dur', type=float, default=0)
ap.add_argument('--phone-hz', type=float, default=300); ap.add_argument('--pairs', default='')
a = ap.parse_args(); FS = 48000
T.P.update(dict(DEV_ON=33, D_OUT_HI_HZ=37, D_ROLLOFF_DB_OCT=42))
x, fs = sf.read(a.song, always_2d=True)
if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)      # the engine processes interleaved stereo
x = np.clip(resample_poly(x, 160, 147, axis=0) if fs == 44100 else x, -1, 1).astype(np.float32)
if a.dur: x = x[int(a.start * FS):int((a.start + a.dur) * FS)]
mono = x.astype(float).mean(axis=1)
lo = sosfiltfilt(butter(4, [30, 150], btype='band', fs=FS, output='sos'), mono)
e = lo ** 2; k5, k150 = int(.005 * FS), int(.15 * FS)
fast = np.convolve(e, np.ones(k5) / k5, 'same'); slow = np.convolve(e, np.ones(k150) / k150, 'same')
ratio = 10 * np.log10((fast + 1e-20) / (np.r_[slow[:k150], slow[:-k150]] + 1e-20))
on = []; i = 0
while i < len(ratio):
    if ratio[i] > 8 and fast[i] > 1e-4 * fast.max(): on.append(i / FS); i += k150
    else: i += 1
on = np.array(on)
lib = T.load_lib(a.lib)
VAR = [('off', dict(vb_on=0)), ('default', dict(vb_on=1, vb_algo=6)), ('12dB', dict(vb_on=1, vb_algo=6, dev_on=1, d_rolloff_db_oct=-12)),
       ('flat', dict(vb_on=1, vb_algo=6, dev_on=1, d_rolloff_db_oct=-24))]
for spec in filter(None, a.pairs.split(';')):
    nm, kv = spec.split(':'); VAR.append((nm, {k: float(v) for k, v in (p.split('=') for p in kv.split(','))}))
erb = lambda f: 24.7 * (4.37 * f / 1000 + 1)
cams = np.arange(21.4 * np.log10(4.37 * .15 + 1), 21.4 * np.log10(4.37 * 1.5 + 1), 1.0)
fcs = (10 ** (cams / 21.4) - 1) / 4.37 * 1000
banks = [butter(2, [fc - erb(fc) / 2, fc + erb(fc) / 2], btype='band', fs=FS, output='sos') for fc in fcs]   # order 4 band-pass
phone = butter(4, a.phone_hz, btype='high', fs=FS, output='sos') if a.phone_hz > 0 else None
if a.phone_hz < 0:      # --phone-hz -1: the S26 Ultra model (study/phone_model.py): its dynamics processor, then speaker+room
    import sys as _s; _s.path.insert(0, 'study'); import phone_model as PM
    from scipy.signal import firwin2, fftconvolve
    fgrid = np.r_[0, 40, 80, PM.SPEAKER_HZ, 20000, FS / 2]; gdb = np.r_[-40, -40, -30, PM.SPEAKER_DB, -30, -40]
    FIR = firwin2(4097, fgrid / (FS / 2), 10 ** (gdb / 20))
    class _Ph:
        pass
    def _phone(y):
        z, _ = PM.drc(np.stack([y, y], 1), FS); return fftconvolve(z.mean(axis=1), FIR, 'same')
EF = 1000; fm = np.fft.rfftfreq(200, 1 / EF); wm = np.where((fm >= 20) & (fm <= 200), 2 * (fm / 70) ** 2 / (1 + (fm / 70) ** 4), 0)
def rough(y):
    if phone is not None: y = sosfiltfilt(phone, y)
    elif a.phone_hz < 0: y = _phone(y)
    nf = len(y) // (FS // 5); R = np.zeros((nf, len(fcs)))
    for b, sos in enumerate(banks):
        env = resample_poly(np.abs(hilbert(sosfiltfilt(sos, y))), 1, 48)
        for f in range(nf):
            s = env[f * 200:(f + 1) * 200]
            if len(s) < 200: break
            mu = s.mean() + 1e-12; S = np.fft.rfft(s - mu); mod = np.sqrt(np.sum(np.abs(S * wm) ** 2) * 2) / 200
            R[f, b] = (mod / mu) ** 2 * (np.mean(s ** 2)) ** .3
    return R
res = {}; base = None
tf = (np.arange(10 ** 6) * .2 + .1)
import research_p1plus as RP
from vb_quality.stage_capture import StageCapture
plib = RP.api(a.lib)
if a.phone_hz < 0:
    _phone_only = _phone
def bass_db(y):
    """energy 150-700 Hz after the phone model (the audible bass harmonics), dB"""
    z = _phone_only(y) if a.phone_hz < 0 else y
    S = np.abs(np.fft.rfft(z)) ** 2; fr = np.fft.rfftfreq(len(z), 1 / FS)
    return 10 * np.log10(S[(fr >= 150) & (fr < 700)].sum() + 1e-30), 10 * np.log10(S.sum() + 1e-30)
for name, kw in VAR:
    kw = dict(kw); stage = int(kw.pop('stage', 0)); r4 = [kw.pop(k, None) for k in ('r4hold', 'r4floor', 'r4tau')]
    eng = T.Engine(plib, FS, **kw)
    if r4[0] is not None:
        import ctypes as _c
        plib.pvb_set_r4_research.argtypes = [_c.c_void_p, _c.c_int, _c.c_double, _c.c_double]
        assert plib.pvb_set_r4_research(eng.h, int(r4[0]), float(r4[1]), float(r4[2])) == 1
    cap = StageCapture(plib, eng.h, stage, int(len(x) / FS * 3000) + 16) if stage else None
    y = eng.process(x, block=256); lat = eng.latency(); eng.close()
    y = y[lat:].astype(float).mean(axis=1)
    R = rough(y); nf = len(R); t = tf[:nf]
    hit = np.array([np.any((tc - on >= -.05) & (tc - on < .3)) for tc in t]) if len(on) else np.zeros(nf, bool)
    mid = (fcs >= 200) & (fcs <= 600)
    out = dict(total=float(R.sum(1).mean()), mid=float(R[:, mid].sum(1).mean()),
               total_hits=float(R[hit].sum(1).mean()) if hit.any() else None, total_rest=float(R[~hit].sum(1).mean()),
               mid_hits=float(R[hit][:, mid].sum(1).mean()) if hit.any() else None, mid_rest=float(R[~hit][:, mid].sum(1).mean()))
    bd, td = bass_db(y); out['bass_band_db'] = bd; out['total_db'] = td
    if base is None: base = out
    out['bass_band_change_db'] = round(bd - base['bass_band_db'], 2); out['total_change_db'] = round(td - base['total_db'], 2)
    out['change_pct'] = {k: round(100 * (out[k] / base[k] - 1), 1) for k in out if isinstance(out[k], float) and base.get(k)}
    res[name] = out; print(name, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}), flush=True)
