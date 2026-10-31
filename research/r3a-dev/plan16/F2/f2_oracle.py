"""Stage 0 oracle (16.18, CHOICES.md section 4): hold existing ON voices (age >= 50 ms) at the pre-hit amplitude over [t_d, t_d + W] at the LOGOFF 4.12 s hit.
Offline: v1.5 trace + stage capture of the LOGOFF 37-49 s excerpt, D-path synthesis (synth16 engine gains), R1 burst (gate16/e7_v7d.burst)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F2'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F'); sys.path.insert(0, '/home/ksysh/r3a-dev/gate16')
import numpy as np
from scipy.signal import resample_poly, sosfilt
import fcommon as FC
import research_core_metrics as M
import research_core_signals as S
import research_core_api as CA
import e7_v7d as E7
import synth16 as SY
import tables as T
from vb_quality.stage_capture import INDEX as SI

FS = 48000
HIT = 3.0 + 4.12


def render_all(libpath, params=None, key='logoff'):
    lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
    ctx = M.Ctx(libpath, 15, params or dict(voicing=0, ampSource=0))
    x2 = np.stack([lg, lg], 1) if lg.ndim == 1 else lg
    r0 = ctx.render(key, x2, 0.0, voice=True, stage=True)
    rd = ctx.render(key, x2, -120.0)
    return M.layer_of(r0, rd), np.asarray(r0['voice'], float), r0['stage']


def perc_env_series(stage):
    core = stage[:, SI['core_low32']].astype(np.int64) + (stage[:, SI['core_high32']].astype(np.int64) << 32)
    bp = np.zeros(core.max() + 1)
    bp[core] = stage[:, SI['original_p']]
    att, rel = np.exp(-1. / 6), np.exp(-1. / 120)
    E = np.zeros_like(bp); e = 0.0
    for i in range(len(bp)):
        ep = bp[i] * bp[i]
        a = att if ep > e else rel
        e = a * e + (1 - a) * ep
        E[i] = e
    return E


def cues(Eh, floor=1e-8, nmed=16, ratio=10 ** 0.9, refr=19):
    out = []; last = -10 ** 9
    for h in range(len(Eh)):
        if h < nmed:
            continue
        m = np.median(Eh[h - nmed:h])
        if Eh[h] > ratio * m and Eh[h] > floor and h - last >= refr:
            out.append(h); last = h
    return out


def synth(voices, dur_s):
    """3 kHz layer (kOutSos filtered) of voices [(t, f, amp)] as render_layer16, then 16x to 48 kHz"""
    n = int(np.ceil(dur_s * 3000)) + 8
    y = np.zeros(n)
    for (t, f_, a_) in voices:
        i0 = max(0, int(np.floor(t[0] * 3000))); i1 = min(n, int(np.ceil(t[-1] * 3000)) + 1)
        if i1 <= i0 + 1:
            continue
        tt = np.arange(i0, i1) / 3000.0
        f = np.interp(tt, t, f_); a = np.interp(tt, t, a_, left=0.0, right=0.0)
        ph = 2 * np.pi * np.cumsum(f) / 3000.0
        G = SY.engine_gains(f, 8)
        s = np.zeros(len(tt))
        for k in range(2, 9):
            s += G[k - 2] * np.cos(k * ph)
        y[i0:i1] += a * s
    y = sosfilt(T.OUT_SOS, y)
    return resample_poly(y, 16, 1)


def build(d, hd, cap_db, W_ms, ramp_hops=2, age_hops=10, pre_hops=3):
    """voices as lists per id: dict id -> dict(h, f, amp, amp_held, old(bool))"""
    H = d['hop'].shape[0]
    ih = d['hop'][:, 0]
    t = (ih + 16 - 398) / 3000.0 + CA.CORE_T0
    nW = int(np.ceil(W_ms / (16 / 3000.0 * 1000)))
    ids = np.unique(d['voice'][d['state'] > 0])
    res = {}
    for v in ids:
        hs, js = np.nonzero((d['voice'] == v) & (d['state'] > 0))
        o = np.argsort(hs); hs, js = hs[o], js[o]
        # split into runs of consecutive hops
        brk = np.flatnonzero(np.diff(hs) != 1) + 1
        for a, b in zip(np.r_[0, brk], np.r_[brk, len(hs)]):
            h, j = hs[a:b], js[a:b]
            f = d['f_osc'][h, j]; amp = d['A'][h, j] * d['c'][h, j] * d['sigma'][h, j]
            st = d['state'][h, j].astype(int)
            held = amp.copy(); old = False
            if hd is not None and h[0] <= hd <= h[-1] and st[hd - h[0]] == 2:
                on_first = h[0] + int(np.flatnonzero(st == 2)[0])
                age = hd - on_first
                if age >= age_hops and (hd - pre_hops) >= h[0]:
                    old = True
                    L = amp[hd - pre_hops - h[0]] * 10 ** (cap_db / 20)
                    for q in range(len(h)):
                        k = h[q] - hd
                        if 0 <= k < nW:
                            held[q] = min(amp[q], L)
                        elif nW <= k < nW + ramp_hops:
                            r = (k - nW + 1) / ramp_hops
                            held[q] = (1 - r) * min(amp[q], L) + r * amp[q]
            res.setdefault(int(v), []).append(dict(h=h, t=t[h], f=f, amp=amp, held=held, old=old))
    return res


def layer_of_set(res, which, sel, dur):
    vs = []
    for v, runs in res.items():
        for r in runs:
            if sel(r):
                vs.append((r['t'], r['f'], r[which]))
    return synth(vs, dur)


def best_shift(x, b, lo=-60, hi=60):
    best = (-2, 0)
    for s in range(lo, hi + 1):
        bb = np.roll(b, s * 48)
        c = float(np.dot(x, bb) / (np.linalg.norm(x) * np.linalg.norm(bb) + 1e-30))
        if c > best[0]:
            best = (c, s)
    return best


def band_energy(lay, c, lo=150, hi=600):
    Lb = M.bandpass(lay, lo, hi)
    i0, i1 = int((c - .05) * FS), int((c + .05) * FS)
    return float(np.sum(Lb[i0:i1] ** 2))


def main():
    lay, tr, stage = render_all(str(FC.LIB15))
    d = CA.trace_dict(tr)
    dur = len(lay) / FS
    # reproduction of the F number
    old, new, ref = E7.burst(lay, HIT, 'R1')
    print(f'engine v1.5 LOGOFF R1 burst at 4.12 s: {new:.2f} dB (F/ reports +5.90)')
    E = perc_env_series(stage)
    ihs = d['hop'][:, 0].astype(int)
    Eh = E[np.clip(ihs, 0, len(E) - 1)]
    cu = cues(Eh)
    tcen = (ihs - 382) / 3000.0 + CA.CORE_T0
    print('cue hops with centre time in 6.5..8 s:', [(h, round(float(tcen[h]), 3), float(10 * np.log10(Eh[h] / np.median(Eh[h - 16:h])))) for h in cu if 6.5 < tcen[h] < 8.0])
    print('cues in whole excerpt:', len(cu), 'of hops', len(Eh))
    cand = [h for h in cu if HIT - 0.10 <= tcen[h] <= HIT + 0.05]
    if not cand:
        print('NO CUE near the hit'); json.dump(dict(error='no cue'), open('/home/ksysh/r3a-dev/plan16/F2/f2_oracle.json', 'w')); return
    hd = cand[0]
    print('t_d hop', hd, 'centre time', tcen[hd])
    out = dict(hd=int(hd), t_d=float(tcen[hd]), n_cues=len(cu), engine_burst=new)
    base = build(d, None, 0, 80)
    lb = layer_of_set(base, 'amp', lambda r: True, dur)
    n = min(len(lb), len(lay)); lb = lb[:n]
    for cap, W in ((0.0, 80), (0.0, 40), (3.0, 80), (6.0, 80), (3.0, 40), (6.0, 40)):
        res = build(d, hd, cap, W)
        n_old = sum(1 for runs in res.values() for r in runs if r['old'])
        lh = layer_of_set(res, 'held', lambda r: True, dur)[:n]
        # (a) synth only
        ba = E7.burst(lb, HIT, 'R1')[1]; ha = E7.burst(lh, HIT, 'R1')[1]
        # (b) engine layer + g (held - base), fitted on 100-700 Hz in HIT +- 1.5 s
        i0, i1 = int((HIT - 1.5) * FS), int((HIT + 1.5) * FS)
        x = M.bandpass(lay, 100, 700)[i0:i1]; b = M.bandpass(lb, 100, 700)[i0:i1]
        cc, sh = best_shift(x, b)
        bb = np.roll(b, sh * 48)
        g = float(np.dot(x, bb) / np.dot(bb, bb))
        dl = np.roll(lh - lb, sh * 48) * g
        ym = lay[:n] + dl
        bb_ = E7.burst(ym, HIT, 'R1')[1]
        key = f'cap{cap:g}_W{W}'
        out[key] = dict(n_old_voices=n_old, synth_base=ba, synth_held=ha, gain_a=ba - ha, fit_corr=cc, fit_shift_ms=sh, fit_g=g,
                        engine_plus_delta=bb_, gain_b=new - bb_)
        print(key, json.dumps(out[key]), flush=True)
        if cap == 0.0 and W == 80:
            # birth / rise split of the burst-window band energy (synth, 150-600 Hz, +-50 ms)
            l_old_act = layer_of_set(res, 'amp', lambda r: r['old'], dur)[:n]
            l_old_held = layer_of_set(res, 'held', lambda r: r['old'], dur)[:n]
            l_oth = layer_of_set(res, 'amp', lambda r: not r['old'], dur)[:n]
            Eall = band_energy(lb, HIT); Eo = band_energy(l_old_act, HIT); Eh_ = band_energy(l_old_held, HIT); Eot = band_energy(l_oth, HIT)
            # reference level of the 10 ms boxes (same reference as the R1 definition), to put energies in dB re reference
            Lb = M.bandpass(lb, 150, 600)
            box = int(.010 * FS)
            ref = np.median([float(np.sum(Lb[int(round(t0 * FS)):int(round(t0 * FS)) + box] ** 2)) for t0 in list(np.arange(HIT - .3, HIT - .1, .01)) + list(np.arange(HIT + .1, HIT + .3, .01))])
            f_ = lambda e: float(10 * np.log10(e / 10 / ref + 1e-30))
            out['split_synth_cap0_W80'] = dict(E_all_dB=f_(Eall), E_old_actual_dB=f_(Eo), E_old_held_dB=f_(Eh_), E_others_dB=f_(Eot),
                                              rise_part_energy_share=float((Eo - Eh_) / max(Eall, 1e-30)), others_share=float(Eot / max(Eall, 1e-30)))
            print('split', json.dumps(out['split_synth_cap0_W80']), flush=True)
            print('old voices held:', [(v, [(round(float(r['t'][0]), 2), round(float(r['f'][0]), 1)) for r in runs if r['old']]) for v, runs in res.items() if any(r['old'] for r in runs)])
    json.dump(out, open('/home/ksysh/r3a-dev/plan16/F2/f2_oracle.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
