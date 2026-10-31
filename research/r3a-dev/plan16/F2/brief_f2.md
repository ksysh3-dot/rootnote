# Brief F2 — post-hit rise limit for existing ON voices (Resultant core, section 16.18)

You are a Sonnet worker. Opus designs and judges; you implement and measure. Do not commit. Do not touch app code outside `pvb_resultant.*`, and do not edit the docs.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.18** (and 16.17 for the decision rule, guards and measurement setup). The previous worker's folder ~/r3a-dev/plan16/F/ has everything to reuse: patch/build scripts, V0 check, `f_burst.py` (LOGOFF R1 via gate16/e7_v7d.py), the suite runner, `f_right.py`, `f_diag412.py` (the 4.12 s trace view that motivated this). The rejected D2 diff is `F/d2.diff` — do NOT apply it; the worktree must start clean at HEAD (check `git status`).

Order:
1. ~/r3a-dev/plan16/F2/CHOICES.md before results (hit-cue details: which HPSS buffer, block, median length, refractory; voice-age definition; how amp_pre is taken).
2. Stage 0 oracle on the v1.5 trace (offline, synthesis as in plan16/D render path): hold existing ON voices (age >= 50 ms) at pre-hit amp over [t_d, t_d+80 ms] at the LOGOFF 4.12 s hit; R1 burst; birth vs rise split of the burst energy. If the gain is < 2 dB, STOP and report (no C++).
3. Otherwise implement in C++ (`pvb_resultant.h/.inc`): one new resultant param at the end of the list (0 = off = default; encode cap and W as you document, e.g. two params if cleaner — say which). Off must be bit-identical to v1.5 (V0, as in F/v0_check). Build into `tools/pvb-harness/build_core152/`. Save `git diff` to F2/rise.diff and record the library sha256. Leave the change uncommitted.
4. Measure the grid (cap {+3,+6} dB × W {40,80} ms) plus v1.5 and P1: primary 4.12 s (and 4.73 s) R1; the 16.17 guards plus the new co-struck re-attack guard (synthetic: same-pitch repeated bass notes with a click-kick at each onset, as 16.10.1 B1 bkp-click (i); re-attack rise90 <= v1.5 + 5 ms); report-only rest of suite, hit-detection count per song, cap activity.
5. Apply the selection and decision rules mechanically.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Never commit audio. Long jobs in background with logs. Report concise Korean: tables, decision, MEASURED vs INTERPRETATION, file paths, diff summary.
