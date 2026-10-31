"""Sign check of the layer high-pass phase compensation (19.7.1): steady tones, layer = out(vb 0 dB) - out(vb -120 dB) as V2.
For each k = 2, 3 (4): dphi = circular mean over 200 ms Hann frames (input time 0.7-3.5 s) of angle(zl_filter * conj(zl_unfiltered)) at k f0, where both renders use the same input.
Expected: comp 0 -> the filter's phase (and gain), comp 1 with the right sign -> |dphi| < 0.05 rad (gain stays |H|). Sign + = this build, sign - = lib_m."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/HP')
import numpy as np
from scipy.signal import butter, sosfreqz
import hpcommon as H
import research_core_signals as S
FS = 48000


def layer_of(lib, x, v):
    y0, _, lat = H.render(lib, x, v, trace=False, vb_level_db=0.0, out_db=-18.0)
    yd, _, _ = H.render(lib, x, v, trace=False, vb_level_db=-120.0, out_db=-18.0)
    return (y0 - yd).mean(1)


def phase_at(lay, lay_ref, f):
    N = int(.2 * FS); w = np.hanning(N); n = np.arange(N); e = np.exp(-2j * np.pi * f * n / FS); ph = []; g = []
    for c in np.arange(.7, 3.5, .1):
        s = int(c * FS)
        if s + N > len(lay):
            break
        zl = np.sum(lay[s:s + N] * w * e); zr = np.sum(lay_ref[s:s + N] * w * e)
        ph.append(np.angle(zl * np.conj(zr))); g.append(abs(zl) / max(abs(zr), 1e-30))
    ph = np.array(ph)
    return float(np.angle(np.mean(np.exp(1j * ph)))), float(np.sqrt(-2 * np.log(max(abs(np.mean(np.exp(1j * ph))), 1e-12)))), float(20 * np.log10(np.median(g)))


l19 = H.CA.load(str(H.LIB19)); lm = H.CA.load(str(H.LIB_M))
t = np.arange(int(4 * FS)) / FS
sigs = {'sin75': 0.1 * np.sin(2 * np.pi * 75 * t), 'sin100': 0.1 * np.sin(2 * np.pi * 100 * t), 'sin62': 0.1 * np.sin(2 * np.pi * 62 * t),
        'tone_steady': S.tone_steady()}
out = {}
for hz, order in ((150, 8), (135, 8), (150, 4)):
    sos = butter(order, hz, 'highpass', fs=3000, output='sos')
    for sn, x in sigs.items():
        X = S.stereo(x)
        f0 = {'sin75': 75, 'sin100': 100, 'sin62': 62, 'tone_steady': 100}[sn]
        ref = layer_of(l19, X, H.vec(dict(H.B3P2)))                                    # unfiltered
        runs = {'comp0': (l19, 0), 'comp1_plus': (l19, 1), 'comp1_minus': (lm, 1)}
        for rn, (lib, comp) in runs.items():
            lay = layer_of(lib, X, H.vec(dict(H.B3P2, layerHpHz=hz, layerHpOrder=order, layerHpComp=comp)))
            for k in (2, 3, 4):
                f = k * f0
                if f > 700:
                    continue
                m, sd, gdb = phase_at(lay, ref, f)
                _, hh = sosfreqz(sos, worN=[2 * np.pi * f / 3000])
                key = f'BW{order}_{hz}|{sn}|{rn}|k{k}'
                out[key] = dict(f=f, dphi=m, std=sd, gain_db=gdb, filt_phase=float(np.angle(hh[0])), filt_gain_db=float(20 * np.log10(abs(hh[0]))))
                print(key, {a: round(b, 3) for a, b in out[key].items()}, flush=True)
json.dump(out, open(H.HP_DIR / 'sign_check.json', 'w'), indent=1)
