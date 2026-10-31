# Plan16 P (section 16.15): reading choices, fixed BEFORE any E_sil / E_act / rho number was computed

Spec: docs/RESULTANT_CORE.md 16.15 (+16.8.1 act15, 16.9 V values, 16.14). Slakh TRAIN only (reads `X.SLAKH/<Track>/mix.flac` and `common16.ref` MIDI/stem for the 10 V6 songs; no validation/test path touched). Offline Python, no engine/doc/other-folder edits, no commit.
What was looked at before this file: the layer-extraction check (verify1.py / verify2.py, one song then a second: energies of whole signals only, nothing split by silent/active) and the time-alignment calibration (p_align.py, comparison of layer ENVELOPES with the 16.9 trace-based layer; no silence/activity split). Both are reported below as evidence for the choices.

## 1. Capture point
* `pvb_set_diagnostic_capture` + `pvb_copy_diagnostic` per 256-frame block (the capture only holds the last block). Source: `Engine::process` in `pvb_engine.cpp`: `diagnosticLayer_ = delayedLayer * (mix*fade*gate*vbx*limiter gain)`, where `delayedLayer = vg*layer*og` = the generator layer after the engine's output filter/gain, delayed by the limiter latency so it is aligned with the output; BEFORE the sum with the dry path and the limiter. This is generic engine code (not per algorithm), so it is the SAME point for algo 15 (core) and algo 6 (P1). The fall-back (vb on - vb off, ceiling limiter off) is therefore NOT needed.
* Check (verify2.py, Track00001 and Track00025, both algos, 0.5-30 s): `output - layer` equals the vb-off render (aligned with its own latency 88; vb-on latency is 7140) to max abs 2.9e-8 (rms 2e-9, relative 3.5e-8); `(vb on - vb off)` vs captured layer: corr 0.99999999999997, relative diff 2e-7. So layer + dry path = output, the limiter does not intervene (same equality), and `output - layer` is identical between core and P1 (dry path is algorithm independent). The two channels of the layer are identical (max |L-R| = 0); the mono layer is used.
* Render: default `T.Engine` parameters (as plan16/L/build.py: vb_on 1, ramp 0, `vb_level_db`/`out_db`/ceiling at their defaults), block 256, `y[latency:latency+30 s]`, 31 s excerpt from 0 s (`X.read_excerpt`), core with `CA.set_resultant(lib, e)` defaults. Library: `build_core/libpvbcapi.so` (sha256 in render_info.json). Songs: the 10 V6 songs, the same 0-30 s excerpts as 16.9.

## 2. Band, energy, units
* Band 150-700 Hz: 4th-order Butterworth band-pass (SOS), applied zero-phase (`sosfiltfilt`) on the 48 kHz mono layer. E = sum of squared band samples over the selected sample set.
* Units: the captured layer is on the physical output scale, the 16.9 numbers on the synthesis scale of the trace layer. kappa = sum over the 10 songs of E_trace / sum of E_cap (core, 150-700 Hz band, t >= 0.5 s; from p_align.py) is applied to BOTH engines (same constant), and energies are reported as kappa*E / R3R with R3R = 59.3507 (pooled R3 right energy). rho is a ratio, so kappa does not affect it. The absolute values are only comparable to 16.9 numbers up to this calibration.

## 3. Hop and frame
* No hop/frame: the classification of time is done per 48 kHz output sample (the activity mask is a union of time intervals; drum windows too). Band filtering is zero-phase (smearing of a few ms at 150 Hz at activity edges; accepted).

## 4. Time alignment
* Output index i (after removing the engine latency 7140 samples) is taken as input time t = i / 48000, for both engines, without a further shift. Evidence (p_align.py, 4-30 s, 10 songs, correlation of 150-700 Hz band envelopes (10 ms boxcar) between the captured layer and the 16.9 trace-based layer that already carries the core LAG (-12 ms) / P1 lag (-11 ms)): residual shift of the captured layer relative to the trace layer, median +0.52 ms (core) and +1.29 ms (P1), per song -6.2 .. +5.6 ms, correlations 0.88-0.98 (except Track00024, a no-bass song: 0.73 core / 0.49 P1, shift -5.5 / -6.2 ms; low correlation, so its shift is not trusted and it does not move the median). All well inside one tracker hop (5.33 ms). Rule fixed before the metrics: apply a shift only if the median exceeds 3 ms; it did not, so none. The LAG is thus already inside the engine path (the trace-based pipeline shifts voices by it; the output layer needs nothing extra).
* Drum hits `rf['drum_on']` and stem activity are in input (excerpt) time.

