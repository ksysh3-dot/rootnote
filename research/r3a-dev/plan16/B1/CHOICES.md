# Plan16 B1 (RESULTANT_CORE.md 18.6): choices, fixed BEFORE any pulsing number was computed

Only renders were started before this file (no envelope modulation, no per-window quantity was looked at).

## Material and engines
* 14 FLAC files of `/mnt/c/Users/ksysh/Music/vanila/` read in place (soundfile, 44.1 kHz stereo -> polyphase 160/147 to 48 kHz, clip +-1, no mono down-mix before the engine; stereo into the engine as in plan16/P). Whole tracks. No audio is copied or kept: only 5 ms envelopes are cached (`cache/*.npz`); the Apparition layers/traces are kept in `cache/` only for the window analysis and are not committed.
* Engines (libs read-only from `~/r3-work/tools/pvb-harness`): P1 = `build_core` algo 6; v1.5 = `build_core` algo 15 with the 16 defaults of that build (the lib predates capRho/windowCreep and refuses 18 values); v1.6-a base = `build_core16a` algo 15 with capRho = 1.5, windowCreep 0 (api copy of 084ea45: `api084.py`, since the checked-out `research_core_api.py` is being edited).
* Render conventions as plan16/P: default `T.Engine` (vb_on 1, ramp 0), block 256, engine latency removed from the head. Layer = diagnostic capture (`pvb_set_diagnostic_capture`), after the output filter, before mixing; same point for both algorithms (verified in P/CHOICES.md section 1). Layer L/R are identical; mono layer used.

## Envelope and modulation measure
* Layer band 150-600 Hz (4th-order Butterworth band-pass, zero-phase `sosfiltfilt`); input low band 40-600 Hz (same filter family) of the L+R mean of the resampled input.
* Envelope: non-overlapping 5 ms boxes (240 samples), RMS, in dB re full scale, floored at -90 dB (so that a silent layer is a flat floor, not -inf). Envelope rate 200 Hz.
* Window 2.0 s (400 envelope samples), hop 0.5 s. In each window: remove the mean of the dB envelope, Hann window, FFT (zero padded to 2048), modulation energy M^2 = integral of power over 2-12 Hz, normalised so that a sinusoidal dB-modulation of amplitude a gives M^2 = a^2/2 (i.e. variance units, dB^2). Reported as M = sqrt(M^2) in dB-rms.
* Input subtraction: pulse excess of engine e in a window = M_layer(e) - M_input (both in dB-rms, same window, same band edges of the modulation). Ranking of windows uses the v1.5-vs-P1 difference D = excess(v1.5) - excess(P1) (= M_v15 - M_P1, the input term cancels; it is kept for the per-song table).
* A window is eligible only if the mean v1.5 layer envelope power in 150-600 Hz is above -70 dBFS (otherwise the dB envelope is mostly floor artefact) and t is inside the track after the first 2 s.
* Ranking: windows sorted by D, descending; the top 3 are taken greedily with a minimum distance of 8 s between window starts (stricter than "non-overlapping", so that the three are separate passages for the ear). Also reported: v1.6-a base in the same windows.
* Layer pulsing rate in Hz in a window = argmax of the 2-12 Hz modulation power spectrum of the layer dB envelope (bin spacing after padding 0.1 Hz).

## 14-song table
* For each song and engine: median and 95th percentile of the excess (M_layer - M_input) over eligible windows (eligible = v1.5 criterion above applied to all three engines identically), plus the song's worst v1.5 window by D (time mm:ss). Reports only; no thresholds.

## Trace analysis of the chosen windows (algo 15, trace on; fields per `api084.TRACE_FIELDS`)
* Hop times by `hop_time` (analysis centre). Per window: voices (slot, voice id, track) in state ON(2)/REL(3) with f_track, f_osc, A (dB), coasting flag; pairs of simultaneously sounding voices with |f_osc - f_osc'| < 14 Hz (beat rate = difference); births = a voice id first appearing with state ON, release cycles = entering state REL; the rates per second; the input low-band spectral peaks over time (STFT 0.5 s Hann, 20-700 Hz, local-max peak list) to compare f_osc against the real notes (for (d) ghost pitches) and to see vibrato.
* Mechanism rules for (a)-(e) are interpretation and are stated in the report with the evidence; a rate match is: layer pulsing rate within 20 % of the candidate rate (pair beat df, birth rate, vibrato rate).
