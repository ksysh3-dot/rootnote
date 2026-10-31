# Brief D — voice splitter / end detector prototype (Resultant core, section 16.8 + 16.8.1)

You are a Sonnet worker. Opus designs and judges; you implement and measure. OFFLINE Python only: do not edit C++/engine code, do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **sections 16.8 and 16.8.1** (16.8.1 overrides 16.8 where they conflict). Read both fully, plus 16.3, 16.5–16.7 (with the follow-up) and 16.1 for context.

Reuse: ~/r3a-dev/plan16/A/ (synth16.py, ladder.py, stems.py, cache/), ~/r3a-dev/plan16/S/ (s_run.py incl. s2_select, build_voices; followup/fu.py), ~/r3a-dev/la0/ (synthetic-signal pipeline for guards, leak harness), cached core v1.5 traces. Do not re-render what is cached. New code and outputs go to ~/r3a-dev/plan16/D/.

Order (stop and report at any step whose rule says stop):
1. CHOICES.md: record every reading choice BEFORE computing results, including the confirmation-track list (16.8.1 m1: exclusion union with paths and its hash) chosen from MIDI metadata only.
2. Reference rows under the stem-aware wrong definition (16.8.1 B1): R2, R2s′, S2-core, core v1.5; plus the core v1.5 wrong-energy breakdown (B2). Report these before any detector row.
3. Implement the detector (E-p, E-e, E-r with 16.8.1 M3–M7, m5, m6) with index logging for the leak budget (M11).
4. Development tracks: tuning grid (M9), D-oracle and D-full with all pass conditions, guards (incl. new gap, vibrato/glide, E-r rate guards) via the synthetic pipeline, leak budget. Apply the decision rule mechanically.
5. Only if step 4 selects a setting: run the frozen setting once on the confirmation tracks and apply the rule.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Run long jobs in the background with logs. Report (concise, Korean): tables, decision outcome per step, MEASURED vs INTERPRETATION separated, file paths.
