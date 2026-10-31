# Brief A2 — V5a drop decomposition (Resultant core, section 16.6)

You are a Sonnet worker. Opus designs and judges; you measure. OFFLINE Python only: do not edit C++/engine code, do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.6** (read it fully). Context: section 5 "V5 실곡" definition (V5a), 16.3, 16.5.

Reuse everything in ~/r3a-dev/plan16/A/ (synth16.py, ladder.py, stems.py, diag_v5.py, extra.py, cache/). Do not re-render what is cached. New code and outputs go to ~/r3a-dev/plan16/A2/.

Tasks:
1. For the T60 V5a excerpt, list every "bass present" 20 ms bin that counts as a V5a drop for rows R3, R2, core v1.5 (k ≤ 8 synthesis, as in 16.5 post-hoc) and P1.
2. Classify each drop bin with the categories and order of 16.6 (first match wins): B (boundary), T (input timbre), W (weight table), O (other). Use the exact tests in 16.6.
3. Run the two counterfactual R3 variants of 16.6 (flat weights; stem-activity boundaries) and report their V5a.
4. Report per row: V5a %, counts per category, and the 16.6 relative criterion (row − R3 ≤ 2 %p) pass/fail. Apply the 16.6 interpretation rule mechanically and state its outcome.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Record any reading choice for ambiguous spec text in A2/CHOICES.md BEFORE computing the classification. Keep it short: this is a small diagnostic (aim well under one hour).

Report (concise, Korean): tables, rule outcome, MEASURED vs INTERPRETATION separated, file paths.
