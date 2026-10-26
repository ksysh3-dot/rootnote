# P1+ objective refinement protocol

> Historical initial protocol. Its phase-only candidate and fixed carrier/latency
> screen predate the later HQ study. The adopted P1+ baseline is flags 6; current
> decisions are in P1PLUS_BASELINE.md and P1PP_RESEARCH.md.

2026-10-26. Baseline DSP: RootNote 4331423274665b6c16ca9d438389c289e39b92d4.
Remote main b3c6fe47ee0c1720a43a6de2ae31efa6c80f0b24 has the same P1 implementation;
the only libpvb change in the comparison is two Bankstown documentation lines.

## Scope and decisions fixed before candidate results

Preserve P1's HPSS, 128 ms analysis, 3 kHz core, 16-sample hop, 2..8 harmonics,
OLA, latency, output safety settings and default app profile. Study (1) residual
history/model mismatch and (2) intermittent source-phase references separately.
The first stage is reproducibility and controlled experiments, not an APK release.

Full production Engine/profile 6 must be exercised, including actual analysis.
A controlled renderer test may locate a cause but is not a substitute for that.
Capture-off and flags=0 must preserve baseline output bit for bit. Public trace
schema and Android settings must not change. No output-dependent metric tuning.

Development signals: steady 55/83 Hz; 55 Hz AM at 3/7/11 Hz; weak 165 Hz partial
crossing the reference-amplitude threshold at 2/7 Hz, two phases; 55/83 Hz rank
crossing; close 55/58 Hz pair; note off; noise seed 2026102601; silence.
Held-out seed 2026102602 generates six additional anchor conditions. Do not use
held-out results to select parameters and then call the same set held out again.
If parameters are changed, label these cases as development and allocate a fresh
test set. Checks include both 48 and 44.1 kHz and different callback sizes.

An input-derived spectral-support residual includes legitimate AM sidebands.
It is a diagnostic for these constructed signals, not a universal noise score.
Normal two-tone beating, raw hop-energy change and output/source subtraction are
not noise ground truth. No per-frame output normalization is permitted.

Provisional adoption screen: reproduce a relevant failure; reduce its declared
unwanted component by at least 3 dB; retain wanted carrier levels within 0.3 dB;
no >1 dB worsening of the declared residual on clean control cases above the
numerical floor; no new invalid/nonfinite output, latency, termination, reset,
block-size or current-frame rejection regression. A reduction from a silent or
attenuated generator does not pass. These are engineering margins, not audibility
thresholds. If this screen fails, retain the experiment and rejection evidence,
not the candidate as an app default.

Implementation correctness, limited signal fidelity, real-music applicability,
device behavior and listener preference are separate conclusions. Listening
fatigue or a nonsignificant small-panel comparison yields an unresolved result;
it does not prove equivalence. Stronger claims require a defined effect margin,
adequate experimental sensitivity, and uncertainty estimates.

## Development revision before opening the held-out set

The first phase candidate used 1%/0.5% acquisition/release and six-hop hold.
On the development anchors it improved the 7 Hz cases but worsened both 2 Hz
cases; reject it. An initial implementation omitted transfer of its new state
between observed tracks, which the full-path check exposed as zero effect.
The corrected candidate and its negative results remain in rejected-debounce.patch.

Second phase candidate: when there is no valid reference, retain the synthesis
offset rather than steer it toward the table default. New tracks still start
at the table phase, and valid reference corrections keep the existing 0.12 rad
bound. No acquisition threshold, extra state, lookahead or amplitude is changed.
Use the same development cases and unchanged engineering margins. The held-out
set has not yet been opened as of this revision.

## Real-music applicability study (fixed before running the corpus)

The user selected Desktop/TestSound and the Rayark concert collection. Select
three fixed eight-second excerpts per WAV/FLAC at 15%, 50% and 85% of the
available start interval (duration minus 8.25 seconds). Read up to four seconds
before each excerpt and 0.22 seconds after it; reset between excerpts. Resample
to 48 kHz using scipy.signal.resample_poly, retaining stereo. Process the same
PCM with baseline, history-only and phase-only variants: profile 6, VB +6 dB,
output -18 dB, zero parameter ramp. The conservative output gain makes this a
DSP comparison, not a simulation of high-volume phone limiting.

Save source-file SHA256, decoded-input SHA256, timestamps and settings. Report
full-mix and generated-layer RMS, four-times-oversampled true peak, phase-control
activity and track/latency invariance. Phase activity is a fraction of eligible
harmonic/hop observations; it is not a percentage of audible errors. Difference
signals and RMS-matched difference are diagnostics, never quality labels.
The source files have unknown prior processing. No clean virtual-bass reference,
speaker/microphone path or listening verdict is supplied by these recordings.

## Outcome (2026-10-26)

The phase-preserving candidate reduced the declared synthetic residual in all
four targeted development cases and all six held-out conditions at both rates.
It failed the fixed 0.3 dB wanted-carrier-level margin; no margin was relaxed.
Retain it as an experimental host flag, disabled by default. The history-only
candidate did not demonstrate the required synthetic improvement. The corpus
contains 29 files and 87 excerpts, 696 seconds evaluated; this is not an analysis
of every second of every song. See the saved results for exact values and scope.
