"""Endpoint and guard metrics computed on the synthesized proxy layer (y48, 150-600 Hz, input-time axis) and on the voice lists.
Definitions follow section 7 / 13.3 and the acceptance code (research_core_metrics / research_core_xcheck); deviations are listed in CHOICES.md."""
import numpy as np
from scipy.signal import butter, sosfilt
from data import X, C, FS, HOP_S
import proxy16 as PX
import research_core_metrics as M

PER, STEP_DUR, STEP_NOTES = PX.PER, PX.STEP_DUR, PX.STEP_NOTES


def box_rms(x, ms):
    return X._box_rms(x, ms)


def _first(seg, thr, above=True):
    ok = seg >= thr if above else seg <= thr
    return float(np.argmax(ok) / FS * 1000) if ok.any() else float('inf')


# ------------------------------------------------------------------------------------------------ E1 / E2 : bare note, gated line
def v3h_bare(y):
    env = box_rms(y, 5.0)
    refv = float(np.mean(env[int(1.2 * FS):int(1.45 * FS)]))
    if refv <= 1e-12:
        return dict(rise50=float('inf'), rise90=float('inf'), tail=float('inf'))
    return dict(rise50=_first(env[int(.5 * FS):int(.9 * FS)], .5 * refv), rise90=_first(env[int(.5 * FS):int(.9 * FS)], .9 * refv),
                tail=_first(env[int(1.5 * FS):int(3.0 * FS)], .1 * refv, above=False))


def v3h_line(y):
    env = box_rms(y, 5.0)
    r50, r90, tl, settled, lead = [], [], [], [], []
    for i in range(2, 40):
        t0 = i * PER; refv = float(np.mean(env[int((t0 + .06) * FS):int((t0 + .11) * FS)]))
        if refv <= 1e-12:
            r50.append(np.inf); r90.append(np.inf); tl.append(np.inf); settled.append(np.inf); continue
        w0 = env[int((t0 - .040) * FS):int((t0 + .125) * FS)]
        ok0 = w0 >= .1 * refv
        lead.append(float(np.argmax(ok0) / FS * 1000 - 40.0) if ok0.any() else np.inf)       # info: when the layer first exceeds -20 dB re the note level, ms re the note start (negative = early)
        seg = env[int(t0 * FS):int(t0 * FS) + int(.125 * FS)]
        r50.append(_first(seg, .5 * refv)); r90.append(_first(seg, .9 * refv))
        sg = env[int((t0 + .125) * FS):int((t0 + .125) * FS) + int(.12 * FS)]
        tl.append(_first(sg, .1 * refv, above=False))
        ab = np.flatnonzero(sg > .1 * refv)
        settled.append(float((ab[-1] + 1) / FS * 1000) if len(ab) else 0.0)
    f = lambda a: float(np.median(a))
    return dict(rise50=f(r50), rise90=f(r90), tail=f(tl), tail_settled=f(settled), miss90=int(np.isinf(r90).sum()), n=len(r90), lead10=f(lead) if lead else float('nan'))


def amp_series_near(voices, t, f0, tol=0.12):
    """sqrt(sum of squared voice amplitudes) of the voices within tol of f0 at the times t (the 'A c' series of the dominant note voice)"""
    S = np.zeros(len(t))
    for v in voices:
        if v['t'][0] > t[-1] or v['t'][-1] < t[0]:
            continue
        a = np.interp(t, v['t'], v['amp'], left=0.0, right=0.0)
        if not a.any():
            continue
        f = np.interp(t, v['t'], v['f'])
        S += np.where(np.abs(f - f0) <= tol * f0, a * a, 0.0)
    return np.sqrt(S)


def rerise(y):
    """AMENDMENT A1 (before results): V3h.RERISE.  Layer envelope = 5 ms boxcar RMS of the synthesized 150-600 Hz layer.  Reference = mean envelope over
    the 45..8 ms before the note end.  t_f = first time after the note end at which the envelope falls below ref - 20 dB (searched up to note end + 120 ms).
    RERISE = max of the envelope over [t_f, note end + 120 ms] in dB above the -20 dB line, floored at 0 (0 when the envelope never falls below the line).
    Statistic: median over notes 2..39 of the 25 dB gated line, plus the count of notes above 6 dB."""
    env = box_rms(y, 5.0); vals = []; fell = 0
    for i in range(2, 40):
        t_e = i * PER + STEP_DUR
        ref = float(np.mean(env[int((t_e - .045) * FS):int((t_e - .008) * FS)]))
        if ref <= 1e-12:
            continue
        line = 0.1 * ref
        post = env[int(t_e * FS):int((t_e + .120) * FS)]
        below = np.flatnonzero(post < line)
        if not len(below):
            vals.append(0.0); continue
        fell += 1
        k = below[0]
        vals.append(max(0.0, float(20 * np.log10(max(post[k:].max(), 1e-30) / line))))
    vals = np.array(vals)
    return dict(median=float(np.median(vals)) if len(vals) else float('nan'), n_above6=int((vals > 6).sum()), n=len(vals), n_fell=fell)


