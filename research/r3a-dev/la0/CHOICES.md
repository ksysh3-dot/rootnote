# Stage-0 lookahead experiment (section 14): implementation choices, locked before any evaluation song was run

Spec: docs/RESULTANT_CORE.md section 14 (branch research/resultant-core-20261030, HEAD 352d8f7) + coordinator amendment A1 (received after a
development pass on TRAIN songs and synthetic signals, before any evaluation song was processed).
Where section 14 is silent or ambiguous the most literal reading was taken; nothing below was chosen after seeing evaluation-song numbers.

## Amendment A1 (before results)
* V3h.rebound is replaced by RERISE: envelope = 5 ms boxcar RMS of the synthesized 150-600 Hz layer; reference = mean over 45..8 ms before the note end;
  first time after the note end below ref - 20 dB; RERISE = max envelope from that time to note end + 120 ms, dB above the -20 dB line, floored at 0
  (0 when the envelope never falls below the line); median over notes 2..39 of the 25 dB gated line, plus the count of notes above 6 dB.
  Rule (c) = tail -10 ms or more AND RERISE -6 dB or more.  The old definition is kept as information only (`rebound_old_info_db`).
* V7d burst = 10 log10(E_hit / E_ref), E_hit = mean power of the ten 10 ms boxes within +-50 ms of the hit, E_ref = median power of the forty 10 ms boxes in
  [-300,-100] U [+100,+300] ms; limit core <= max(+3 dB, P1 burst + 1 dB).  Time base: the acceptance excerpt LOGOFF 37-49 s rendered from 0 (3 s warm-up), hits at
  excerpt time 3.0 + 4.12 and 3.0 + 4.73 s (song time 44.12 / 44.73 s); the layer is on the latency-compensated input-time axis.

## Time axis and availability (the important reading)
* Stream sample j of bh / band = input time (j-191)/3000 + 1359/48000 s (section 3), minus 1.04 ms (the 3 kHz streams' phase delay at 100 Hz, measured on a
  clean 100 Hz note, t_delay.py).  P1 hop centres tc (P1 harmonic-trace header) are in input seconds; the P1 and core hop grids are identical (asserted).
* L_samp = round(3 L_ms) = 0 / 192 / 360 / 651.  L is the length of input usable after the output position t (section 14 definition).  A tracker hop
  (frame centre c, frame +-191 samples) needs the input up to c + 191, so it is usable at output position t iff **c + 191 <= t + L_samp** (TRK_LAG = 191).
  Consequences: L = 0 uses tracks that are 64 ms stale (chunks and f are held at the newest usable hop); L = 64 is exactly the current engine (hop c usable at t = c,
  LS windows up to 64 ms ahead); L = 217 sees hops up to c = t + 153 ms.  This follows the definition of L and the statement that 64 is free within the current delay.
* The literal-looking alternative "hop usable iff c <= t + L" (TRK_LAG = 0, L = 0 would then use a hop that already contains 64 ms of future) is run as a
  clearly labelled SENSITIVITY, not for the decision.
* Chunk start/end in output time: [c_first + max(D,0), c_last + hop + max(D,0)], D = 191 - L_samp.

