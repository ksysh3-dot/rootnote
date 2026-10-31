# Plan16 S (section 16.7): reading choices, fixed BEFORE any S-row number was computed

Spec: docs/RESULTANT_CORE.md 16.7 (+ 16.3, 16.6).  Slakh TRAIN only.  Code in ~/r3a-dev/plan16/S/.  Everything not listed here is identical to plan16/A/CHOICES.md
(same 10 songs 0-30 s + T60 36-48 s V5a excerpt, k=2..8 synthesis, kOutSos, LS N_p 320 / N_f 191 / ridge / 10 ms smoothing / 5 ms fades, V6b + strict truths, F and M gain variants, pre-echo on gap attacks).
Exploration done before writing this: only the state codes / dict keys of the cached core trace and LA structures were inspected (no S metric).

## Reuse
* R0, R1, R2, R3, R2s, P1 come from `plan16/A/ladder_raw.json` (A's run).  `s_run.py` also recomputes R2 and R3 with A's own code and compares them with the stored values (consistency check, printed in the log; nothing is substituted).
* Candidate pool and LA segmentation come from the cached LA run `la0/cache/la_<key>_bh_64_191.pkl` (L = 64 = current engine information, TRK_LAG 191, bh stream), unchanged.  Core segmentation comes from the cached core v1.5 voice trace (`Sig.core_d`).
* No re-render; no classifier is needed for S rows (pitch or candidate is given by the oracle).

## S1 (candidate real, boundary = MIDI)
* Segment set = the truth segments of A (`ladder.segments`: maximal runs where the same bass note is the LOWEST sounding bass note), f_true = their f (octave tp applied).
* "Tracker candidate pool inside a MIDI segment" = the LA chunks of the cached L=64 bh run (runs of one P1 tracker id, all P1 tracks with state > 0, not only bass-like ones).
  A chunk is a candidate of a segment [s, e] if it has real hops (`ch.hs`, state > 0) with hop centre tc in [s, e).  Hop frequency = the tracker f at that real hop.
* Candidate quality in a segment = number of its real hops inside the segment with |1200 log2(f / f_true)| <= 50 cent (factor 1 only).  The oracle picks the candidate with the largest count (tie -> smaller median |cent| error).
  The segment is **missing** if no chunk has such a hop.  (Octave / 0.5x, 2x, 3x candidates are NOT accepted: "50 cent of the answer"; a lenient count is printed as information.)
* Layer of the chosen candidate: its in-tolerance real hops form runs of consecutive hops; each run is one LS chunk with f(t) = tracker f interpolated between hops (held outside), presence = [max(s, tc_first), min(e, tc_last + hop)] (input time; hop = 16 samples), amplitude from the mix bh stream, N_p 320 / N_f 191 window clipped to that interval, 10 ms smoothing, 5 ms fades (A's `oracle_voices` machinery generalised).  Where the candidate is absent or off by > 50 cent inside the segment there is no layer (partial miss).
* **Missing share, headline for the 10 % override = segment-level**: (# truth segments with no candidate) / (# truth segments), 10 songs.  Also reported: time-weighted (segment time without S1 layer / segment time, t > 0.5 s).  The override is evaluated for both; any disagreement is stated (no tie-break invented).
* Right/wrong of S1 hops by the common machinery (voice f vs sounding MIDI, both truths).

## S2 (segmentation real, pitch = truth)
* Real intervals: S2-LA = all intervals `res['ivs']` of the cached LA-bh-64 run (j_on/j_off stream samples -> time via stream_time); the 16.1 leak applies (about 50 ms more future used), marked in tables.
  S2-core = per core voice id, maximal runs of consecutive hops with state in {2 ON, 3 REL} (CAND = 1 excluded; a 3 -> 2 transition starts a new interval = a new ON; a hop gap splits).  Interval time = [tc_first, tc_last + hop] + calibration lag (-12 ms from `lags.json`, the same shift A applies to core voices) = input time.
* Pitch of a real interval = f of the truth segment (lowest bass note) occupying most of the interval's TIME; "no bass note sounding" is a competing class.  If silence wins, the interval gets no layer (the oracle knows there is no bass note).
* Association filter: the interval's own tracker/voice median frequency must be within 50 cent of 0.5/1/2/3 x f_winner (V6b rule).  Reason: otherwise every guitar/kick chunk overlapping a bass note would be handed the bass pitch (spurious layers unrelated to the segmentation of the bass note).  Dropped intervals are counted.
* No de-duplication: several compatible intervals (chunks at f and 2f, several voices) each give a layer at f_true, consistent with A's R1 oracle (keeps every right interval; R1 right energy +0.68 dB shows duplicates exist).  Gain variant M compensates the level.  **Sensitivity S2b** (information only, not in the decision): per truth segment only the compatible interval of largest overlap.
* Layer: LS on mix bh with f_winner constant, window clipped to the real interval, same N_p/N_f/smoothing/fades as R2.  lag 0 in `measure` (core times already shifted).
* A truth segment is "S2-missing" if no kept interval has it as winner (information only).

## Metrics
* All 16.3 columns for S1, S2-LA, S2-core: right layer dB vs R3, wrong/R3-right fixed and matched (gain dB), V5a on T60 with the 16.6 criterion V5a(row) - V5a(R3) <= 2 %p (R3 = 8.2 % from A; absolute 5 % shown for reference only), pre-echo median (gap attacks), V6b share.  Pass flags: cond1 (<= 0.5 x P1, F and M), cond2 (right >= R3 - 1 dB, F), cond3 new V5a criterion, cond4 pre-echo <= 1 dB.
* Boundary error for every kept S2 interval with winner segment w: d_on = t_on(real) - MIDI start(w), d_off = t_off(real) - MIDI end(w); same vs stem-activity boundaries of A (`ladder.stem_activity` on the clean stem bh).  Median, p10, p90.  Populations: (i) all kept intervals; (ii) single-note intervals (winner occupies >= 80 % of the interval).  Additionally per ATTACK truth segment the nearest kept real onset within +-300 ms (signed vs MIDI start; none within = missing onset, counted).  S1 uses the MIDI boundary (error 0 by construction); its stem-activity error equals R2's (from A).
* Decision rule (16.7), mechanical, fixed gain F, 10 songs pooled: share_cand = log(S1/R2)/log(R1/R2), share_seg = log(S2-core/R2)/log(R1/R2) on the "wrong/R3 right" numbers (v6b truth = primary, strict as sensitivity, M also shown).  Larger = bottleneck; both >= 0.5 -> both, larger first; S1 missing > 10 % -> candidate generation is the bottleneck irrespective of shares.  S2-LA reported, S2-core decides.
