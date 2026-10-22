"""hpv51.py - round 5.1 variants of the hpv generator (HPSS hybrid + phase-vocoder harmonic path).

layer_hpv51(m48, **opts) with every option at its default reproduces vb5 vbcore.layer_hpv(m48, 384) bit for bit
(checked in selftest()). Each option changes ONE mechanism so that its effect can be attributed:

  phase = 'k'    harmonic k phase k*Phi + PSI_k (vb5)
          'pm'   phase-matched (Moon et al. 2016): where the source has a reliable partial near k*f0 in the band where the
                 harmonic is added, the synthesised harmonic takes that partial's phase as it arrives at the MIX POINT
                 (dry path: EQ v1.1 filters + the render delay LAT; layer path: output band filter + interpolation FIR).
                 The offset (target - k*Phi) is slew-limited per track/harmonic (PM_SLEW rad per frame) so that a
                 detection that comes and goes cannot make a phase jump.
  harm  = 'add'  add the target harmonic amplitude T_k on top of whatever the source has (vb5)
          'ex'   Moliner et al. 2020 style: existing partial E_k (reliable, >= T_k/EX_GMAX) is AMPLIFIED in place up to
                 the target (a phase-locked copy of the measured partial: its own frequency, amplitude and phase, gain
                 G = clip(T_k/E_k, 1, EX_GMAX), added (G-1)*partial); only missing/weak harmonics are synthesised
                 (amplitude T_k - E_k, phase-matched if a weak partial is seen). Existing partials >= T_k get nothing.
  peaks = 'v5'   up to 4 peaks, second peak within 12 Hz dropped (vb5)
          'pk'   no spacing rule; up to PK_MAX peaks; harmonic grouping (a peak at n*f of a lower kept peak, n=2..5,
                 is that note's own partial: no series of its own); sinusoidality test (residual of a one-sinusoid fit
                 over the main lobe); a peak whose residual exceeds PK_RES_DB is 'unresolved' and its harmonics are
                 faded out (per-track gain, PK_FADE_S), so an unresolvable pair (minor third in 128 ms) is attenuated
                 instead of being replaced by one of its notes.
  env   = 'v5'   imposition with the one-pole 20 ms envelope of |analytic(bh)| (vb5)
          'close' imposition with a beat-insensitive envelope: grey-scale closing (max then min filter, ENV_CLOSE_S)
                 of |analytic(bh)|, centred on the frame time; uses ENV_CLOSE_S of the PV's N/2 look-ahead, so the
                 latency does not change. Fills envelope dips shorter than ENV_CLOSE_S (beats >~ 1/ENV_CLOSE_S Hz).
          'none' no imposition (diagnostic)
  perc  = 'u'    percussive stream -> 1-band analytic generator u^k (vb5)
          'none' no percussive path (diagnostic)
          'gate' u^k on the percussive stream, but only while the percussive stream is transient: gain from the ratio of
                 percussive to harmonic energy (fast detector), so steady content leaking through the soft HPSS mask
                 does not drive the multiplicative generator (diagnostic / candidate)
  lvl   = None   no output level control (vb5)
          'alc'  output harmonic level control (Apple US10382857B1 idea + Mu & Gan 2015 overflow idea): (a) level
                 tracking: band-limited layer RMS vs the input bass RMS times the faithful ratio, gain limited to
                 +-LVL_RANGE_DB, slow (LVL_T_S); (b) overflow: the layer gain is reduced so that |dry + layer| stays
                 below LVL_CEIL (sample peak, 48 kHz dry path estimate at 3 kHz), with a look-ahead min filter and
                 LVL_REL_S release. Needs the dry signal (passed by the caller).
"""
import numpy as np
from scipy.signal import lfilter, sosfilt, sosfreqz
from scipy.ndimage import maximum_filter1d, minimum_filter1d
import vbcore as V
import common5 as C

FS, FSD = V.FS, V.FSD
PM_TOL_REL, PM_TOL_HZ = 0.02, 3.0          # existing partial search: |f - k f0| <= max(3 Hz, 2 %)
PM_REL_DB = -40.0                           # reliable if >= -40 dB re the fundamental peak and >= PV_ABS_DB
PM_SLEW = 0.12                              # rad per frame (5.3 ms) -> pi in ~140 ms
EX_GMAX = 4.0                               # +12 dB maximum gain on an existing partial
PK_MAX = 6
PK_RES_DB = -15.0                           # joint-fit residual above which a peak counts as unresolved
PK_HOLD_S, PK_HOLD_HZ = 0.150, 8.0          # residual peak-hold: 150 ms, +-8 Hz around the peak (catches the beat cycle)
PK_ONSET_RISE = 1.41                        # onset: strongest peak > +3 dB over its max of the previous 43..300 ms
PK2_BORN_S, PK2_FALL = 0.060, 1.19          # pk2: new-note test against 60 ms of tracks; 'falling' = 1.5 dB below the 43 ms max
PK2_STRONG = 0.7                            # pk2: tracks >= 0.7 x the frame's strongest count in the new-note history
PK_FADE_S = 0.030
PK_GROUP_TOL_REL, PK_GROUP_TOL_HZ = 0.015, 1.5
ENV_CLOSE_S = 0.060
# overflow ceiling in the domain where the layer is added (before the -5 dB output gain): -1 dBTP + 5 dB - 0.5 dB margin
LVL_T_S, LVL_RANGE_DB, LVL_CEIL, LVL_REL_S = 0.300, 6.0, 10 ** ((-1.0 - C.OUT_DB - 0.5) / 20), 0.150
GOV_THR, GOV_DUCK_DB, GOV_ATT_S, GOV_REL_S = 0.10, -12.0, 0.020, 0.200   # 'gov': frame off-grid share above which the layer ducks
POLY_REL, POLY_ATT_S, POLY_REL_S = 0.25, 0.020, 0.200                  # 'mask': >= 2 kept peaks within -12 dB -> u^k branch off
LAT_HPV = None                              # render delay (48 kHz samples) used for the phase match; set by the caller