## LA components
1. Chunks: runs of one tracker id over consecutive hops (all tracks with state > 0 of the P1 reference build's harmonic trace; id = r[0] + 65536 r[13]).  Two runs are
   joined when the gap <= 50 ms, the end/start frequencies differ <= 3 %, one-to-one greedy by gap, and the join is knowable at the gap start:
   gap <= (L_samp - 191)/3000 s (no joins at L = 0 and, with a zero-length gap only, at L = 64).  Gap hops are interpolated in f.
2. Short envelope e(t): single-chunk LS at the chunk frequency (ridge 1e-4 tr(G)/2), asymmetric Hann window of 10 ms = [t-(10-u), t+u], u = min(5 ms, L),
   evaluated every 4 stream samples (1.33 ms).  Frequency basis: tracker f(t) interpolated between hops, phase integrated, held at the newest usable hop.
3. Interval start: M = max e over [t_s, t_s + L]; t_on = first t >= t_s with e > 0.5 M.  L = 0: M = e(t_s) (literal "max so far from t_s"), so t_on = t_s immediately
   (degenerate but literal; also after a t_off).  Interval end: first t after t_on such that e < median(e over [t_on, t]) - 12 dB (running, causal median) and stays
   so for min(L, 50 ms) (checked with the lookahead); L = 0: the instant.  After t_off the t_on search restarts at t_off.  Intervals shorter than 4 samples are dropped.
4. Amplitude: A(t) on a 8-sample (2.67 ms) grid inside each interval.  LS window [t - N_p, t + min(N_f, L)], N_p = 320 and N_f = min(650, L_samp) (the caps; the spec gives bounds
   only), asymmetric Hann halves, each chunk's basis columns zero outside its own interval ([t_on, t_off] clipping).  All intervals active at that grid time are
   solved jointly (ridge 1e-4 tr(G)/(2V)), A_cap = min(A_joint, 2 A_single) (D2 cap, single solve with the same window/basis).  joint/single ratio p95 (before the cap)
   is reported over all joint solves with >= 2 active intervals of the evaluation songs.  Smoothing: boxcar over [t-(10-u), t+u] ms (u = min(5 ms, L)), clipped to the interval.
5. Decision (once per interval): features from the tracker hops usable at t_on (hops from t_on - 1 hop up to the newest usable hop, never beyond t_off; the single newest
   usable hop when that set is empty, i.e. L <= 64): log2 f, f jitter (cent std), median |df/dt|/f, decay slope (dB/s), median raw, median res, 2f and 3f evidence
   (strongest other track near 2f / 3f relative to this track, log-compressed), length (log1p(min(len, L)/hop)), integer-ratio lower track (flag + log ratio), nearest other track
   (cents, log ratio), number of tracks.  Weighted L2 logistic regression (Newton), features standardised on the weighted training set, weights normalised to mean 1, ridge 1.0
   on the standardised coefficients (identical for every L and stream; retrained per (stream, L)).  Training: Track00060/40/01/05/12 (0-30 s), label = right/wrong weight
   majority of the interval (V6b label, weight Af^2), sample weight = sum of Af^2.  p(note) < 0.5 -> the whole interval is off.  Gate: 5 ms linear fade-in at t_on,
   5 ms fade-out after t_off.  Oracle: same intervals, kill the intervals whose MIDI weight majority is wrong (synthetic signals: the known note frequencies; LOGOFF: none).
6. Synthesis (all rows): oscillators k = 2, 3 phase-continuous from f(t), a_k = P1 gain(f) w_k(f) rolloff (24 dB/oct above 220 Hz = upperBlend 1; verified to 1.0000 against the
   P1 harmonic trace), kOutSos causal filter at 3 kHz, x16 resampling to 48 kHz.  Voices: LA = one per ON interval (f held/interpolated as above); core = voices with state > 0, f = f_osc, amplitude
   A c sigma; P1 = tracks with state > 0, f, amplitude a fade (life ignored, as written in the spec).  Time stamps: LA at input time; core and P1 rows at hop centres plus a constant
   calibration offset (core -12 ms, P1 -11 ms) obtained by cross-correlating the proxy layer with the REAL layer on Track00060 36-48 s (a TRAIN excerpt, not a test signal).
7. V6b / right weight: weight of a voice-hop = (amplitude feeding the synthesis at the hop centre)^2; wrong = not within 50 cent of 0.5/1/2/3 x any sounding MIDI note of the song
   (drums included, bass shifted by the octave tp), hops with tc > 0.5 s.  This reproduces the suite per track to 4 digits for core v1.5.  Right-weight retention of an LA row =
   right weight with the classifier / right weight with every interval on (same stream, L); versus-core ratio reported as well.

## Metrics on the proxy layer (all rows identical code)
* E1: V3a = peak of the cycle-averaged 150-600 Hz layer power of the 9 s bass line (layer only, not output); V3h rise90 on the isolated 1 s note and on the 25 dB gated line;
  V3c.enter = median over notes of the first hop in the first 125 ms at which the dominant voice (largest amplitude) is within 2 % of the new note (inf counts as a miss).
* E2: V3h tail "stable" (안정 꼬리) = last time the 5 ms RMS envelope is above -20 dB re the note level within 120 ms after the note end (this window ends 5 ms before the next
  note and therefore sees pre-echo of the next onset); the first-crossing tail is reported too.  RERISE: amendment A1.
* E3: V5a on Track00060 36-48 s (low-bin fraction, suite definition).  E4: V6b eval-5, without Track00024, retention.  E5: V7d burst (A1).
* Guards: V3d on the 9 s bass line (notes 2..15, suite formula = causal 10 ms power, LS-line baseline over [t0-150,t0-50] extrapolated to the window centre) and on the 25 dB gated
  line (notes 2..39) in the PLAIN form of the spec words: rise = dB(mean power [t0-30,t0]) - dB(mean power [t0-150,t0-50]); median <= 1 dB for both.  Reason (decided before the
  evaluation songs, after the development pass): the suite's line-extrapolation form gives +50 dB for the REAL P1 layer on the gated line (tail -> floor window, steep fitted slope), i.e.
  it is not a usable measurement there; the plain form gives -25.8 dB real P1 / -31.7 dB real core, reproduced by the proxy (-30.0).  The suite form is kept as information
  (`v3d_line_suite_info`).  The power is floored at -60 dB re the layer's own p90 (the gated proxy layers contain exact zeros).  V4b on bass+kick+pink (suite formula, Hann 20 ms bins at 300 Hz, <= 2 %); V9 pink only (births/s <= P1, energy <= P1 + 3 dB,
  window 0.5-9.9 s); V3i substitute = gate flips/s of "a voice within 5 % of 100 Hz is on" on the SNR 8 dB tone (window 1.0-9.9 s), <= 1/s; right weight kept >= 90 %.
