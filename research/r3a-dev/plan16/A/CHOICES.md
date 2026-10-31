# Plan16 A (section 16.1-16.3): reading choices, fixed BEFORE the ladder numbers were computed

Spec: docs/RESULTANT_CORE.md 16.1-16.3 (HEAD 9b0e52b).  Slakh TRAIN only.  Code in ~/r3a-dev/plan16/A/, LA prototype from ~/r3a-dev/la0 (unchanged, cached LA results reused).
Written before ladder.py was run.  The leak test (16.1), the synthesis check (16 common) and the R3-a code audit (16.2) do not depend on these choices and were run first.

## 16 common (synthesis)
* Engine set: k = 2..8 while k f <= 700 Hz, a_k = g(f) w_k(f) r_k A, voicing 0 (gl = 1), r_k = 1 for k f <= 220 else g12 + 1.0 (g12^2 - g12) (vbAlpha2_ = VbHpv{true,true,1}: gentle, upperMode 1 -> upperBlend fixed at 1),
  g12 = 10^(-12 log2(fk/220)/20).  `lookup()` = numpy.interp-then-linear tables (tables.py port; the pvb_vb_tables.h of r3-work and r3-ref-core are identical).  Output filter kOutSos unchanged.
  Phases are free (cos(k * integrated f)); no psi alignment (as in section 14).
* All rows (R0..R3, P1 reference) use this one synthesis (`synth16.render_layer16`).

## Songs and time bases
* Ladder songs: the 10 V6 TRAIN songs (`common16.TRACKS`, equal to LA `TRAIN + EVAL`), excerpt 0-30 s, plus the T60 V5a excerpt (Track00060 36-48 s, excerpt time; V5a only).
* Energy / pre-echo / V6b use t > 0.5 s (hops with tc > 0.5, the V6b convention).

## Truth segments (R2/R3 and the ladder's strict truth)
* Bass MIDI = the notes of the 'Bass' class stems (`X.bass_stems_and_notes`), f = 440 * 2^((pitch + tp - 69)/12) (tp = the YIN-consensus octave of `common16`).
* At every time the truth is the LOWEST sounding bass note.  A segment is a maximal time run in which the same bass note is the lowest; a boundary is any change of the lowest note.
  A segment start is an ATTACK (re-attack) if the new lowest note starts at that time; it is a fall-through (no attack) if the lowest note ends and a higher still-sounding note takes over.
* Chunk of R2/R3 = one segment, constant f_true, interval [MIDI start, MIDI end] (j_on / j_off in stream samples via `stream_index`).  Segments shorter than 4 samples at 3 kHz are dropped.

## Right / wrong of a voice-hop (R0, R1, P1 rows)
* PRIMARY = the V6b definition used everywhere in sections 13-14: right iff within 50 cent of 0.5 / 1 / 2 / 3 x ANY sounding MIDI note (drums included, bass shifted by tp).  This is also what the R1 oracle (14, whole-interval weight majority) uses, so R1 and the wrong-energy column are consistent.
* STRICT (information; the ladder decision is also re-run with it): right iff within 50 cent of 0.5 / 1 / 2 / 3 x the lowest sounding BASS note f_true(t).
* Hop-level: voice frequency at hop centres tc (P1 hop grid), classification held between hop centres (nearest hop).
* R2/R3 voices carry f_true exactly: right by construction under both truths (checked numerically, not assumed).

## Energies
* Layer energy = sum of squares of the 3 kHz layer (after kOutSos), t > 0.5 s.  Right layer / wrong layer = the layer rendered from the right-only / wrong-only amplitude (same phases, linear, so right + wrong == the full layer; cross terms exist, so the energies do not add).
* Pooled = sums over the 10 songs.  Per-song values are tabulated as well.
* Fixed-denominator wrong energy = wrong-layer energy / R3 right-layer energy, pooled.  "Right layer vs R3 in dB" = 10 log10(E_right_row / E_right_R3), pooled.
* Matched-gain variant (M): ONE global gain per row, chosen so that the pooled right-layer energy equals R3's (so within +-0.5 dB by construction; the per-song deviation is reported); wrong energy scales with the same gain^2.  The P1 reference row is matched the same way.
  Fixed-gain variant (F): gain 1.