def rebound(voices):
    """OLD V3h.rebound (13.3), superseded by RERISE (amendment A1); kept as INFORMATION only: after the note end, the rise of the dominant amplitude
    above its minimum within 0-80 ms, dB; the series is floored at -40 dB re its level 45-8 ms before the note end; median over the notes"""
    out = []
    for i in range(2, 40):
        t_e = i * PER + STEP_DUR; f0 = STEP_NOTES[i]
        tt = t_e + np.arange(-0.045, 0.0801, 0.001)
        S = amp_series_near(voices, tt, f0)
        pre = S[(tt >= t_e - 0.045) & (tt <= t_e - 0.008)]
        ref = float(pre.mean()) if len(pre) else 0.0
        if ref <= 1e-9:
            continue
        S = np.maximum(S, ref * 1e-2)
        post = S[tt >= t_e]
        k = int(np.argmin(post))
        out.append(20 * np.log10(post[k:].max() / post[k]))
    return float(np.median(out)) if out else float('nan'), len(out)


def enter_time(voices, tc_hops):
    """V3c.enter: first hop (tc >= note start, < +125 ms) at which the DOMINANT voice (largest amplitude) is within 2 % of the new note; median ms"""
    ent = []
    idx = [i for i in range(2, 40) if i != 20]
    for i in idx:
        t0 = i * PER; fn = STEP_NOTES[i]
        h = np.flatnonzero((tc_hops >= t0) & (tc_hops < t0 + STEP_DUR))
        th = tc_hops[h]
        A = []; Fq = []
        for v in voices:
            if v['t'][0] > th[-1] or v['t'][-1] < th[0]:
                continue
            A.append(np.interp(th, v['t'], v['amp'], left=0.0, right=0.0)); Fq.append(np.interp(th, v['t'], v['f']))
        e = np.inf
        if A:
            A = np.array(A); Fq = np.array(Fq); top = np.argmax(A, axis=0)
            ok = (A.max(axis=0) > 0) & (np.abs(Fq[top, np.arange(len(th))] - fn) <= 0.02 * fn)
            if ok.any():
                e = float(th[np.argmax(ok)] - t0) * 1000
        ent.append(e)
    ent = np.array(ent)
    return float(np.median(ent)), int(np.isinf(ent).sum())


# ------------------------------------------------------------------------------------------------ guards
def v3d(y, notes_t0):
    """pre-echo (suite definition): causal 10 ms power; baseline = LS line of its dB over [t0-150,t0-50] ms, extrapolated to the centre of [t0-30,t0];
    rise = dB(mean power over [t0-30,t0]) - line"""
    p = M.causal_power(y, 10.0); rises = []
    # measurement guard-rail (not in the suite): the gated layers of the proxy rows can be EXACTLY zero in the gap, which would turn the dB baseline into
    # -300 dB and any energy into hundreds of dB.  The power is floored at -60 dB re the layer's own p90 power (identical rule for every row).
    pfl = max(float(np.percentile(p, 90)) * 1e-6, 1e-30)
    p = np.maximum(p, pfl)
    plain = []
    for t0 in notes_t0:
        tb = np.arange(int((t0 - .150) * FS), int((t0 - .050) * FS))
        Eb = M.db10(p[tb])
        sl, ic = np.polyfit(tb / FS - t0, Eb, 1)
        w1 = np.arange(int((t0 - .030) * FS), int(t0 * FS))
        rises.append(float(M.db10(np.mean(p[w1])) - (ic + sl * (w1.mean() / FS - t0))))
        # plain form (spec words): rise of the mean power over [t0-30, t0] over the mean power over [t0-150, t0-50] (the 'previous normal level')
        plain.append(float(M.db10(np.mean(p[w1])) - M.db10(np.mean(p[tb]))))
    return dict(median=float(np.median(rises)), max=float(np.max(rises)), n=len(rises), median_plain=float(np.median(plain)), max_plain=float(np.max(plain)))


