# Brief G — bass-context gate prototype (Resultant core, sections 16.13 + 16.13.1)

You are a Sonnet worker. Opus designs and judges; you implement and measure. OFFLINE Python only: do not edit C++/engine code, the docs, or existing files in other plan16 folders. Do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **sections 16.13 and 16.13.1** (16.13.1 overrides 16.13). The reviewer's full text with exact replacement wording is ~/r3a-dev/plan16/G/review_1613.md — where 16.13.1 is terse, follow that file's replacement text. Context: 16.8.1, 16.9 (silent-voice definition and cause tags), 16.10.1 (guards M4, evaluation path M6). The 16.10 prototype in ~/r3a-dev/plan16/K/ is the closest template (structure, CHOICES.md, stage-0 reporting).

Reuse (read/import, do not modify): ~/r3a-dev/plan16/D/ (dcommon.py, ref_rows.py, guards.py, guards_raw.json, conf_list.json), ~/r3a-dev/plan16/V/ (v_run.py cause tags), ~/r3a-dev/plan16/K/ (helpers you may import), ~/r3a-dev/la0/ (data.py, caches). New code and outputs go to ~/r3a-dev/plan16/G/.

Order (stop and report at any step whose rule says stop):
1. G/CHOICES.md BEFORE computing results: core baseline table (per song, silent wrong_sa with and without t<4 s), grid axes and values, every reading choice (causal q95, N_s, P at hop h, ramps).
2. Stage 0 (0a time shape per song, 0b oracle per H, 0c real gate at g_cap −24 dB per (H, D_s), 0d first-note cost report-only) on the development tracks. Report it. If any stop condition fires (16.13 0a/0b, 16.13.1 B1, M5), STOP here and report — do not run the grid. If 0b R_max < 50 %, also STOP (Opus resets the threshold).
3. Only if stage 0 passes: full gate, new synthetic guard signals (vib_100, glide incl. 808 drop, sparse bass, quiet passage) plus the existing guard set and 16.10.1 M4 guards, grid, selection rule, mechanical decision on development tracks.
4. Only if step 3 selects a setting: build conf2 by the fixed rule in 16.13.1 M3 (train only; record paths and hashes; if not enough songs qualify, report "확인 불가" and stop), frozen setting, one run, mechanical decision.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob); when scanning train for conf2, list only the train directory. Log read trace hop indices for causality. Long jobs in background with logs. Report concise Korean: tables, decision per step, MEASURED vs INTERPRETATION separated, file paths.
