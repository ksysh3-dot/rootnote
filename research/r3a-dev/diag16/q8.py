"""Q8: attack candidate evaluated OFFLINE.  A_band = single-voice LS (N_min = 30 past, 24 future, core window) on the band/pre-HPSS stream (detailRing52_) at the
voice's basis frequency; TF = 20log10(A_band / median LS amplitude at probes 22,30,38,45 Hz above and below, same window); A_fast = A_band*smoothstep(TF;3,12) dB;
A_new = A_bh + o*max(0, A_fast - A_bh) with A_bh = the core's trace A.  o = 1 at voice birth (first ON hop) and, as an UPPER BOUND, at the known note onsets
(the trace exposes theta_hat but not the measured phase error e, so phase-transition hops cannot be identified), decaying with tau_o.  Layer = proxy (see proxy16)."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M
import research_core_signals as RS
import streams16 as S
import proxy16 as PX

out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def sstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1); return t * t * (3 - 2 * t)


def band_info(D):
    fb = PX.prev_freq_table(D); H = len(D['tc'])
    Ab = np.full((H, 8), np.nan); TF = np.full((H, 8), np.nan)
    for h in range(H):
        n0 = D['hop'][h] - 191
        if n0 < 40 or n0 + 30 >= len(D['det']):
            continue
        for j in range(8):
            if D['st'][h][j] > 0:
                a, m = S.ls_probe(D['det'], n0, fb[h, j], float(np.clip(D['raw'][h, j, X.F_DFDT], -400, 400)), 30)
                Ab[h, j] = a; TF[h, j] = 20 * np.log10(max(a, 1e-12) / max(m, 1e-12))
    return Ab, TF


def o_matrix(D, onsets, tau_ms, use_onsets):
    tau = tau_ms / 1000.0; tc = D['tc']; d = D['d']; st = D['st']; H = len(tc)
    O = np.zeros((H, 8))
    for v in np.unique(d['voice'][st > 0]):
        hs, js = np.nonzero((d['voice'] == v) & (st == 2))
        if not len(hs):
            continue
        tb = tc[hs.min()]
        h2, j2 = np.nonzero((d['voice'] == v) & (st > 0))
        sel = tc[h2] >= tb
        O[h2[sel], j2[sel]] = np.exp(-(tc[h2[sel]] - tb) / tau)
    if use_onsets and len(onsets):
        tr = np.sort(np.asarray(onsets) - 0.008)
        i = np.searchsorted(tr, tc, 'right') - 1
        oo = np.where(i >= 0, np.exp(-(tc - tr[np.maximum(i, 0)]) / tau), 0.0)
        O = np.maximum(O, oo[:, None] * (st > 0))
    return O


def scale_for(D, Ab, TF, onsets, tau, use_onsets, gate=(3, 12)):
    A = D['d']['A']; Afast = np.nan_to_num(Ab * (1.0 if gate is None else sstep(TF, gate[0], gate[1])))
    O = o_matrix(D, onsets, tau, use_onsets)
    Anew = A + O * np.maximum(0, Afast - A)
    return np.where(A > 1e-9, Anew / np.maximum(A, 1e-9), 1.0)


VARS = ([('baseline', None, False, None)] + [(f'AS SPECIFIED TF gate(3,12) births only, tau_o={t}', t, False, (3, 12)) for t in (30, 60)] +
        [(f'AS SPECIFIED TF gate(3,12) births + known onsets (upper bound), tau_o={t}', t, True, (3, 12)) for t in (30, 60)] +
        [(f'EXTENSION no TF gate, births only, tau_o={t}', t, False, None) for t in (30, 60)] +
        [(f'EXTENSION no TF gate, births + known onsets (upper bound), tau_o={t}', t, True, None) for t in (30, 60)])


def main():
    # ---------------------------------------------------------------- step line 25 dB
    sig, onsets = PX.sig_step_line(25.0)
    D = PX.load('step25', sig); Ab, TF = band_info(D)
    dur = len(sig) / PX.FS
    P('### Q8.1 gated step line, band SNR 25 dB (proxy layer; real layer values from the acceptance: rise90 28.1 ms, tail 44.2 ms for config A)')
    for lab, tau, uo, gt in VARS:
        sc = None if tau is None else scale_for(D, Ab, TF, onsets, tau, uo, gt)
        amp, _ = PX.proxy_amp(D, sc); tt, env = PX.env_at(D['tc'], amp, dur)
        r, t, tl = PX.v3h_gated(tt, env)
        P(f'  {lab}: rise90 {PX.stat(r)} ms; tail (first -20 dB) {PX.stat(t)} ms; settled tail (last above -20 dB) {PX.stat(tl)} ms')
    # TF diagnostics
    on_h = (D['st'] == 2)
    P(f'  TF (tone over floor, N=30 band LS) on ON voice-hops: median {np.nanmedian(TF[on_h]):.1f} dB, p10 {np.nanpercentile(TF[on_h],10):.1f}, p90 {np.nanpercentile(TF[on_h],90):.1f}; fraction with TF>=12 dB {np.nanmean(TF[on_h]>=12)*100:.0f} %, <3 dB {np.nanmean(TF[on_h]<3)*100:.0f} %')
    # ---------------------------------------------------------------- bare note
    xb, ob = PX.sig_bare(); Db = PX.load('bare100', xb); Abb, TFb = band_info(Db)
    P('\n### Q8.2 bare 100 Hz note (1 s from 0.5 s), rise90 from the note start (proxy)  [real layer: 9.2 ms for A? see acceptance table: 29.7 ms for config A]')
    for lab, tau, uo, gt in VARS:
        sc = None if tau is None else scale_for(Db, Abb, TFb, ob, tau, uo, gt)
        amp, _ = PX.proxy_amp(Db, sc); tt, env = PX.env_at(Db['tc'], amp, 3.5)
        refv = env[int(1.2 / .001):int(1.45 / .001)].mean(); seg = env[int(.5 / .001):int(.9 / .001)]
        r90 = np.argmax(seg >= .9 * refv); r50 = np.argmax(seg >= .5 * refv)
        P(f'  {lab}: rise50 {r50:.0f} ms, rise90 {r90:.0f} ms')
    # ---------------------------------------------------------------- bass + kick + pink (V4b-like) and kicks that are not bass onsets
    for kshift, title in ((0.0, 'bass+kick+pink, kick ON the bass onsets (V4b signal)'), (0.25, 'bass+kick+pink with the kick moved to +250 ms (kick hits that are NOT bass onsets)')):
        x, bon, kon, bass = PX.sig_bass_kick_pink(kshift)
        Dk = PX.load(f'bkp_{int(kshift*1000)}', x); Abk, TFk = band_info(Dk)
        P(f'\n### Q8.3 {title}')
        for lab, tau, uo, gt in VARS:
            sc = None if tau is None else scale_for(Dk, Abk, TFk, bon, tau, uo, gt)
            s_ = np.ones((len(Dk['tc']), 8)) if sc is None else sc
            # third-harmonic amplitude of voices near 100 Hz
            near = (np.abs(Dk['d']['fosc'] - 100) < 8) & (Dk['st'] > 0)
            p3 = (np.where(near, Dk['d']['a3'], 0.0) * s_) ** 2
            tt, e3 = PX.env_at(Dk['tc'], p3.sum(axis=1), 8.0)
            low = 0; n = 0
            for nn in range(2, 15):
                vals = np.array([e3[int((0.5 * nn + .04 + .02 * j) / .001):int((0.5 * nn + .06 + .02 * j) / .001)].mean() for j in range(20)])
                db = 10 * np.log10(vals + 1e-20); low += int((db < np.median(db) - 6).sum()); n += 20
            # exceedance statistics
            exc = 20 * np.log10(s_ + 1e-12)
            def win(trig, lo, hi):
                m = np.zeros(Dk['st'].shape, bool)
                for t0 in trig:
                    m |= ((Dk['tc'] - t0 >= lo) & (Dk['tc'] - t0 <= hi))[:, None]
                return m & (Dk['st'] == 2)
            mk = win(kon, 0, .15); mb = win(bon, -.01, .06)
            ex_k = exc[mk]; ex_kn = exc[mk & near]; ex_b = exc[mb & near]
            P(f'  {lab}: V4b-like low bins {low}/{n}; A_new/A_bh in 0-150 ms after kick: all ON voices mean {ex_k.mean():.2f} dB p95 {np.percentile(ex_k,95):.2f} max {ex_k.max():.2f}, '
              f'near-100 Hz voices mean {ex_kn.mean() if len(ex_kn) else float("nan"):.2f} p95 {np.percentile(ex_kn,95) if len(ex_kn) else float("nan"):.2f} max {ex_kn.max() if len(ex_kn) else float("nan"):.2f}; at bass onsets (-10..+60 ms, near 100 Hz) mean {ex_b.mean() if len(ex_b) else float("nan"):.2f} p95 {np.percentile(ex_b,95) if len(ex_b) else float("nan"):.2f} max {ex_b.max() if len(ex_b) else float("nan"):.2f}')
            if kshift:
                # also the change of the total proxy amplitude in the kick windows
                a0, _ = PX.proxy_amp(Dk, None); a1, _ = PX.proxy_amp(Dk, s_)
                mm = np.zeros(len(Dk['tc']), bool)
                for t0 in kon:
                    mm |= (Dk['tc'] - t0 >= 0) & (Dk['tc'] - t0 <= .15)
                P(f'      proxy layer amplitude change in the kick windows: {20*np.log10((a1[mm]**2).sum()/max((a0[mm]**2).sum(),1e-30))/2:+.2f} dB (energy-weighted)')
        # births caused by the kick
        if kshift:
            d = Dk['d']; st = Dk['st']; kb = 0; allb = 0
            for v in np.unique(d['voice'][st == 2]):
                hs, js = np.nonzero((d['voice'] == v) & (st == 2)); t0 = Dk['tc'][hs.min()]
                allb += 1
                if np.any((t0 - np.array(kon) >= 0) & (t0 - np.array(kon) <= .1)):
                    kb += 1
            P(f'  voice births (first ON): {allb}, of them within 100 ms after a (non-bass) kick: {kb}')
    # ---------------------------------------------------------------- Track00060 V5a-like
    xt = RS.load_excerpt(RS.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0)
    Dt = PX.load('t60_36_48', xt); Abt, TFt = band_info(Dt)
    ref = M.bass_ref('Track00060'); rf = C.ref('Track00060')
    onsets_t = rf['ss'] - 36.0
    onsets_t = onsets_t[(onsets_t > 0) & (onsets_t < 12)]
    B = int(.020 * PX.FS); nb = int(8.0 / .020)
    cen_song = 39.0 + .020 * (np.arange(nb) + .5)
    f0 = M.midi_f0_fast(cen_song, ref['notes'], ref['tp'])
    lo = ref['lo']; nbins = len(lo) // B
    levall = 10 * np.log10(np.mean(lo[:nbins * B].reshape(nbins, B) ** 2, axis=1) + 1e-20); p95 = np.percentile(levall, 95)
    k0 = int(39.0 / .020); lev = levall[k0:k0 + nb]
    present = np.isfinite(f0) & (lev > p95 - 20)
    bs = M.bandpass(ref['bz'][36 * PX.FS:49 * PX.FS], 150, 600)
    i0 = 3 * PX.FS
    es = np.array([np.sum(bs[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(nb)])
    idx = np.flatnonzero(present); cen = (np.arange(nb) + .5) * .02
    P(f'\n### Q8.4 Track00060 V5a-like: low bins of (proxy layer energy / bass-stem 150-600 Hz energy) per 20 ms bin; the proxy replaces the real layer (APPROXIMATION); present bins {len(idx)}; the real layer has 11 low bins (5.73 %)')
    for lab, tau, uo, gt in VARS:
        sc = None if tau is None else scale_for(Dt, Abt, TFt, onsets_t, tau, uo, gt)
        amp, _ = PX.proxy_amp(Dt, sc); tt, env = PX.env_at(Dt['tc'], amp, 11.8)
        pw = np.array([np.mean(env[int((3 + .02 * k) / .001):int((3 + .02 * (k + 1)) / .001)] ** 2) for k in range(nb)])
        ratio = 10 * np.log10(pw + 1e-20) - 10 * np.log10(es + 1e-20)
        low = [i for i in idx if ratio[i] < np.median(ratio[idx[np.abs(cen[idx] - cen[i]) <= .25]]) - 6]
        P(f'  {lab}: low bins {len(low)}/{len(idx)} = {100*len(low)/len(idx):.2f} %')
    json.dump({}, open(C.D16 / 'q8.json', 'w'))
    open(C.D16 / 'q8_report.txt', 'w').write('\n'.join(out))


if __name__ == '__main__':
    main()
