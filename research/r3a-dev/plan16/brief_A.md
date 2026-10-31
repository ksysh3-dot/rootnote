# Brief A — leak test, R3-a audit, oracle ladder (Resultant core, section 16)

You are a Sonnet worker. Opus (the coordinator) designs and judges; you implement and measure. OFFLINE Python only: do not edit C++/engine code, do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.1–16.3** (read it fully). Context: sections 14, 14.1 (the LA prototype and its known k=2,3 synthesis limit), 15.

Reuse the LA prototype in ~/r3a-dev/la0/ (run_la0.sh, CHOICES.md, cache/, metrics.py, evaluate.py) and ~/r3a-dev/diag16/ helpers (streams16.py, common16.py, q1.py labels). Do not re-render what is cached.

Tasks, in order:
1. **16 common**: replace the LA synthesis by the engine's harmonic set: k = 2..8 while k·f ≤ 700 Hz, weights from the engine `lookup()` table (read pvb_vb*.cpp/pvb_vb.h to replicate it exactly, or measure it through the lib) with the voicing-0 rolloff (`amplitudes()` in app/src/main/cpp/libpvb/pvb_resultant.inc:780). Show a check that your Python weights match the engine for 35/45/60/100/150 Hz.
2. **16.1 leak test** on LA (L = 64 and 217): identical prefix to T, four different suffixes; outputs for t ≤ T − L must match within 1e-9. Report pass/fail per suffix.
3. **16.2 R3-a audit**: find in the code whether R3-a is active for algo 15 and the P1 profile; if active, record pre/post frequencies and compute the share of "below the lowest MIDI note" wrong weight that R3-a moved.
4. **16.3 oracle ladder** R0–R3 exactly as specified, with both the matched-right-energy and fixed-gain variants, the four pass conditions per row, and the decision rule applied mechanically. Report R2's MIDI-boundary vs stem-activity differences.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Put new code and outputs in ~/r3a-dev/plan16/A/. Keep runtime modest; run long jobs in the background with logs. Record any reading choice for ambiguous spec text in plan16/A/CHOICES.md BEFORE computing the ladder results.

Report (concise, Korean or English): per-task tables, decision-rule outcome, MEASURED vs INTERPRETATION clearly separated, file paths.
