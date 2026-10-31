# Plan16 F2 (section 16.18): reading choices, fixed BEFORE any F2 number was computed

Spec: docs/RESULTANT_CORE.md 16.18 (+16.17 for guards/decision rule). Slakh TRAIN only, nothing else under slakh2100. Code in ~/r3a-dev/plan16/F2/. F/ helpers reused (fcommon, f_burst, f_right, v0_check).
Exploration done before writing this: read-only reading of pvb_vb52.cpp core52 (what the HPSS streams are) and of pvb_resultant.inc hop/amplitudes/synthesize; no metric, no ratio, no energy computed.

## 1. Hit cue (causal, in the core, per hop)
* Energy buffer: the engine's existing `percEnv52_` (VbHpv private; reachable from ResultantCore because pvb_resultant.inc is in the same TU and friend). It is the exponentially smoothed square of the HPSS percussive sample bp (attack 2 ms, release 40 ms) of the 32-190 Hz band path, i.e. P energy of the 40-200 Hz band to the extent the engine's own band-pass defines it (no extra filter, no new state in VbHpv: pvb_vb52.cpp is untouched). It is read once per hop in ResultantCore::hop, at the hop's call time (it has just seen bp of ring slot ih - 191, the analysis centre).
* Rule: E(h) = percEnv52_ at hop h. Median M(h) = median of E over the previous 16 hops (85 ms), the current hop excluded (ring of 16 doubles, filled with the hop values also when not measured). Cue iff E(h) > 10^(0.9) * M(h) (+9 dB) AND E(h) > 1e-8 (absolute floor, -80 dB re full scale in the band, only against digital silence) AND hops since the last cue >= 19 (refractory 100 ms, longer than the longest window) AND at least 16 hops have been seen. Cue hop = h_d, t_d = hop time of h_d.
* Offline (stage 0) the same E series is rebuilt from the stage capture column `original_p` with the engine's smoothing constants (attack exp(-1/6), release exp(-1/120)), sampled at core index i_h = 383 + 16 h.

## 2. Voice eligibility
* Voice age = hopCount_ - onHop (hops since it became ON; onHop is set at birth to ON). Eligible iff state == On AND age >= 10 hops (53 ms >= 50 ms) AT h_d. Decided once at the cue hop; a voice that is CAND, REL, Fade or younger than 10 hops at h_d is never touched in this window (births and CAND untouched, as the spec). A voice born later during the window is also not touched.
* A voice that stops being ON during the window (REL) keeps its already fixed limit until the window ends (it can only fall).

## 3. amp_pre and the limit
* amp quantity = the synthesis amplitude base = A * c * sigma of the voice (what `amplitudes()` multiplies into all partials; trace amp = A c sigma).
* amp_pre = base of the same voice 3 hops (16 ms) before h_d (small per-voice ring of the last 8 base values, hop-indexed). Reason: LS future 24 samples (8 ms) plus the cue latency one hop; 16 ms is outside the kick's own influence in the fit. If that older value was not defined (voice younger) the voice is not eligible (age >= 10 hops makes this impossible).
* Limit L = amp_pre * 10^(cap/20). In the window [h_d, h_d + W] (W in ms, hop count = ceil(W / 5.333)) the synthesis base is min(base, L). After the window a linear 10 ms release (2 hops): limited base blends linearly from min(base, L) to base over the 2 hops. The cap acts on the SYNTHESIS amplitude only (a multiplier in `amplitudes()` on the partials); A, A1, the LS, the weights, SNR and every state transition see the uncapped values, so the analysis path is unchanged (off = bit-identical).
* Parameters: two new parameters at the end of the list (18 values): `riseCapDb` (index 17; 0 = feature OFF = default; otherwise the cap in dB, range 0.5..24) and `riseWinMs` (index 18; default 80; range 10..200; ignored while riseCapDb = 0). Grid: riseCapDb in {3,6} x riseWinMs in {40,80}. ("cap 0 dB" is not representable; stage 0 holds at 0 dB offline only.)