## 5. Activity ("act" = bass sounding) and silence
* Truth segments `LD.segments(key)` (lowest-bass-note runs, MIDI) and `act15(segs, bz)` (stem 40-220 Hz envelope, -15 dB of the segment peak, plan16/D `dcommon.act15`, exactly as in 16.8.1/B1).
* Active interval of segment k = [s_k, O_k], O_k = act15 off if the segment has stem activity else the MIDI end e_k (same as `SATruth.O_`: start at the MIDI start; only the time AFTER the MIDI end is extended to the stem activity end, never before the start). Active mask = union of intervals; silence = everything else. (If act15 off < e_k the interval ends at e_k.)
* Sensitivity variants, reported but not used for the rule: (i) also extending to the stem rise before the MIDI start (act15 `on`), (ii) pure MIDI [s_k, e_k].
* Songs without bass MIDI in 0-30 s (Track00023, 24, 26): no active interval, all of the song is silence, E_act = 0, rho undefined.

## 6. Judged range
* Main numbers: t >= 4 s (spec). Whole-excerpt values (t >= 0.5 s, the 16.9 range; the first 0.5 s are dropped as in all earlier plan16 numbers) are reported next to them.
* Pooled = sums over the 10 songs; T24, T25, T26 are reported separately; also pooled without Track00040 (information).

## 7. Metrics and the rule (applied mechanically)
* E_sil = band energy over silent samples, E_act = over active samples, rho = E_sil / E_act (pooled and per song). rho_P1/rho_core = r.
* Drum-near share of E_sil: share of E_sil on samples with a drum hit d (any drum pitch, `rf['drum_on']`) such that d - t is in [-150, +20] ms (= the 16.9 / V convention t - d in [-20, +150] ms: the layer follows the hit). Pooled and per song.
* Validity: Spearman (scipy `spearmanr`, ties averaged) over the 10 songs between the core output-based E_sil (main: t >= 4 s; also t >= 0.5 s, the range of V) and the 16.9 trace-based silence wrong_sa per song (`plan16/V/v_raw.json`, `E_sil` of the silence-class voices; unit R3R, t > 0.5 s). If rho_s < 0.7 for the main version, no decision is made, only reported (spec). If the two versions straddle 0.7 this is flagged.
* Rule, fixed here from 16.15:
  * (A) r <= 0.5 pooled AND the same r <= 0.5 holds on >= 2 of T24, T25, T26.
  * (B) 0.75 <= r <= 1.33 pooled.
  * (C) rho_core <= 0.75 rho_P1 pooled, i.e. r >= 1/0.75 = 1.3333.
  * else mixed: record per-song values, Opus decides. (A with the per-song condition failing is "mixed".)
* Gap in the pre-registration, handled as follows (flagged): T24 and T26 have no bass in 0-30 s, so E_act = 0 and rho is undefined for them; only T25 can enter the "2 of 3" condition with a true rho. The strict rule is therefore reported as is (at most 1 of 3 evaluable). As the substitution used for the per-song condition (reported alongside, never replacing the strict result) I use rho* = E_sil(song) / E_act(pooled, same engine, same t range), which keeps the "remove the overall layer size" normalisation. Opus judges which reading to follow.
* Reports only (no rule): E_act of both engines; per-song rho; drum-near share.

## Post-run additions (appended after the first p_main run; nothing above was edited except one wording fix before any metric was computed)
* Unit correction (2026-10-31): the first p_main printout used kappa from p_align (energy per 3 kHz interval) with sums over 48 kHz samples, i.e. all unit-scaled values were 16x too large. kappa was divided by 16 and p_main rerun; rho, r, shares and Spearman values are unit free and did not change. The tables in p_report.txt are the corrected run.
* Extra check added after seeing the Spearman result (p_check_trace.py, flagged as post hoc, not part of the rule): the same time-silent band energy measured on the 16.9 trace-based layer (core and P1 reference trace). Captured vs trace-layer E_sil: Spearman 1.000 (core) / 0.952 (P1); pooled rho 0.1870 vs 0.1869 (core) and 0.1313 vs 0.1299 (P1); r 0.702 vs 0.695. So the output capture reproduces the trace-based layer; the Spearman gap to the 16.9 wrong_sa numbers (0.636) is the same on the trace side (0.636), i.e. definitional: 16.9 counts only the wrong-pitch energy of silence-CLASS voices (voice-level occupancy), full band, whereas 16.15 counts all layer energy in bass-silent TIME in 150-700 Hz.