def v4b(y, clean):
    """bass + kick + pink: 20 ms Hann projections at 300 Hz tiling 40-440 ms of notes 2..15 (notes 0.5 s apart), ratio to the clean bass partial,
    floor -80 dB; fraction of bins more than 6 dB below the note median"""
    nlow = nbin = 0
    for c in range(2, 16):
        t0 = .5 * c; cen = t0 + .040 + .020 * np.arange(20) + .010
        r = M.ratio_db(M.proj_power(y, cen, 300.0), M.proj_power(clean, cen, 300.0))
        m = np.median(r); nlow += int(np.sum(r < m - 6)); nbin += len(r)
    return dict(low_frac=nlow / nbin, low_bins=nlow, bins=nbin)


def v7d_burst(y):
    """LOGOFF hit burst (13.3): layer energy within +-50 ms of the hit (excerpt time 3.0 + hit) minus the median 10 ms box energy over
    [-300,-100] U [+100,+300] ms scaled to 100 ms (x10), dB"""
    out = {}
    z = M.bandpass(y, 150, 600)
    box = int(round(.01 * FS))
    for hit in (4.12, 4.73):
        c = 3.0 + hit          # 37-49 s excerpt: the hit is at excerpt time 3.0 + hit (song time 40 + hit); layer on the latency-compensated input-time axis
        P_ = lambda a: float(np.mean(z[int(round(a * FS)):int(round(a * FS)) + box] ** 2))
        E_hit = float(np.mean([P_(a) for a in c - .05 + .01 * np.arange(10)]))                       # ten 10 ms boxes within +-50 ms
        E_ref = float(np.median([P_(a) for a in np.r_[c - .3 + .01 * np.arange(20), c + .1 + .01 * np.arange(20)]]))   # forty boxes
        out[f'{hit}'] = float(10 * np.log10((E_hit + 1e-30) / (E_ref + 1e-30)))
        out[f'{hit}_E_db'] = float(10 * np.log10(E_hit + 1e-30))
    return out


_V5 = {}


def v5_setup():
    if _V5:
        return _V5
    bz, notes = X.bass_stems_and_notes('Track00060')
    lo = X.band_fft(bz, 40, 220); B = 960; nb = len(lo) // B
    lev = 10 * np.log10(np.mean(lo[:nb * B].reshape(nb, B) ** 2, axis=1) + 1e-20); p95 = float(np.percentile(lev, 95))
    K = 400; k0 = int(round(39.0 / 0.02)); cen = 39.0 + 0.02 * (np.arange(K) + 0.5)
    ns = np.array([n[0] for n in notes]); ne = np.array([n[1] for n in notes])
    sounding = np.array([bool(np.any((ns <= c) & (c < ne))) for c in cen])
    present = sounding & (lev[k0:k0 + K] > p95 - 20)
    es_sig = X.band_fft(bz[36 * FS:49 * FS], 150, 600)
    i0 = 3 * FS
    es = np.array([np.sum(es_sig[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    _V5.update(dict(B=B, K=K, i0=i0, present=present, idx=np.flatnonzero(present), tcen=(np.arange(K) + .5) * .02, es_db=10 * np.log10(es + 1e-20)))
    return _V5


def v5a(y):
    S = v5_setup(); B, K, i0 = S['B'], S['K'], S['i0']
    n = len(y)
    lay = X.band_fft(y[:min(n, 12 * FS + 1000)], 150, 600)
    lay = np.pad(lay, (0, max(0, i0 + K * B - len(lay))))
    el = np.array([np.sum(lay[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    ldb = 10 * np.log10(el + 1e-20); ratio = ldb - S['es_db']
    idx, tcen = S['idx'], S['tcen']; drop = 0
    for i in idx:
        m = idx[np.abs(tcen[idx] - tcen[i]) <= .25]
        if ratio[i] < np.median(ratio[m]) - 6:
            drop += 1
    return dict(frac=drop / len(idx), drops=drop, n=len(idx))


# ------------------------------------------------------------------------------------------------ V9 / V3i
def energy_db(y, t0, t1):
    z = M.bandpass(y[int(t0 * FS):int(t1 * FS)], 150, 600)
    return float(M.db10(np.mean(z ** 2), 1e-14))


def flips_per_s(onb, dur):
    return float(np.sum(onb[1:] != onb[:-1]) / dur)
