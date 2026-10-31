# Brief F — v1.5.1: D2 stage-1 coefficient cap only (Resultant core, section 16.17)

You are a Sonnet worker. Opus designs and judges; you implement and measure. Do not commit. Do not touch app code. Do not edit the docs.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.17**. The fix itself is 13.2 D2 **as revised by 13.5 MAJOR F4**: the cap goes on the stage-1 coefficients, using the diagonal block of G as A_single (cost 0), applied before the residual is built, and A1 is clipped too. Do NOT implement D1, D3, D4 or any other v1.6 item. Read 13.1 Q3 (the cause), 12 (the v1.5 acceptance table and suite), and 13.5 A1 (R1 burst definition) for context.

Code: the research worktree ~/r3-work (branch research/resultant-core-20261030), core in `pvb_resultant.h` / `.inc`, host API `pvb_set_resultant` (see 4.2, and the param list in 5.8). Add ONE new resultant parameter at the end of the list (0 = off = default, otherwise ρ). With it off, output must be bit-identical to v1.5 (V0) — prove it. Build into a NEW directory `tools/pvb-harness/build_core151/` (do not overwrite build_core). Record the source diff (`git diff` saved to ~/r3a-dev/plan16/F/d2.diff) and the library sha256. Leave the source change uncommitted in the worktree for Opus to review.

Measure, for v1.5 (param off), ρ = 1.5, 2, 3, and P1 (vb_algo 6) where the spec compares to P1:
- Primary: LOGOFF 4.12 s R1 burst (and 4.73 s). LOGOFF copy: ~/r3a-dev/songs (find the file; it is the user's song — never commit it).
- Guards (16.17): V3a peak, rise90, V3b, V3i, V4b, V3e 10 Hz beat, right layer F on the 10 dev songs (plan16/D tools, render-based or trace-based as in 16.9 — say which).
- Report-only: the rest of the existing suite (`tools/pvb-harness/research_core_metrics.py`, as used for ~/r3a-dev/core_results/verify_A), V6b, cap activity rate.
Then apply the 16.17 selection and decision rules mechanically.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Long jobs in background with logs, work files in ~/r3a-dev/plan16/F/. Report concise Korean: tables, decision, MEASURED vs INTERPRETATION, file paths, diff summary.