## 4. Stage 0 oracle (offline, no C++)
* Source: v1.5 (HEAD lib, F/build_v15) LOGOFF excerpt 37-49 s through M.Ctx (level 0 and -120, out_db -5), voice trace + stage capture.
* t_d = first offline cue hop at or after the input hit time 7.12 s - 30 ms (render time 3.0 + 4.12). Hold = cap 0 dB, W = 80 ms, ramp 10 ms (as the C++ will be), eligible voices as in section 2, amp_pre as in section 3.
* Synthesis: plan16/D render path = synth16 engine harmonic set (k = 2..8, engine_gains), phase = cumsum of the trace fosc, amp = trace A c sigma, kOutSos, upsampled x16 to 48 kHz. Burst = F/f_burst.py's E7.burst R1 on (a) the synth-only sustained layer, base vs held, and (b) engine layer + g * (held - base) with g (and a time shift) fitted by LS of the engine layer on the base synth around the hit. Both reported; gain = base - held burst.
* Birth / rise split: energy in 150-600 Hz in the burst window [c-50, c+50] ms of (i) the whole base synth, (ii) voices that are eligible old voices only (actual amp), (iii) the same with held amp, (iv) all other voices (births, CAND, young). The rise part = E(old, actual) - E(old, held); birth part = E(others).
* Stop rule: gain < 2 dB on the primary reading -> STOP, no C++. Primary reading = (b) when its fit correlation is >= 0.7, otherwise (a). Fixed here before the number is seen.

## 5. Hit-detection count, cap activity (reported)
* hit-detection count per song = number of cues in the render (counter exported by a research-only function pvb_resultant_rise_stats, built with -DPVB_RESEARCH_CAPSTATS, as F/patch_d2), cap activity = voice-hops where min() changed the base / voice-hops inside windows of eligible voices.

## 6. Re-attack guard (new)
* Synthetic (16.10.1 B1 bkp-click (i) recipe: the existing `sig_bass_kick_pink`/bkp family in research_core_signals; I use the same bass-with-click-kick construction): same-pitch (98 Hz) repeated bass notes, one every 0.5 s, 0.35 s long with exponential decay, a short click-kick (60 Hz decaying sine + click) at EACH onset, plus pink noise as in the bkp family. Metric: rise90 of the layer envelope after each re-attack onset from t_onset - 20 ms to the peak, average over notes 3..N. Limit: rise90 <= v1.5 + 5 ms. The exact script (f2_reattack.py) is written and run after the lib is built; details of the parameters of the signal are fixed in that file before it is run on the F2 lib and recorded below if they differ from this text.

## 7. Everything else
* Guards of 16.17 (V3a peak, rise90, V3b, V3i, V4b, LOGOFF 4.73 s R1, V3e 10 Hz beat, right-layer F on the 10 dev songs) via the F/ suite runner (fmetrics.py generalised to the two new parameters) and F/f_right.py (trace-based as 16.9), unchanged definitions. P1 row from the existing baseline JSON.
* Selection and decision rules: 16.17/16.18 mechanical; ties within 0.5 dB -> softer = cap +6, W 40.

## Post-run additions (2026-10-31; nothing above edited)
* Stage 0: the offline cue nearest the nominal hit has centre time 7.063 s (57 ms before the nominal 7.12 s), so the cue search window is widened from [HIT-30, HIT+50] ms to [HIT-100, HIT+50] ms (first cue in it). Only the cue time had been seen; no burst number.
* Stage 0 result (f2_oracle.json): registered hold (cap 0 dB, W 80 ms, ramp 10 ms, age >= 50 ms) gain = 0.55 dB < 2 dB on the primary reading (fit corr 0.43 < 0.7 so reading (a)); STOP rule fired, no C++ written. Information only (f2_oracle_info.json): W 120-160 ms would give 5.6 dB, because the 78->105 Hz voice (id 462) rises 70-100 ms after the cue.
