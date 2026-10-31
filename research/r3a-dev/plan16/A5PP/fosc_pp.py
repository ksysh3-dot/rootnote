"""f_osc tracking error on synthetic glide and vibrato lines (A5'' guard: median f_osc error vs base <= +10 cent).
Signals (generated here, not part of the suite; bass spectrum PARTIALS 1:0.5:0.18, peak -12 dBFS as tone_steady, 25 dB pink SNR as the suite lines, seed 1; noise-free variant too):
  glide : 100 Hz for 0.8 s, then an exponential glide up 7 semitones (100 -> 150.5 Hz) in 1.0 s (700 cents/s), then holds; 3.5 s total
  vib   : f0 = 100 Hz * 2^(30 cent * sin(2 pi 5.5 t) / 1200) for 4 s (+-30 cent, 5.5 Hz)
  vibw  : same with +-60 cent at 4 Hz (wider/slower)
Truth: f0(t) at the analysis-centre time tc of each hop (tc = hop time of the voice trace, as V3c). Estimate: f_osc of the dominant ON voice (largest (A c sigma)^2) at that hop,
ignoring hops with tc < 0.5 s. Error = 1200 log2(f_osc / f0(tc)), folded to the nearest octave (a voice may sit on 2 f0 / f0/2). Reported: median |error| (cent), median signed error,
p90 |error|, and the fraction of hops with a dominant ON voice, over the moving part (glide: 0.8-1.8 s + 0.3 s; vib: all hops after 0.5 s).
usage: fosc_pp.py [labels...]"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5PP')
import numpy as np
import a5ppcommon as VC
import a5pprows as AR
import research_core_metrics as M
import research_core_signals as S

M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0), ('betaSusMin', 0), ('betaSusMax', 0), ('betaOnsetMs', 0)]
FS = 48000


def synth(f0_of_t, dur):
    t = np.arange(int(dur * FS)) / FS
    f = f0_of_t(t)
    ph = 2 * np.pi * np.cumsum(f) / FS
    x = sum(a * np.sin(k * ph) for k, a in S.PARTIALS)
    x = x * (10 ** (-12 / 20) / np.abs(x).max()) * S._ramp(len(x))
    return x


def glide_f(t):
    u = np.clip((t - 0.8) / 1.0, 0, 1)
    return 100.0 * 2 ** (7 * u / 12)


def vib_f(cents, hz):
    return lambda t: 100.0 * 2 ** (cents * np.sin(2 * np.pi * hz * t) / 1200)


SIGS = {'glide': (glide_f, 3.5, (0.8, 2.1)), 'vib30': (vib_f(30, 5.5), 4.0, (0.5, 4.0)), 'vib60': (vib_f(60, 4.0), 4.0, (0.5, 4.0))}


def measure(ctx, key, x, f_of_t, win):
    X = S.stereo(x)
    r = ctx.render(key, X, 0.0, voice=True)
    vs = M.voices(ctx, r)
    errs = []; nh = 0; nd = 0
    for h in range(len(vs.tc)):
        tc = vs.tc[h]
        if not (win[0] <= tc < win[1]):
            continue
        nh += 1
        on = np.flatnonzero(vs.on[h])
        if not len(on):
            continue
        top = on[np.argmax(vs.w[h][on])]
        fo = vs.f[h][top]
        if not np.isfinite(fo) or fo <= 0:
            continue
        nd += 1
        e = 1200 * np.log2(fo / f_of_t(np.array([tc]))[0])
        errs.append(e - 1200 * np.round(e / 1200))
    e = np.array(errs)
    return dict(med_abs=float(np.median(np.abs(e))) if len(e) else None, med_signed=float(np.median(e)) if len(e) else None,
                p90_abs=float(np.percentile(np.abs(e), 90)) if len(e) else None, frac_dom=nd / max(nh, 1), n=nh)


if __name__ == '__main__':
    labels = sys.argv[1:] or ['v15'] + AR.GRID
    out = {}
    for lab in labels:
        d, algo, prm = AR.ROWS[lab]
        ctx = M.Ctx(str(VC.LIB16B), 15, prm)
        out[lab] = {}
        for nm, (fn, dur, win) in SIGS.items():
            x = synth(fn, dur)
            for snr in (None, 25.0):
                xx = x + (S.pink_for_band_snr(x, snr) if snr else 0.0)
                out[lab][f'{nm}|{"clean" if snr is None else "snr25"}'] = measure(ctx, f'{lab}{nm}{snr}', xx, fn, win)
        print(lab, {k: (round(v['med_abs'], 1), round(v['med_signed'], 1), round(v['frac_dom'], 2)) for k, v in out[lab].items() if v['med_abs'] is not None}, flush=True)
    json.dump(out, open(VC.A5_DIR / 'fosc_pp.json', 'w'), indent=1)
