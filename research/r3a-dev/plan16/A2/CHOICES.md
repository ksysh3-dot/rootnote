# Plan16 A2 (section 16.6): reading choices, fixed BEFORE the classification was computed

Spec: docs/RESULTANT_CORE.md 16.6. Slakh TRAIN only (Track00060 excerpt 36-48 s). Reuses plan16/A (cache/ladder_y3.pkl for P1, R2, R3; stems cache).

1. Drop bin = suite V5a definition (metrics.v5a): "bass present" 20 ms bin (idx of v5_setup) whose layer/stem ratio is > 6 dB below the median of present bins within +-250 ms. Bin time = excerpt time 3.0 + tcen.
2. Rows: R3, R2 = cached ladder layers; core v1.5 = voices_core + E.shift(core lag) through render_layer16 (k<=8, as 16.5 X2); P1 = cached ladder layer (k<=8 synthesis of the ladder, as in the 16.5 table).
3. B: bin centre within <= 50 ms of ANY MIDI bass note start or end (every note of the song reference, not only lowest-note segment boundaries), or of the start/end of a stem-activity interval (same stem_activity as R2s: segments' stem on/off, active ones only). Distances in excerpt time.
4. T: bass-stem-sum (the V5a stem, X.bass_stems_and_notes) energy in the same 20 ms bin (B = 960 grid), ratio = dB(150-600 Hz energy) - dB(40-150 Hz energy) (band_fft over the whole song as in v5_setup). Local median = median of that ratio over present bins within +-250 ms (same neighbourhood as V5a's 500 ms window). T iff bin ratio > local median + 6 dB.
5. W: applied to every row against the SAME set: a bin is W iff it is not a drop bin in the flat-weight R3 counterfactual (spec literal). For rows other than R3 this is a reading of the spec (W then means "a flat-weight clean-stem layer would not drop here").
6. Flat counterfactual: a_k = g(f) * 1 for all k = 2..8 with k f <= 700 Hz (w_k r_k = 1); g(f) from the lookup kept; phases, LS amplitudes, intervals, output filter unchanged. "Same gain matching": V5a is level-invariant (median-relative ratio), so no gain matching is applied.
7. Stem-activity counterfactual: R3 (clean stem stream LS) with the intervals of R2s (stem-activity interval where active, MIDI interval otherwise), normal weight table.
8. Order B > T > W > O (first match). Interpretation rule uses R3 only: share W >= 50 % -> weight table is a real synthesis problem; else B+T >= 50 % -> floor comes from the measurement; else neither. Percent of R3 drop bins (denominator = R3 drops).
9. Relative criterion: V5a(row) - V5a(R3) <= 2 %p, R3 = k<=8 ladder R3 (same synthesis, same excerpt). P1 and R3 always reported together.