# ---------------------------------------------------------------- phase responses of the two paths
_PHT = {}


def path_phase(f):
    """phi_eq(f) - phi_out(f): dry-path filter phase (EQ v1.1 filters at 48 kHz) minus the layer path's 3 kHz output
    band filter phase. Linear-phase FIR delays and the render delay are handled separately."""
    if 'f' not in _PHT:
        fg = np.arange(20.0, 1000.0, 0.25)
        _, he = sosfreqz(C.eq_sos(FS, 'eq'), worN=fg, fs=FS)
        _, ho = sosfreqz(V._OUT_SOS, worN=fg, fs=FSD)
        _PHT['f'] = fg; _PHT['d'] = np.unwrap(np.angle(he) - np.angle(ho)); _PHT['eq'] = np.abs(he); _PHT['out'] = np.abs(ho)
    return np.interp(f, _PHT['f'], _PHT['d'])


def path_mag(f):
    path_phase(np.array([100.0]))
    return np.interp(f, _PHT['f'], _PHT['eq']), np.interp(f, _PHT['f'], _PHT['out'])


def _hann_kernel(N, nfft, span=40.0, res=64):
    """real zero-phase kernel of the periodic Hann window, sampled on the zero-padded FFT grid, as a function of the
    offset in fractional bins: returns a callable K(off_bins) normalised to K(0) = 1. Tabulated at 1/res bin over
    +-span bins and linearly interpolated (max error < 1e-4 of the peak)."""
    win = np.hanning(N + 1)[:-1]
    n = np.arange(N) - N // 2
    grid = np.arange(-span, span + 1e-9, 1.0 / res)
    tab = (np.cos(2 * np.pi * np.outer(grid, n) / nfft) @ win) / win.sum()
    def K(off):
        return np.interp(np.atleast_1d(off), grid, tab, left=0.0, right=0.0)
    return K


# ---------------------------------------------------------------- online grid check (phase-2 candidates 'gov', 'mask')
from scipy.ndimage import median_filter as _medf


def _tol(f):
    return max(4.0, 0.1 * 24.7 * (4.37 * f / 1000.0 + 1.0))       # metrics51.tol_out


def _src_peaks(Ms, f_grid):
    """source peaks as metrics51.classify sees them, from the vocoder's own source frame: low peaks 28-200 Hz within
    50 dB of the band max, high peaks 140-620 Hz within 60 dB; both >= 10 dB above the +-40 Hz local median."""
    out = []
    df = f_grid[1] - f_grid[0]
    # low search from 20 Hz (the album classifier starts at 28 Hz, where a note within one main lobe of the edge fails
    # the local-median prominence test; the online check must not drop the harmonics of a 30-40 Hz note for that reason)
    for lo, hi, rel in ((20.0, 200.0, 50.0), (140.0, 620.0, 60.0)):
        sel = np.where((f_grid >= lo) & (f_grid <= hi))[0]
        c = Ms[sel]
        if c.size < 3 or c.max() <= 0:
            out.append(np.zeros(0)); continue
        med = _medf(c, size=int(40.0 / df) * 2 + 1, mode='nearest') + 1e-20
        mid = c[1:-1]
        ok = (mid >= c[:-2]) & (mid > c[2:]) & (mid >= c.max() * 10 ** (-rel / 20)) & (mid >= med[1:-1] * 10 ** 0.5)
        i = np.where(ok)[0] + 1
        a, b, cc = np.log(c[i - 1] + 1e-30), np.log(c[i] + 1e-30), np.log(c[i + 1] + 1e-30)
        den = a - 2 * b + cc
        off = np.clip(np.where(np.abs(den) > 1e-12, 0.5 * (a - cc) / np.where(np.abs(den) > 1e-12, den, 1.0), 0.0), -1, 1)
        out.append(f_grid[sel[i]] + off * df)
    return out[0], out[1]


_KS = np.arange(2, V.K_MAX + 1)


def _on_grid(fk, src_lo, src_hi):
    t = _tol(fk)
    if src_hi.size and np.any(np.abs(fk - src_hi) <= t):
        return True
    return bool(src_lo.size and np.any(np.abs(fk - _KS[:, None] * src_lo[None, :]) <= t))


def _frame_gain(frames, n, rule, att_s, rel_s, H):
    """per-frame values at output centre indices -> per-sample gain (FSD): target = rule(value) held over the frame's
    hop, then attack/release one-pole (attack = falling gain)."""
    tgt = np.ones(n)
    for c, v in frames:
        if c < n:
            tgt[c:min(n, c + H)] = rule(v)
    a = np.exp(-1 / (att_s * FSD)); r = np.exp(-1 / (rel_s * FSD))
    out = np.empty(n); gcur = 1.0
    for i in range(n):
        v = tgt[i]
        gcur = a * gcur + (1 - a) * v if v < gcur else r * gcur + (1 - r) * v
        out[i] = gcur
    return out


