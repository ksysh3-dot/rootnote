# Plan16 L: reading choices and excerpt selection, fixed BEFORE any pair was rendered

Spec: docs/RESULTANT_CORE.md 16.11 (+16.9 silent-voice definition), brief_l.md.  Slakh TRAIN only (T25, T26 mix.flac of train; no validation/test path touched).  No engine code edited, nothing committed.

## Score
* Series = core v1.5 silence-voice stem-aware wrong layer, ALL causes (plan16/V `one_song`, unchanged; components 3..7 of `render_multi` summed, kOutSos-filtered, 3 kHz, input-time axis i/3000, lag already applied).  `score.py` -> `sil_series.npz`.  Check: T25 E_sil 6.8531 (= 0.1155 R3R units, 54 % of 0.211), T26 3.0620 (0.0516): equal to V's numbers.
* Window score = sum of y^2 over the window, samples with t > 0.5 s only (16.9 convention).  Units below = score / R3R (R3R = 59.3507, same unit as 16.9).
* Excerpt = the 30 s analysis excerpt, mix.flac seconds 0-30 of each song.

## Test windows (9 s, hop 0.25 s, start >= 1.0 s so that the engine is settled and t > 0.5 s holds)
* Reading 1 (deviation from "top 3 non-overlapping" literal greedy): a 30 s excerpt holds exactly three disjoint 9 s windows with only 3 s of slack, and a greedy top-3-by-score fails for T26 (it finds only 2: 19.25, 5.5).  So the three windows are the mutually non-overlapping triple with the LARGEST SUM OF SCORES (brute force over all starts); they are then ranked by score.  For T25 the greedy and the optimal triple agree up to 0.25 s shifts (greedy 20.75 / 11.75 / 2.75).
* T25: 21.00 s (0.0723), 12.00 s (0.0358), 3.00 s (0.0074).
* T26: 21.00 s (0.0210), 2.75 s (0.0199), 11.75 s (0.0107).

## Null windows
* "4th-best non-overlapping" does not exist: a fourth 9 s window cannot fit in 30 s without overlapping the three test windows of its song, and the "best remaining window of either song" fallback has the same problem (each song's excerpt is filled by its own three).  Reading 2: the null window of each song = the window (start >= 1.0 s, hop 0.25 s) with the SMALLEST total overlap with that song's test windows; ties by highest score.
* T25 null: start 1.00 s (0.0033), overlaps the 3.00 s test window by 7.0 s.  T26 null: start 1.00 s (0.0189), overlaps the 2.75 s test window by 7.25 s.  So nulls are NOT disjoint from test windows: the same passage can be heard in a test pair and in a null pair.  Reported to Opus.
* One null pair is core|core, the other P1|P1; which null gets which: seeded RNG (below).

## Rendering
* Library: build_core/libpvbcapi.so (same build for both sides), vb_algo 15 (core v1.5, Resultant parameters = research_core_api DEFAULTS, voicing 0) versus vb_algo 6 (P1).  Engine = the `research_r4l6c_render_pairs.py` convention: `T.Engine(lib, 48000, vb_on=1, vb_algo=a, ramp_ms=0)` with the engine default parameters (out_db -5, ceil -1, vb_level_db 0, hp 100 Hz ...), block 256, output = y[latency:], i.e. the mix + layer through the output chain, the same output gain for both.  No phone-speaker simulation and no fixed loudness target exist in that script.
* Pre-roll: each song is rendered once per algorithm from second 0 of the mix (31 s fed so the output covers 30 s after the 146.9 ms latency), windows are cut out of that continuous render, so the engine is settled by construction.
* Per pair: file = A (9 s) + 1 s silence + B (9 s), 48 kHz, stereo, PCM_16 (as listen/blind_inj), 10 ms fade at each segment edge.  B scaled to A by full-band RMS (both channels, 9 s); then a common scale min(1, 0.95 / pair peak).
* Seed 20261031, `np.random.default_rng(seed)`, draws in this order: (1) permutation of the two null types over [T25 null, T26 null], (2) permutation of the 8 items [6 tests in the order above, T25 null, T26 null] giving file numbers 1..8, (3) one side bit per test pair (nulls need none).
* Spots: per pair, 1 s windows (hop 0.25 s) inside the 9 s window ranked by core v1.5 silence wrong energy in that window (same series, same rule for test and null); greedy non-overlapping top 3, listed in time order, same times for A and B (+10 s for B).
