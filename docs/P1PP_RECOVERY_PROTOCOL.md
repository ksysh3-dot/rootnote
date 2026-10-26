# P1++ confirmation-recovery investigation — 2026-10-26

Prior fixed baseline: P1+ flags 6. Prior impact mode 2 guards an unconfirmed
track's first acceptance. User requested the characteristic difference between
the broadband-2 regression and the improved kick cases, and a justified exception
or improvement. Do not fit a broadband classifier to one inspected signal.

## Diagnosis before a new candidate

Saved paired traces of all eight strongest fresh cases have identical track
frequencies and lifecycle states across P1+ and mode 2. Input H/P separation and
the percussive path also match. Broadband 2's late gain is exactly 1 in both
variants; its late difference already exists in raw tonal grains.

The 74.38 Hz background is reacquired under track ID 12. P1+ starts the admitted
track at fade 1, whereas mode 2 initially rejects it and later admits it as an
existing track. Fade then rises from zero using the old smoothing rule. At source
centers 1.378/1.421/1.458 s mode-2 fade is .901/.976/.993 while P1+ is 1.
This artificial recovery of the intended tone enters the late stationary-model
residual. It is not evidence that every residual component is a new noise tone.

## Candidate rule fixed before candidate output

Host mode 3 retains mode 2's current-fit guard. When an existing unconfirmed track
first passes its allowed fit, set its fade to 1, exactly as a newly born valid
track already does. Keep grain/OLA smoothing; do not reset phase or frequency,
change the model threshold, bypass the guard by signal class or add latency.
Valid modulation fits keep their existing handling. Modes 0/1/2 must remain bit
exact with the previous implementation. No change to Android defaults.

## Evaluation

Revisit the original eight/32 level settings as inspected development data,
including both lower-level broadband-2 improvements and the strongest regression.
Keep late stationary residual, pre/early windows and attack energy. Inspect the
six prior short-note and normal-AM controls and retain any new failures.
Then fix the rule and evaluate a new seeded set (2026102609), including pitched
and broadband finite impacts, background reacquisition and clean note onsets.
Count levels and sample rates as repeats, not independent signals. Do not change
DSP constants after seeing those outputs. Real-music differences remain unlabeled
quality diagnostics. Regression thresholds do not reinstate old level/latency vetoes.

## One refined recovery rule, before the new seed

Mode 3 fixes broadband-2 and retains positive late reductions on all six inspected
strong kicks, but some attack energy increases. Keep that result. Compare mode 4:
remember that a track was initially rejected; restore its normal birth fade only
when both its current stationary residual and effective residual pass the existing
-15 dB test. A valid modulation fit may still admit it earlier with mode-2 fade;
this additional bit only decides recovery, not acceptance. Keep the pending bit
through matches until clean recovery. No signal-class threshold is introduced.
This definition is fixed before viewing seed 2026102609; the old eight cases are
development data. Modes 0/1/2/3 must preserve their previous outputs.

## Mode choice and final confirmation, before reading that cohort

On seed 2026102609, modes 3 and 4 both remove the late regressions in the tested
window. Mode 4 retains more mode-2 attack behavior, so select it as the recovery
candidate. This new cohort contributed to selection and is not an untouched
final validation set for that choice. Keep both modes and their adverse changes.
Freeze all DSP rules, then evaluate seed 2026102610 (8 new shapes, three levels)
against P1+ and mode 2. No tuning or further candidate choice will follow its
results in this round. Also disclose pre/early windows and clean-note controls.

## Recorded outcome

The frozen mode-4 confirmation (seed 2026102610) has 8 shapes / 24 level settings.
Late residual: 13 improve by >0.1 dB, none worsen by >0.1 dB. Early 0..80 ms:
2 improve, 10 worsen by >0.1 dB; worst increase 3.465 dB. The selection cohort's
worst early increase is 9.603 dB. Four of six short-note shape controls worsen
versus P1+. These costs prevent an overall quality/adoption claim. Mode 3 remains
available; its better short-note results are preserved. See the round-2 results
and reproduction commands under research/p1pp/2026-10-26-recovery/.