* P1 limits use the P1 PROXY row (same synthesis).  The proxy P1 layer lacks the real P1's envelope forcing and percussive layer: it matches the real P1 layer on V4b, V6b, V5a,
  V3i but NOT on tail, RERISE, V3a, V3d, V7d (calibration table in the report).

## Findings recorded before the evaluation run (development pass: TRAIN songs + synthetic signals)
* bass+kick+pink (V4b): the P1 tracker itself has no state>0 track within 5 Hz of 100 Hz in 269 of 1050 note hops (25.6 %), core v1.5 has a voice in all 1050 (coasting, section 5.2).
  Section 14 joins runs only across gaps <= 50 ms, so every LA row inherits the tracker's dropouts (V4b 20-25 %, limit 2 %).  This is a property of the specified inputs, not of the
  implementation (checked hop by hop).
* The 10 ms envelope e(t) cannot separate pitches closer than ~100 Hz; on the step line (98/104/110 Hz) the 98 Hz chunk's interval stays open through the 125 ms gap and ends ~36 ms
  after the next onset at L = 64 and 120 (interval listing in the report), so the long future window pulls the next note's energy early (onset lead -8 .. -35 ms).

* Bass line (V3d-bass): at every L and both streams the whole 9 s line is ONE interval of the 100 Hz chunk (diag_intervals.txt): the 350 ms decay ends only ~12 dB below its peak, so e(t)
  never falls 12 dB under its running median, no t_off exists at the same-pitch re-attacks, and for L >= 64 the future half of the LS window (min(650, L)) pulls the next attack forward
  (V3d 0.00 dB at L = 0, 1.0-3.8 dB at L >= 64).  The guard therefore fails at every L >= 64 for a reason that belongs to the specified boundary rule.

## Readings added by the implementer (flagged)
* The "4 of 5 songs in the same direction" requirement is applied as a GATE only to V6b; for the right-weight retention the per-song direction count (songs up / down) is printed beside it and
  the 90 % level is the guard.  (Section 14 names both; the retention deltas are mostly mixed in direction.)
* "Stable tail" (안정 꼬리) = settled tail (last time above -20 dB within 120 ms after the note end); this window ends 5 ms before the next onset, so a layer that starts early
  (pre-echo) reads 120 ms.  The first-crossing tail is printed next to it and rule (c) is annotated when it is met only through the settled tail.
* Rule (a): the specification asks for a 95 % interval and >= 4/5 same-direction songs; requiring the interval to exclude 0 is the implementer's addition (both flags are reported).
* Guards that name "P1" use the P1 PROXY row (same synthesis); the real P1 layer differs on tail / RERISE / V3a / V7d (no envelope forcing or percussive layer in the proxy), real values are
  in the calibration table.

## Decision rule implementation (mechanical)
* "clearly better" X over Y = guards of X all within limit AND at least one of: (a) V6b pooled delta <= -5 %p with >= 4/5 songs negative, 4/4 without Track00024, and the clustered
  bootstrap (5 s windows within song, 10,000 resamples, ratio of sums) 95 % interval below 0; (b) V5a <= -2 %p AND V3h rise90 <= -5 ms on BOTH the bare note and the 25 dB line
  (the OR variant is reported); (c) tail(stable) <= -10 ms AND RERISE <= -6 dB.
* Stream (bh vs band): endpoint wins over the 11 E1-E5 endpoints (V3a distance to 21 ms, rise90 bare, rise90 line, enter, tail, RERISE, V5a, V6b, V6b without T24, burst 4.12, burst 4.73),
  a win = better by more than the rule threshold of that endpoint (V3a/rise/enter 5 ms, tail 10 ms, RERISE 6 dB, V5a 2 %p, V6b 5 %p, burst 1 dB), summed over L = 64 and 217;
  tie -> bh.  The rule is then applied to the chosen stream (the other is shown).
* "better than core v1.5 on E1..E5": a group is better when its endpoint wins exceed its losses (same tolerances); 3 of the 5 groups are needed.
