# Brief K — hit-context check prototype (Resultant core, sections 16.10 + 16.10.1)

You are a Sonnet worker. Opus designs and judges; you implement and measure. OFFLINE Python only: do not edit C++/engine code or existing files in other plan16 folders, do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **sections 16.10 and 16.10.1** (16.10.1 overrides 16.10). The reviewer's full text with exact replacement wording is ~/r3a-dev/plan16/K/review_1610.md — where 16.10.1 is terse, follow that file's replacement text. Context: 16.8.1, 16.9 (incl. the silent-voice diagnosis).

Reuse (read/import, do not modify): ~/r3a-dev/plan16/D/ (dcommon.py, ref_rows.py, guards.py, guards_raw.json, conf_list.json), ~/r3a-dev/plan16/V/ (v_run.py cause tags), ~/r3a-dev/diag16/ (q4.py src_peaks, proxy16.py), ~/r3a-dev/la0/ (data.py, caches). New code and outputs go to ~/r3a-dev/plan16/K/.

Order (stop and report at any step whose rule says stop):
1. K/CHOICES.md BEFORE computing results: core baseline guard table first (16.10.1 MINOR), grid axes and values, every reading choice.
2. Stage 0 (0a separation, 0b upper bound, 0c attack upper bound) on the development tracks. Report it. If any stop condition fires, STOP here and report — do not run the grid. If 0c is worse than −2 dB, also STOP and report (Opus will reset the attack threshold).
3. Only if stage 0 passes: hit detector + provisional cap + confirmation, new bkp-click synthetic signals, all guards, grid, selection rule, mechanical decision on development tracks.
4. Only if step 3 selects a setting: confirmation tracks via a new adapter, frozen setting, one run, mechanical decision.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Index logging for causality. Long jobs in background with logs. Report concise Korean: tables, decision per step, MEASURED vs INTERPRETATION separated, file paths.