# ---------------------------------------------------------------- the generalised phase-vocoder path
def pv_layer51(bh, A_fast, md2=None, phase='k', harm='add', peaks='v5', env='v5', N=V.PV_N, H=V.PV_H, nfft=V.PV_NFFT,
               d_hpss=0, stats=None, shift=0, lat48=None, grid='none', mask_smooth_s=0.0, frame_trace=None,
               continuous_phase=False, follow_partials=False, harmonic_rolloff_db_per_octave=0.0):
    """bh: harmonic stream (FSD); A_fast: |analytic(bh)|; md2: decimated full-band mono aligned with bh (needed for
    phase='pm' / harm='ex'); d_hpss: samples by which bh lags md (for the phase bookkeeping)."""
    if N % 2 or N < 2 * H or nfft < N or mask_smooth_s < 0:
        raise ValueError('invalid window, FFT size, or mask smoothing time')
    if (continuous_phase or follow_partials) and (harm != 'add' or phase != 'pm'):
        raise ValueError('continuous-phase research requires additive phase matching')
    if follow_partials and not continuous_phase:
        raise ValueError('partial following requires continuous-phase synthesis')
    if not np.isfinite(harmonic_rolloff_db_per_octave) or harmonic_rolloff_db_per_octave < 0:
        raise ValueError('harmonic rolloff must be finite and nonnegative')
    n = len(bh)
    win = np.hanning(N + 1)[:-1]
    wsum = win.sum()
    nf = (n - N) // H + 1
    half = N // 2
    f_grid = np.fft.rfftfreq(nfft, 1 / FSD)
    df = f_grid[1] - f_grid[0]
    lo_bin = int(np.searchsorted(f_grid, 25.0)); hi_bin = int(np.searchsorted(f_grid, 200.0))
    out = np.zeros(n + 2 * N); apv = np.zeros(n + 2 * N)
    gw = np.bartlett(2 * H + 1)[:-1]
    gn = np.arange(-H, H)
    tracks = []
    eps_abs = 10 ** (V.PV_ABS_DB / 20)
    ks = np.arange(2, V.K_MAX + 1)
    need_src = phase == 'pm' or harm == 'ex' or grid != 'none'
    gframe = []; pframe = []                    # (output centre index, value) per frame for 'gov' / 'mask'
    if need_src:
        assert md2 is not None and (LAT_HPV is not None or lat48 is not None)
        tau_aa = V.AA_DELAY / FS
        LATR = LAT_HPV if lat48 is None else lat48
        t_corr = 2 * tau_aa + (half + shift + d_hpss) / FSD - LATR / FS      # see module doc / PORT_SPEC
    if peaks in ('pk', 'pk2'):
        trk_hist = []
        hold = []; hold_n = max(1, int(round(PK_HOLD_S * FSD / H))); hold_f = np.arange(20.0, 210.0, 1.0)
        apk_hist = []; onset_near = int(round(0.043 * FSD / H)); onset_far = int(round(0.300 * FSD / H)); onset_left = 0
        pk2_born_n = int(round(PK2_BORN_S * FSD / H))
        K = _hann_kernel(N, nfft)
        lobe = int(np.ceil(2 * FSD / N / df))                          # main-lobe half width in zero-padded bins
        kern = K(np.arange(-lobe, lobe + 1).astype(float))
    st = dict(frames=0, peaks=0, unresolved=0, grouped=0, pm_found=0, pm_tried=0, ex_amp=0, ex_synth=0,
              mask_flips=0, track_births=0, fundamental_phase_error_max_rad=0.0,
              harmonic_phase_limited=0, followed_partials=0)
    mask_alpha = 1 - np.exp(-H / (mask_smooth_s * FSD)) if mask_smooth_s else 1.0
    max_peaks = PK_MAX if peaks in ('pk', 'pk2') else V.PV_MAX_PEAKS
    for j in range(nf):
        s0 = j * H; frame = bh[s0:s0 + N] * win
        fr = np.r_[frame[half:], np.zeros(nfft - N), frame[:half]]
        X = np.fft.rfft(fr)
        mag = np.abs(X[lo_bin:hi_bin])
        if mag.size == 0 or mag.max() * 2 / wsum < eps_abs:
            tracks = []
            if peaks in ('pk', 'pk2'):
                apk_hist = []; trk_hist = []
            continue
        lm = np.where((mag[1:-1] >= mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
        if lm.size == 0:
            tracks = []
            continue
        st['frames'] += 1
        order = lm[np.argsort(mag[lm])[::-1]]
        thr = mag.max() * 10 ** (V.PV_REL_DB / 20)
        pk = []
        for i in order:
            if mag[i] < thr or len(pk) >= max_peaks:
                break
            a_, b_, c_ = np.log(mag[i - 1] + 1e-30), np.log(mag[i] + 1e-30), np.log(mag[i + 1] + 1e-30)
            den = a_ - 2 * b_ + c_
            off = 0.5 * (a_ - c_) / den if abs(den) > 1e-12 else 0.0
            off = float(np.clip(off, -1, 1))
            fp = f_grid[lo_bin + i] + off * df
            ap = np.exp(b_ - 0.25 * (a_ - c_) * off) * 2 / wsum
            ph = float(np.angle(X[lo_bin + i]))
            if peaks == 'v5':
                if any(abs(fp - q[0]) < 12.0 for q in pk):
                    continue
                pk.append((fp, ap, ph, 1.0, False))
            else:
                pk.append((fp, ap, ph, lo_bin + i + off, False))
        if peaks in ('pk', 'pk2') and pk:
            # sinusoidality: residual of a JOINT fit of all picked peaks (each a stationary sinusoid with the measured
            # frequency, amplitude and phase) over each peak's main lobe; a resolved neighbour is explained by its own
            # model, an unresolved pair (one lobe holding two components) leaves a large residual
            lo_s = max(int(min(q[3] for q in pk)) - lobe - 1, 0); hi_s = int(max(q[3] for q in pk)) + lobe + 2
            kk = np.arange(lo_s, hi_s)
            model = np.zeros(len(kk), complex)
            for q in pk:
                model += (q[1] * wsum / 2) * np.exp(1j * q[2]) * K(kk - q[3])
            err = np.abs(X[lo_s:hi_s] - model) ** 2
            pk2 = []
            for q in pk:
                m_ = np.abs(kk - q[3]) <= lobe
                own = (q[1] * wsum / 2) ** 2 * np.sum(K(kk[m_] - q[3]) ** 2)
                pk2.append((q[0], q[1], q[2], 10 * np.log10(np.sum(err[m_]) / max(own, 1e-30) + 1e-12), False))
            pk = pk2
            # harmonic grouping: ascending frequency; a peak at n*f of a lower kept peak belongs to that note
            pk.sort(key=lambda q: q[0])
            kept = []
            for q in pk:
                own = False
                for p in kept:
                    nn = round(q[0] / p[0])
                    if 2 <= nn <= 5 and abs(q[0] - nn * p[0]) <= max(PK_GROUP_TOL_HZ, PK_GROUP_TOL_REL * q[0]):
                        own = True; break
                if own:
                    st['grouped'] += 1
                else:
                    kept.append(q)
            pk = kept
            # frequency-local peak-hold of the residual (an unresolved pair's residual swings with its beat). Frames whose
            # window straddles an onset (new energy above the recent maximum; steady beats never exceed it) do not
            # write: a stationary-sinusoid fit is not expected to hold there.
            amax = max(q[1] for q in pk)
            past = apk_hist[-onset_far:-onset_near] if len(apk_hist) > onset_near else []
            # a new note: a strong peak with no previous-frame track within 20 % (an unresolved pair's merged peak wanders
            # by less than that from frame to frame; a legato note change moves further)
            if peaks == 'pk':
                born = any(q[1] >= 0.5 * amax and not any(abs(tr['f'] - q[0]) < 0.20 * q[0] for tr in tracks) for q in pk)
                falling = False
            else:
                # pk2: a new note must be new against every track of the last PK2_BORN_S (an unresolved pair's merged peak
                # visits both of its positions within one beat); a falling strongest peak (decay, the falling half of a
                # beat) does not write the hold: a decaying sinusoid is not stationary inside the window
                hist_f = [f_ for fl in trk_hist for f_ in fl] + [tr['f'] for tr in tracks if tr.get('strong', True)]
                born = len(trk_hist) > 0 and any(q[1] >= 0.5 * amax and not any(abs(f_ - q[0]) < 0.20 * q[0] for f_ in hist_f) for q in pk)
                recent = apk_hist[-onset_near:] if apk_hist else []
                falling = len(recent) > 0 and amax < max(recent) / PK2_FALL
            if (not len(past)) or amax > PK_ONSET_RISE * max(past) or born:   # sound after silence / new energy / new note
                onset_left = N // H
            apk_hist.append(amax)
            if len(apk_hist) > onset_far:
                apk_hist.pop(0)
            rmap = np.full(len(hold_f), -200.0)
            for q in (pk if (onset_left <= 0 and not falling) else []):
                m_ = np.abs(hold_f - q[0]) <= PK_HOLD_HZ
                rmap[m_] = np.maximum(rmap[m_], q[3])
            onset_left -= 1
            hold.append(rmap)
            if len(hold) > hold_n:
                hold.pop(0)
            hm = np.max(np.array(hold), 0)
            pk = [(q[0], q[1], q[2], float(np.max(hm[np.abs(hold_f - q[0]) <= PK_HOLD_HZ])), False) for q in pk]
        st['peaks'] += len(pk)
        if frame_trace is not None:
            frame_trace.append((s0 + N + shift, [(q[0], q[1], q[3]) for q in pk]))
        Xs = None
        if need_src:
            frs = md2[s0:s0 + N] * win
            Xs = np.fft.rfft(np.r_[frs[half:], np.zeros(nfft - N), frs[:half]])
            Ms = np.abs(Xs)
        if grid != 'none':
            src_lo, src_hi = _src_peaks(Ms, f_grid)
            e_on = e_off = 0.0
            if peaks in ('pk', 'pk2') and pk:
                am = max(q[1] for q in pk)
                pframe.append((s0 + N + shift, float(sum(q[1] >= POLY_REL * am for q in pk) >= 2)))
        new_tracks = []
        grain = np.zeros(2 * H); agrain = 0.0
        for fp, ap, ph, res_db, _ in pk:
            best = None
            for tr in tracks:
                if abs(tr['f'] - fp) < 0.10 * fp and (best is None or abs(tr['f'] - fp) < abs(best['f'] - fp)):
                    best = tr
            if best is not None:
                tracks.remove(best)
                pred = best['Phi'] + np.pi * (best['f'] + fp) * H / FSD
                Phi = ph + 2 * np.pi * np.round((pred - ph) / (2 * np.pi))
                offk = best['off'].copy(); fg_ = best['fade']
                st['fundamental_phase_error_max_rad'] = max(st['fundamental_phase_error_max_rad'], abs(float(Phi - pred)))
            else:
                Phi = ph
                offk = V.PSI.copy(); fg_ = 1.0 if (peaks == 'v5' or res_db <= PK_RES_DB) else 0.0
                st['track_births'] += 1
            mask_g = best['mask_g'].copy() if best is not None else np.zeros(len(ks))
            mask_on = best['mask_on'].copy() if best is not None else np.zeros(len(ks), dtype=bool)
            # Separate harmonic oscillators prevent a small fundamental phase
            # reset from being multiplied by k. Their correction is bounded at
            # the emitted harmonic, not only at the fundamental's phase offset.
            hphi = np.zeros(len(ks)); hfreq = np.zeros(len(ks)); hon = np.zeros(len(ks), dtype=bool)
            # fade state of this peak (peaks='pk'): towards 0 when unresolved, towards 1 when clean
            if peaks in ('pk', 'pk2'):
                a_f = 1 - np.exp(-H / (PK_FADE_S * FSD))
                tgt = 0.0 if res_db > PK_RES_DB else 1.0
                if tgt == 0.0:
                    st['unresolved'] += 1
                fg_ = fg_ + (tgt - fg_) * a_f
            wk, gk = V.lookup(np.array([fp]))
            if harmonic_rolloff_db_per_octave:
                # Research: attenuate only the sustained path's upper partials.
                # Keep the existing level table and do not redistribute removed
                # energy to the retained partials. A uniform-gain control is
                # necessary when judging any perceptual improvement.
                octaves = np.maximum(np.log2(ks*fp/220.0), 0.0)
                wk = wk * 10**(-harmonic_rolloff_db_per_octave*octaves[:, None]/20)
            amp = ap * gk[0] * fg_
            phase_ = Phi + 2 * np.pi * fp * gn / FSD
            for ki, k in enumerate(ks):
                w = wk[ki, 0]
                if w <= 1e-4:
                    continue
                fk = k * fp
                ak = amp * w                                  # target layer amplitude (3 kHz domain, pre output filter)
                if grid != 'none':
                    ong = _on_grid(fk, src_lo, src_hi)
                    if best is not None and ong != mask_on[ki]:
                        st['mask_flips'] += 1
                    mask_on[ki] = ong
                    if ong:
                        e_on += ak * ak
                    else:
                        e_off += ak * ak
                        if grid == 'mask' and not mask_smooth_s:
                            continue
                    if grid == 'mask' and mask_smooth_s:
                        # Experimental per-harmonic causal fade. The default remains bit-identical.
                        # It can preserve a rejected partial briefly; diagnostics must check that tradeoff.
                        mask_g[ki] += mask_alpha * (float(ong) - mask_g[ki])
                        ak *= mask_g[ki]
                if not need_src or (phase != 'pm' and harm == 'add'):
                    # A source spectrum may be needed only for the grid mask.
                    # That must not silently enable phase matching in a control.
                    grain += ak * np.cos(k * phase_ + offk[ki])
                    continue
                # existing partial near k*fp in the source (mix point reference)
                st['pm_tried'] += 1
                tol = max(PM_TOL_HZ, PM_TOL_REL * fk)
                b0 = int(np.floor((fk - tol) / df)); b1 = int(np.ceil((fk + tol) / df)) + 1
                seg = Ms[b0:b1]
                found = False
                if seg.size >= 3:
                    ii = int(np.argmax(seg)) + b0
                    if Ms[ii] >= Ms[ii - 1] and Ms[ii] > Ms[ii + 1]:
                        a2, b2, c2 = np.log(Ms[ii - 1] + 1e-30), np.log(Ms[ii] + 1e-30), np.log(Ms[ii + 1] + 1e-30)
                        den = a2 - 2 * b2 + c2
                        o2 = float(np.clip(0.5 * (a2 - c2) / den if abs(den) > 1e-12 else 0.0, -1, 1))
                        fe = f_grid[ii] + o2 * df
                        ae = np.exp(b2 - 0.25 * (a2 - c2) * o2) * 2 / wsum
                        if abs(fe - fk) <= tol and ae >= ap * 10 ** (PM_REL_DB / 20) and ae >= eps_abs:
                            found = True
                            phe = float(np.angle(Xs[ii]))
                if found:
                    st['pm_found'] += 1
                    # phase this harmonic must have at the grain centre to arrive in phase with the dry partial
                    psi_t = phe + path_phase(fk) + 2 * np.pi * fk * t_corr
                    tgt_off = psi_t - k * Phi
                else:
                    tgt_off = V.PSI[ki]
                if continuous_phase:
                    freq = fk
                    target = k * Phi + tgt_off
                    if found and follow_partials:
                        # Add the same target layer amplitude; unlike harm='ex',
                        # do not subtract the existing partial from that target.
                        # A sufficiently strong partial is followed in frequency
                        # as well as phase. No claim of source identity is made.
                        heq, hout = path_mag(np.array([fe, fk]))
                        E, T = ae * heq[0], ak * hout[1]
                        if E >= T / EX_GMAX:
                            freq = fe
                            target = phe + path_phase(fe) + 2*np.pi*fe*t_corr
                            ak *= hout[1] / max(path_mag(np.array([fe]))[1][0], 1e-9)
                            st['followed_partials'] += 1
                    if best is not None and best['hon'][ki]:
                        pred_h = best['hphi'][ki] + np.pi*(best['hfreq'][ki]+freq)*H/FSD
                        err_h = float(np.angle(np.exp(1j*(target-pred_h))))
                        theta = pred_h + np.clip(err_h, -PM_SLEW, PM_SLEW)
                        st['harmonic_phase_limited'] += int(abs(err_h) > PM_SLEW)
                    else:
                        theta = target
                    hphi[ki], hfreq[ki], hon[ki] = theta, freq, True
                    grain += ak * np.cos(theta + 2*np.pi*freq*gn/FSD)
                    continue
                dlt = np.angle(np.exp(1j * (tgt_off - offk[ki])))
                offk[ki] = offk[ki] + np.clip(dlt, -PM_SLEW, PM_SLEW)
                if harm == 'add' or not found:
                    if harm == 'ex' and found is False:
                        st['ex_synth'] += 1
                    grain += ak * np.cos(k * phase_ + offk[ki])
                    continue
                # harm == 'ex' and an existing partial: compare at the mix point
                heq, hout = path_mag(np.array([fe, fk]))
                E = ae * heq[0]                               # existing partial at the mix point (before the output gain)
                T = ak * hout[1]                              # what vb5 would add at the mix point
                if E >= T / EX_GMAX:
                    st['ex_amp'] += 1
                    G = min(T / E, EX_GMAX) if E > 0 else 1.0
                    if G > 1.0:
                        # copy of the partial with its own frequency, phase matched at the mix point, scaled (G-1)
                        psi_e = phe + path_phase(fe) + 2 * np.pi * fe * t_corr
                        add = (G - 1.0) * E / max(path_mag(np.array([fe]))[1][0], 1e-9)
                        grain += add * np.cos(psi_e + 2 * np.pi * fe * gn / FSD)
                else:
                    st['ex_synth'] += 1
                    add = max(T - E, 0.0) / max(hout[1], 1e-9)
                    grain += add * np.cos(k * phase_ + offk[ki])
            new_tracks.append(dict(f=fp, Phi=Phi, off=offk, fade=fg_, a=ap, mask_g=mask_g, mask_on=mask_on,
                                   hphi=hphi, hfreq=hfreq, hon=hon))
            agrain += ap * (fg_ if peaks in ('pk', 'pk2') else 1.0)
        tracks = new_tracks
        if grid == 'gov':
            share = e_off / (e_on + e_off) if (e_on + e_off) > 0 else 0.0
            gframe.append((s0 + N + shift, share))
        if peaks == 'pk2':
            # only the strong tracks of the frame (>= PK2_STRONG x its strongest peak) count as 'the note was there'
            am_ = max([tr['a'] for tr in tracks], default=0.0)
            for tr in tracks:
                tr['strong'] = tr['a'] >= PK2_STRONG * am_
            trk_hist.append([tr['f'] for tr in tracks if tr['strong']])
            if len(trk_hist) > pk2_born_n:
                trk_hist.pop(0)
        c = s0 + N + shift                             # vb5: s0 + N (first grain sample 15 samples before the frame end)
        out[c - H:c + H] += grain * gw; apv[c - H:c + H] += agrain * gw
    out = out[:n]; apv = apv[:n]
    dl = half + shift
    A_del = np.r_[np.zeros(dl), A_fast[:-dl]] if dl < n else np.zeros(n)
    al = np.exp(-1 / (V.PV_ENV_SMOOTH_S * FSD))
    P_s = lfilter([1 - al], [1, -al], apv)
    if env == 'v5':
        A_s = lfilter([1 - al], [1, -al], A_del)
    elif env == 'close':
        # closing of the envelope centred on the frame time (A_fast at index i - half): the max filter reaches W/2 ahead,
        # the min filter another W/2: total look-ahead W <= half samples (available inside the PV latency)
        W = int(ENV_CLOSE_S * FSD) | 1
        assert W <= half
        Ad = maximum_filter1d(A_fast, W, mode='nearest')
        Ad = minimum_filter1d(Ad, W, mode='nearest')
        A_c = np.r_[np.zeros(dl), Ad[:-dl]]                     # centred filters: the shift by half keeps it causal
        A_s = lfilter([1 - al], [1, -al], A_c)
    if env == 'none':
        g = (apv > 0).astype(float)
    else:
        g = np.clip(A_s / (P_s + 1e-9), 0.0, V.PV_ENV_CAP) * (apv > 0)
    if stats is not None:
        stats.update(st)
    info = dict(delay_d=half + shift, apv=apv, g=g)
    if grid == 'gov':
        info['gov'] = _frame_gain(gframe, n, lambda v: 1.0 if v <= GOV_THR else 10 ** (GOV_DUCK_DB / 20), GOV_ATT_S, GOV_REL_S, H)
    if grid == 'mask':
        info['poly_off'] = _frame_gain(pframe, n, lambda v: 0.0 if v > 0.5 else 1.0, POLY_ATT_S, POLY_REL_S, H)
    if stats is not None and grid == 'gov' and gframe:
        sh_ = np.array([v for _, v in gframe]); stats['gov_frames_ducked_pct'] = round(100 * float(np.mean(sh_ > GOV_THR)), 2)
    if stats is not None and grid == 'mask' and pframe:
        stats['poly_frames_pct'] = round(100 * float(np.mean([v for _, v in pframe])), 2)
    return out * g, info


def perc_gate(bp, bh, att_s=0.002, rel_s=0.040, ratio_db=0.0, width_db=6.0):
    """gain 0..1 for the percussive generator: on while the percussive stream's fast envelope exceeds the harmonic
    stream's (transient), off for steady leakage (percussive << harmonic). Soft knee over width_db."""
    def env(x):
        p = x * x
        a1 = np.exp(-1 / (att_s * FSD)); r1 = np.exp(-1 / (rel_s * FSD))
        out = np.empty_like(p); e = 0.0
        # one-pole attack/release (vectorised enough: short loop at 3 kHz)
        for i, v in enumerate(p):
            e = a1 * e + (1 - a1) * v if v > e else r1 * e + (1 - r1) * v
            out[i] = e
        return out
    ep, eh = env(bp), env(bh)
    r = 10 * np.log10((ep + 1e-20) / (eh + 1e-20))
    return np.clip((r - ratio_db + width_db / 2) / width_db, 0.0, 1.0)


def level_control(h3, b3, dry3, f_dom=None):
    """output harmonic level control on the 3 kHz layer h3 (already band-limited). b3: the input bass band (32-190 Hz),
    dry3: the dry mix as it will be summed (EQ'd, 3 kHz estimate). Returns the gain series (FSD)."""
    def rms(x, t):
        a = np.exp(-1 / (t * FSD))
        return np.sqrt(lfilter([1 - a], [1, -a], x * x) + 1e-20)
    # (a) level tracking: the layer's band-limited RMS should be the faithful ratio times the input bass RMS.
    # The ratio actually produced on steady tones is within ~2 dB of the table (synth t_tones) so the reference is the
    # long-term ratio of the two detectors; the control only corrects slow departures from it (+-LVL_RANGE_DB).
    Lh = rms(h3, LVL_T_S); Lb = rms(b3, LVL_T_S)
    ratio = Lh / Lb
    ref = np.exp(lfilter([1 - np.exp(-1 / (3.0 * FSD))], [1, -np.exp(-1 / (3.0 * FSD))], np.log(ratio + 1e-12)))  # 3 s memory
    g_a = np.clip(ref / (ratio + 1e-12), 10 ** (-LVL_RANGE_DB / 20), 10 ** (LVL_RANGE_DB / 20))
    # (b) overflow: |dry + g*layer| <= LVL_CEIL  ->  g <= (LVL_CEIL - |dry|) / |layer| where both have the same sign
    hd = h3 * g_a
    same = np.sign(hd) == np.sign(dry3)
    room = np.maximum(LVL_CEIL - np.abs(dry3), 0.0)
    g_b = np.where(same & (np.abs(hd) > 1e-9), np.minimum(1.0, room / (np.abs(hd) + 1e-12)), 1.0)
    la = int(0.005 * FSD)                                   # 5 ms look-ahead (inside the PV latency)
    g_b = minimum_filter1d(np.r_[g_b[la:], np.ones(la)], 2 * la + 1, mode='nearest')
    rel = np.exp(-1 / (LVL_REL_S * FSD))
    out = np.empty_like(g_b); s = 1.0
    for i, v in enumerate(g_b):
        s = v if v < s else rel * s + (1 - rel) * v
        out[i] = s
    return g_a * out


def layer_hpv51(m48, phase='k', harm='add', peaks='v5', env='v5', perc='u', lvl=None, pv_n=V.PV_N, hp_n=V.HP_N,
                placement='lo', dry48=None, stats=None, return_parts=False, causal=False, grid='none', render_lat=None,
                mask_smooth_s=0.0, pv_nfft=V.PV_NFFT, frame_trace=None,
                continuous_phase=False, follow_partials=False, harmonic_rolloff_db_per_octave=0.0):
    """causal=True: strictly causal grain placement. vb5's pv_layer centres the grain of frame j at s0 + N, so its
    first sample (s0 + N - 16) precedes the frame's last sample (s0 + N - 1) by 15 samples: a 5 ms look-ahead at 3 kHz.
    causal=True places it 15 samples later and delays every aligned path (envelope, percussive path) and the phase-match
    timing by the same amount; the render delay grows by 240 samples at 48 kHz (LAT_HPV + 240). The output is then
    exactly the causal=False output delayed by 240 samples (checked in causal_check()).

    Research-only controls: mask_smooth_s applies a per-track/harmonic causal fade
    to grid='mask'; zero preserves the existing output. frame_trace, if supplied,
    receives (PV output centre at FSD, [(frequency, amplitude, fit residual), ...]).
    It is not a perceptual confidence score. pv_nfft must cover the whole window.
    continuous_phase bounds each harmonic oscillator's phase correction;
    follow_partials additionally follows reliable existing partial frequencies
    without subtracting existing amplitude from the additional-layer target.
    These optional research controls require additive phase matching, default OFF.
    harmonic_rolloff_db_per_octave attenuates PV partials above 220 Hz without
    energy redistribution; percussion and the nominal layer gain stay unchanged.
    """
    V.PLACEMENT = placement
    md = V.decimate(m48)
    b = sosfilt(V._BAND_SOS, md)
    hop = hp_n // 12
    bh, bp = V.hpss_split(b, hp_n, hop, V.HP_MED_T, V.HP_MED_F)
    d = hp_n - 1
    bh = np.r_[np.zeros(d), bh[:-d]]; bp = np.r_[np.zeros(d), bp[:-d]]
    eps = 10 ** (V.EPS_DB / 20)
    zh = V.hilbert_iir(bh); zp = V.hilbert_iir(bp)
    md2 = np.r_[np.zeros(d), md[:-d]] if (phase == 'pm' or harm == 'ex' or grid != 'none') else None
    shift = (V.PV_H - 1) if causal else 0
    lat48 = (LAT_HPV + V.DEC * shift) if (causal and LAT_HPV is not None) else None
    if render_lat is not None:                          # a variant with its own render delay (phase match must use it)
        lat48 = int(render_lat) + V.DEC * shift
    hh, inf = pv_layer51(bh, np.abs(zh), md2=md2, phase=phase, harm=harm, peaks=peaks, env=env, N=pv_n, d_hpss=d,
                         stats=stats, shift=shift, lat48=lat48, grid=grid, mask_smooth_s=mask_smooth_s, nfft=pv_nfft,
                         frame_trace=frame_trace, continuous_phase=continuous_phase, follow_partials=follow_partials,
                         harmonic_rolloff_db_per_octave=harmonic_rolloff_db_per_octave)
    half = inf['delay_d']
    if perc == 'none':
        hp = np.zeros(len(zp))
    else:
        hp, _ = V.band_layer(zp, V.F_LO_EDGE, V.F_HI_EDGE, eps)
        if perc == 'gate':
            hp = hp * perc_gate(bp, bh)
    hp = np.r_[np.zeros(half), hp[:-half]]
    if grid == 'mask':
        hp = hp * inf['poly_off']                       # u^k branch off while two or more bass notes are present
    if grid == 'gov':
        hh = hh * inf['gov']; hp = hp * inf['gov']
    h = sosfilt(V._OUT_SOS, hh + hp)
    if lvl == 'alc':
        if dry48 is None:                                   # mono estimate of the dry mix at the summing point
            dry48 = V.delay(sosfilt(C.eq_sos(FS, 'eq'), m48), max(LAT_HPV - 2 * V.AA_DELAY, 0))
        dry3 = V.decimate(dry48)
        b3 = np.r_[np.zeros(d + half), b[:-(d + half)]]
        g = level_control(h, b3, dry3)
        h = h * g
        if stats is not None:
            stats['lvl_gain_db_p5_p50_p95'] = [round(float(v), 2) for v in 20 * np.log10(np.percentile(g, [5, 50, 95]) + 1e-12)]
    out = V.interpolate(h, len(m48))
    if return_parts:
        return out, dict(delay_d=d + half, pv=V.interpolate(sosfilt(V._OUT_SOS, hh), len(m48)),
                         perc=V.interpolate(sosfilt(V._OUT_SOS, hp), len(m48)))
    return out, dict(delay_d=d + half)


def causal_check(opts=None, seconds=10.0):
    """max |causal layer - (non-causal layer delayed by 240 samples)| on a 10 s mixed bass signal"""
    opts = opts or dict(env='close', perc='gate', peaks='pk2', phase='pm')
    rng = np.random.default_rng(5)
    t = np.arange(int(seconds * FS)) / FS
    x = (0.2 * np.sin(2 * np.pi * 55 * t) + 0.15 * np.sin(2 * np.pi * 82.41 * t + 1) * (t > 3) + 0.1 * np.sin(2 * np.pi * 165.3 * t)
         + 0.01 * rng.standard_normal(len(t))) * (t > 0.5)
    a, _ = layer_hpv51(x, **opts)
    b, _ = layer_hpv51(x, causal=True, **opts)
    sh = V.DEC * (V.PV_H - 1)
    return float(np.max(np.abs(b[sh:] - a[:-sh]))), float(np.max(np.abs(a)))


def selftest():
    rng = np.random.default_rng(3)
    t = np.arange(int(2.5 * FS)) / FS
    x = 0.2 * np.sin(2 * np.pi * 55 * t) + 0.15 * np.sin(2 * np.pi * 82.41 * t + 1) + 0.01 * rng.standard_normal(len(t))
    a, _ = V.layer_hpv(x, 384)
    b, _ = layer_hpv51(x)
    return float(np.max(np.abs(a - b)))


if __name__ == '__main__':
    print('max |vb5 hpv - hpv51 defaults| =', selftest())
