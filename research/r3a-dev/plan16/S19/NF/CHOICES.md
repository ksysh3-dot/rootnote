# S19-NF CHOICES (fixed before any result; 2026-10-31)

Spec: RESULTANT_CORE.md 19.2.1 (stage 0b), 19.2.2 (decision v1.6-b). Library build_core16b/libpvbcapi.so (5c1c62c, 19 params). No engine edits.

## Rows
All Resultant rows: capRho 1.5, windowCreep 16, creepMode 2, voicing 0, ampSource 0.
- nfa48 / nfa72 / nfa96 = v1.6-a (betaMin .2, betaMax .9, psiSlew .12) with nFuture 48 / 72 / 96
- nfb48 / nfb96 = v1.6-b (betaMin .05, betaMax .1, psiSlew .03) with nFuture 48 / 96
- References (nFuture 24), reused from `plan16/A5P/`: P1 (algo 6), b0p0 = v1.6-a, b3p2 = v1.6-b.
- Pipeline check: b3p2 is re-run here (suite batch 2, p_primary) and compared with the A5P numbers; the decision uses the A5P reference numbers.
- nFuture is in samples at the 3 kHz analysis rate (24 = 8 ms, 48 = 16 ms, 72 = 24 ms, 96 = 32 ms).

## Measurements (A5P code copied to this directory; only paths/row lists changed)
- Suite (fmetrics16b via run_suite_p.sh, batches of at most 4 rows), burst_p (LOGOFF 4.12/4.73 R1), rerise_p, logoff45_p, fosc_p (glide/vib), right_p (F, 10 dev songs), p_primary (7 user windows: pooled 20-150/150-600 Hz layer ratio + jumps), a5_song14 (14-song pulse table, report-only).
- 12-song layer ratio (NEW, songs12.py): the two user songs Apparition (idx 9) and Reminiscence (idx 6) are excluded, the other 12 vanila songs are rendered whole (same render_song and Butterworth 20-150 / 150-600 bands as p_primary); per-song ratio dB = 10log10(P_lo/P_mid) over the whole song after skipping the first 2 s; the statistic is the median over the 12 songs. Lower = better. "Not worse than v1.6-b" means median(row) <= median(v1.6-b) (rendered here, same code, same session).
- P1 is rendered by the same code as a comparison column.

## Decision (mechanical, in decide_nf.py)
Main (all three): pooled 7-window ratio gain over v1.6-b >= +2.0 dB; at least 5 of 7 windows better than v1.6-b (lower per-window ratio); 12-song median not worse than v1.6-b.
Guards (19.2.1 item 1): a guard FAILS only if the row is worse than P1 on it AND worse than v1.6-b by more than the margin (reference = v1.6-b, nFuture 24, from A5P). Margins: V3a peak +2 ms; V3h.bare.rise90 +2 ms; V3h.25.rise90 +2 ms; V3b +1 dB; V3i.trans +0.5 /s; V4b bass+pink and bass+kick+pink +1 %p; LOGOFF 4.73 s R1 +1 dB; V3g.35.noREL and V3g.45.noREL +5 hops; body (pooled 150-600 Hz level of the 7 windows) -2 dB (worse = lower); right-layer F -0.5 dB (worse = lower; no P1 value exists, so the "worse than P1" clause is treated as met = conservative); V3d pre-echo +0.5 dB (higher = worse). "Worse than P1" uses the P1 column of the same check (strict inequality; for body the pooled mid level of P1 from A5P/primary_p1.json; for LOGOFF the P1 R1 burst).
Report-only: V3c.enter, V3e df4/df10 beats, f_osc glide/vib error, V6b, tails (V3h.*.tail, tail_bp/raw), RERISE, LOGOFF 45 Hz ON fraction/gaps, 14-song pulse table, per-hop jumps, V3d value itself.
Selection: among rows that pass Main and all guards, the lowest pooled ratio; rows within 0.5 dB of the best -> smaller nFuture; equal nFuture -> v1.6-b family (the adopted base). If none qualifies: no change (stay at v1.6-b nFuture 24).

## Addition (coordinator Opus, report-only, added before its numbers were seen)
Leakage-free ratio on the 7 windows (leakfree.py): FFT bins 20-140 Hz energy / 150-600 Hz energy over the whole window (brick-wall, mono mean of layer channels, same render/latency as p_primary), pooled and per window, for P1, v1.6-a, v1.6-b and the 5 new rows (all re-rendered). Does NOT enter the decision.
