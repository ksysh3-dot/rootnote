# Followup to Brief S: readings fixed before computing

Same S2-core definition as ../CHOICES.md (core ON/REL intervals = state 2/3 runs, -12 ms shift, majority-time winner, pitch filter, no dedup). Songs: the 10 songs, 0-30 s (no T60). Time base: 2 ms grid, t > 0.5 s, input/excerpt time.

## Part 1
* Unmatched segment = truth segment that is the winner of no kept S2-core interval (185 expected).
* Per time sample of an unmatched segment, precedence: (i) covered by a KEPT interval (necessarily linked to another note); else (ii-a) covered by an interval that failed the pitch filter; else (ii-b) covered by an interval whose majority was silence; else (iii) no ON/REL interval. (ii) = ii-a + ii-b (silence-won intervals are "matched no note" too, shown separately).
* Segment counts: segment is assigned to a class if that class holds > 50 % of its time (segments can be mixed; counts do not sum to 185).
## Part 2
* S2-core layer re-synthesised from the same kept intervals/LS (identical to s_run; total re-checked against s_raw). Wrong = hop-level V6b wrongness of the voice (same split as measure). Each wrong sample is assigned by time, with precedence: (a) another bass note (lowest-note segment != the voice's winner) sounds at that time (includes the voice running into the neighbouring note before or after the winner, i.e. voice spans a note change); else if no bass note sounds: (b) after the winner's end, (c) before the winner's start; else (d).
* Each category's energy = energy of a layer made only from wrong samples of that category (same phases). Cross terms mean the categories do not sum exactly to the total; the shares are shares of the total, and the sum is reported.
* Interpretation (a) differs from "minority within a majority-note voice" only in that overlapping the neighbour note after/before the winner is also (a).
