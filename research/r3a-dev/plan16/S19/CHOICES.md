# S19-D CHOICES (fixed before results)
Rows: (1) b0p0 = v1.6-a base (capRho 1.5, windowCreep 16, creepMode 2, beta .2/.9, psiSlew .12); (2) b3p2 = A5'-best (beta .05/.1, psiSlew .03); (3) f4 = phase pull off (beta 0/0, psiSlew .01). Library build_core16b (5c1c62c), row definitions = A5P/a5prows.py, voicing 0, ampSource 0.
Data: 7 user windows (P.WINDOWS: Apparition 52, 88.5, 123.5, 201, 203; Reminiscence 96, 113; 2 s each) and all 14 vanila songs, whole song, read in place; only numbers cached (S19/cache: trace fields + 5 ms box energy).
Layer: diagnostic capture, mono mean, latency removed, zero-phase 4th-order Butterworth 20-150 Hz (A5P SOS_LO). Box = 240 samples (5 ms) of summed squares; boxes = input time (A5P convention).
Time mapping: hop h output block centre = (i_h - 398 + 8)/3000 + CORE_T0 (CA.hop_time convention, 2nd output). Event of hop h (compared to h-1) is placed at that block centre. Box <-> nearest hop by centre time.
Voices of a box: per slot weight = k=2 energy inside the band, a_2^2 (mean of hops h-1,h) if f_osc <= 75 Hz (2 f_osc <= 150) else 0. Selected voices = smallest descending set whose weight covers >= 50 % of box weight. Boxes with no weight = "no in-band voice" (k=3-only / filter leakage / silence).
Events (slot, hop vs previous hop, same voice id unless stated):
 birth = first hop ON(2) of a voice (CAND->ON or new id straight to ON; not REL->ON); REL>ON; ON>REL; release = voice end (state>=2 -> 0 or id change);
 window = Np change >25 % (both ON/REL; field Np is the one window length reported); fosc_jump = |df_osc|>2 Hz/hop (both ON/REL); amp_jump = |dB of A*c*sigma|>6 (both ON/REL, both >1e-9);
 note_chg = |f_track(h)/f_track(h-2)| > 50 cent (same id at h-2, both ON/REL).
Attribution: a box is matched by an event of a selected voice whose hop-centre lies within +-10 ms of the box centre. Exclusive = first match in the list order above; also "any-match" (non-exclusive) reported. None = voices present, no event.
Rates: events per second of in-band voices only (f_osc(h) or f_osc(h-1) <= 75 Hz), counted over the window/song span. Energy per event = exclusive energy share (%) / event rate (per s) [% of the span's 20-150 energy per (event/s)]; large = rare-but-heavy.
Songs: shares energy-weighted per song, then median over 14 songs. Also absolute 20-150 energy relative to row 1 total (pooled) so row 2 vs 1 absolute difference by event type is visible.
Lag check: corr of sqrt box energy vs sqrt weight over lags -8..8 boxes, reported per song (convention is not adjusted).