* Pass conditions are evaluated in both variants and the decision rule is applied to both: M = {cond 1 matched, cond 2 by construction, cond 3, cond 4}; F = {cond 1 fixed, cond 2 measured, cond 3, cond 4}.  The headline is stated for both; if they disagree both are reported (no tie-break invented).
  cond 1: wrong-layer energy / R3 right energy <= 0.5 x the same quantity of the P1 row (same variant).  cond 2: right layer >= R3 - 1 dB (fixed gain).  cond 3: V5a <= 5 % on the T60 excerpt.  cond 4: pre-echo <= 1 dB.
* V5a (suite definition, `metrics.v5a`) on the layer of each row for the T60 36-48 s excerpt, 48 kHz-resampled layer as in section 14.  V5a is level-invariant.

## Pre-echo (V3d style, on real music)
* Plain form of section 14 (the suite's line-extrapolation form is unusable, CHOICES of la0): rise = dB(mean layer power over [t0-30, t0]) - dB(mean layer power over [t0-150, t0-50]), power floored at -60 dB re the layer's own p90 power (same rule as la0 metrics.v3d).
* t0 = segment attacks (MIDI bass onsets, lowest-note attacks) with t0 in [0.6, dur-0.3] s and NO bass note sounding in [t0-150 ms, t0) ("gap attacks"): only there the layer before t0 should be quiet, so a rise is pre-echo.  Statistic = median over all gap attacks pooled over the 10 songs, N reported.  Legato attacks and fall-throughs, the p90, and the excess over R3 are information.

## LS of R2 / R3
* Reuse `la.solve_amplitudes` unchanged (window [t - 320, t + 191] samples, asymmetric Hann, basis clipped to the segment interval, 8-sample grid, ridge 1e-4), `la.smooth` (10 ms zero-phase boxcar, within the interval) and the 5 ms fades of `rows.voices_la` - the same as R0.  Implemented with L_ms = 191/3 so that N_f = 191 and the tracker lag term vanishes (D = 0).
* R2: mix bh stream (the stream of R0).  R3: bh stream of the clean bass stem SUM rendered through the same engine capture (includes HPSS and band selection, same time axis).  A raw-decimation sensitivity is only run if R3 fails.

## R0 / R1
* R0 = cached LA-bh-64 (TRK_LAG 191), classifier trained on the 5 TRAIN songs (`pipeline.train_models('bh', 64, 191)`), identical to section 14.  The 5 TRAIN songs are IN-SAMPLE for the classifier (flagged in the report); eval-5 numbers are given separately.
* R1 = the same intervals, oracle on (V6b whole-interval weight majority, ties -> right) = `ORA-bh-64` of section 14.

## Decision rule
* Mechanical, "first failing row from R3 downward": R3 fails -> synthesis/band/weights; R3 passes and R2 fails -> amplitude attribution in the mix; R2 passes and R1 fails -> candidates / segmentation; R1 passes and R0 fails -> selector; all pass -> no bottleneck in this ladder.  All four flags of every row are shown, so non-monotone outcomes are visible.

## R2 MIDI boundary vs stem activity
* Stem envelope = 10 ms boxcar RMS of the stem bh stream.  Per segment: peak P = max envelope within [start, end]; activity = the contiguous region around the peak with envelope >= P - 20 dB, searched inside [max(start - 150 ms, previous end), min(end + 500 ms, next start)].  d_on = stem_on - MIDI start, d_off = stem_off - MIDI end; segments with P < (song 95th percentile of the stem envelope) - 40 dB are "no stem activity".
* Information row R2s = R2 with the stem-activity interval instead of the MIDI interval.


## Post-run additions (information only; appended after ladder_report.txt existed, nothing above was edited)
* The raw-decimation R3 sensitivity announced above was run because R3 failed (cond 3, V5a): `extra.py` X1.  Raw R3 = stem sum, 2nd-order 32-190 Hz band-pass (zero phase) at 3 kHz after `resample_poly(1,16)`, linearly interpolated onto the bh index axis through `stream_time(j)`; no HPSS, no band selection; the same LS / synthesis / V5a code as R3.
* X2: core v1.5's voice list (`rows.voices_core`, calibration lag of section 14) through the same k = 2..8 synthesis, V5a; also through the k = 2, 3 synthesis of section 14 (reproduces the 5.2 % of 14.1).
* X3: V5a drop bins of every row vs polyphony (a second bass note sounding) and distance to a truth-segment boundary (< 50 ms).
* X4 (leak test): the layer amplitude in [T-L-64 ms, T-L] was inspected for the T40 excerpt to decide whether a "pass" is informative.
* The specified decision rule is the one stated under "Decision rule" above.  The line "sensitivity ... ignoring V5a" in ladder_report.txt is NOT part of the rule; it is printed so the reader can see which condition decides.
