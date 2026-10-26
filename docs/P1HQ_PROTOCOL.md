# P1+ HQ continuation — 2026-10-26

The user explicitly superseded the previous fixed carrier-level and latency
constraints. Neither an RMS/carrier increase nor additional latency is a veto.
Report them as costs. Do not hide level changes using per-frame normalization.
Keep the previous report intact as a record of a different design brief.

Develop from the previous phase-preserving P1+ (flags 2), with the original P1
as a control. Existing oscillator, short-detail, AM-family and envelope research
are not new proposals. This iteration investigates centered HPSS within the same
P1 engine, using five future hops for its existing eleven-frame time median.
The new source delay is 80 samples at 3 kHz, or 26.6667 ms. Delay the dry stream
and the phase-reference input consistently. Do not change spectral weights,
output gain, limiter or replace the harmonic generator to obtain this change.

Flags: 0 original P1; 2 phase-preserving P1+; 4 centered HPSS only; 6 both.
Baseline P1 must remain bit exact with flag 0. Only profile 6 applies these flags.
The host API is configured before processing. These are optional research modes.

Quality evidence is separate from execution correctness. First verify the native
HPSS against an independent offline STFT/median/OLA implementation, aligned by
declared delays. Then evaluate mixtures whose harmonic and percussive source
components are known, including short notes and overlapping attacks. Report
source-separation errors, transient localization and synthetic spectral residual;
the reference labels are experimental definitions, not universal music truth.
Preserve phase-only tests and allocate a fresh seeded set for this iteration.

Use the user's TestSound and Rayark collections for applicability and regression.
Measure unknown music's output difference, levels, peak, changes in control paths
and native processing cost. Do not rename these values perceptual quality scores.
Render representative processed excerpts as inspectable output, without requiring
the user to perform repeated AB tests before numerical work can continue.

No success is promised by loosening constraints. Prefer the candidate with
evidence for its intended purpose; report regressions instead of adding an
unrelated hard constraint after seeing results. A failed centered-HPSS experiment
does not invalidate an independently supported phase-preserving mode.

## Development result and one additional hypothesis, before new held-out data

The plain centered window passed the independent oracle and engineering checks.
On the four declared development mixtures, H error changes versus causal HPSS
were +0.38, +0.90, -6.12 and +1.06 dB. The short-note case improved; noise leaking
into the harmonic part increased in the other cases. Do not call all four better.

Compare a prominence-weighted mixture of the causal and centered masks, both
evaluated for the same delayed frame. A locally flat spectrum uses the causal
mask; a peak at least sqrt(10) times its frequency median uses the centered mask.
Interpolate linearly in that ratio between 1 and sqrt(10). The 10 dB prominence
endpoint is already used by P1's spectral source detector, not fitted to these
outputs. Store sixteen frames to retain both target windows. This is an explicit
new hypothesis, not a validated general separator. Flag 8 requires flag 4; flags
14 combine this HPSS rule with phase preservation. Freeze this definition before
evaluating the eight new mixtures and eight new phase conditions.

## Final-layer diagnostic refinement (no DSP retuning)

Retain the fixed third-harmonic envelope test, including the prominence mode's
0.37 dB worsening on a 43.4 Hz short-note condition. That third harmonic is below
the fixed 150 Hz output high-pass and is not the principal emitted cue. To assess
the main cue without selecting from an output, choose the strongest harmonic by
input frequency, unchanged gentle24 weights and unchanged output-filter response.
Evaluate six fresh short-note mixtures with seed 2026102606. A single constant
amplitude scale is allowed, no fitted time shift. Keep both diagnostics and do
not relabel the previously inspected cases held-out. No code parameter changes
are to be made after this fresh test in this iteration.

## Mode selection from measured trade-offs

The six fresh primary-harmonic envelope conditions favored plain centered HPSS
in all six (1.81..11.94 dB less shape error). Prominence weighting improved five
but worsened one by 1.31 dB. Select flags 6 as the optional HQ renderer default;
retain flags 14 as a comparative experiment, not the recommended HQ mode. No DSP
parameters changed after this comparison. These six cases contributed to mode
selection and are not a new untouched final test set for that selected mode.

Original P1 and phase-only P1+ remain available. HQ is a measured trade-off:
short-note temporal fidelity improved in the declared model, while several
source-separation mixtures had higher H error. Do not promise every song improves.
These differences do not recreate the superseded 0.3 dB/zero-extra-latency veto.

Final arithmetic audit: the initial mixture evaluator left different source-clock
end margins for the two delays. Recompute all mixtures using the same source
interval for all variants (the exact common source interval is recorded in each final JSON row). The HQ
mixture regressions are 0.37..1.30 dB after this correction. Source/renderer code
and the selected mode are unchanged. The earlier development figures above
record the initial decision context; final JSON contains the corrected intervals.

## Naming decision on 2026-10-26

The user provisionally adopted flags 6 as **P1+**, the fixed research baseline
for P1++. In the historical sections above, "phase-preserving P1+" means the
phase-only control (flags 2), not the newly adopted P1+ model. Android defaults
and deployment are separate. See P1PLUS_BASELINE.md and P1PP_RESEARCH.md.
