# P1++ impact investigation, 2026-10-26

Baseline P1+ is flags 6, commit 8bec71f. User-reported target: noise rises around
a strong bang then settles. Digital reproduction is not yet identified with the
phone symptom. Seed 2026102607 defines two finite impacts, five input levels and
optional 55 Hz background. Original test used out -18 dB to isolate generation;
this avoids confusing generation with output limiter behavior.

Inspect level-normalized pre/early/late generated energy, track births and
stationary-model residual versus accepted residual. These are diagnostics, not
perceptual noise labels. Subtracting a separately rendered bed measures interaction
with the bed and does not label the result unwanted. Do not optimize only total
generated level. Keep attack energy and legitimate sustained/AM controls.

Initial frozen-P1+ results: at kick+bed input peaks -24/-12/-6 dBFS the declared
recovery diagnostic grows from 12.5 to 47.5 to 82.5 ms; some new tracks have poor
raw stationary fit but pass the onset-history rule. These facts motivate a
counterfactual test, not a conclusion that the 128 ms grace logic is defective.

Before inspecting candidate results, define two host-only modes:

1. Current-frame fit guard: for peaks without a valid modulation fit, effective
   residual is at least the current stationary residual, including onset/falling.
2. Unconfirmed-track guard: apply that requirement until a new track first has a
   nonzero accepted fade. Already confirmed tracks retain the P1+ history rule.

Use the existing -15 dB fit threshold; fit no new constants to this sweep.
Mode 0 must preserve P1+ output bit for bit and other profiles must be unaffected.
No additional latency. Any improvement in tails must be compared with loss of
the intended attack. Test clean short notes, AM and weak source-phase controls.
If mode 1 suppresses real onsets, keep that adverse result. Prefer causal
attribution to stacking further gates. Fresh fixtures are needed after a rule is
chosen, and original fixtures then become development data.

Metric clarification before inspecting fresh-case results: a bed subtraction
retains a constant phase shift of a legitimate sustained tone. It must not be
called residual noise. Also project out constant complex coefficients of the
known input bed's harmonics 1..8 in each pre/early/late window. Report this
stationary-model residual alongside the raw bed-subtracted difference. Keep
the old energy/recovery diagnostics and do not count the metric recheck as new
independent samples. These window metrics remain limited synthetic objectives.

## Outcome

Fresh seed 2026102608: eight independently generated impacts (six kick, two
broadband), four input levels each. Mode 2 reduced late stationary-model residual
by 3.75..16.41 dB on all six strongest kick cases; attack energy changed only
-0.15..+0.32 dB. One broadband case worsened 46.32 dB from a very low residual
floor (-150.7 to -104.3 dBFS at output -18 dB). Pre-impact residual mostly did not
improve, and short-note envelope regressions remain. Keep the option experimental
and retain P1+ as the fixed baseline. No further DSP constants were tuned.

The current-fit guard (mode 1) and the earlier raw difference metric are retained
as adverse/diagnostic evidence. Eight input-selected real-music events show layer
changes, not labeled noise improvements. The engine limiter stayed inactive in
the declared twelve synthetic output/strength settings. Phone protection remains
unmeasured. See research/p1pp/2026-10-26-impact/ for data and limitations.
