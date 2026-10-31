# Brief S19-NF — stage 0b: more LS future (nFuture) against the sustained splatter (RESULTANT_CORE.md 19.2.1, 19.2.2)

You are a Sonnet worker. NO engine code changes (existing parameters only), no builds that modify `~/r3-work` sources, no commits, no downloads, never copy or commit the user's audio. Work in `~/r3a-dev/plan16/S19/NF/`. Another worker runs offline analysis in `~/r3a-dev/plan16/S19/O/` — do not touch it.

Spec (binding): `~/r3-work/docs/RESULTANT_CORE.md` sections **19.2.1** (0단계 b, the new guard rule) and **19.2.2** (the stage-1 decision rule, v1.6-b). Context 18.12-18.14.

Library `~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so` (5c1c62c, 19 params; PARAMS/DEFAULTS in `research_core_api.py`; nFuture is param 12, samples at the 3 kHz analysis rate, default 24, allowed up to 96).

Rows (all with capRho 1.5, windowCreep 16, creepMode 2):
- v1.6-a (β .2/.9, psiSlew .12) × nFuture ∈ {48, 72, 96}
- v1.6-b (β .05/.1, psiSlew .03) × nFuture ∈ {48, 96}
- Reference rows already measured in `~/r3a-dev/plan16/A5P/`: b0p0 (= v1.6-a, nFuture 24) and b3p2 (= v1.6-b, nFuture 24), and P1. Reuse their numbers; re-run one of them only if needed to confirm your pipeline reproduces them.

Measure by reusing ALL of the A5' measurement code in `~/r3a-dev/plan16/A5P/` (p_primary.py layer ratio on the 7 user windows from `/mnt/c/Users/ksysh/Music/vanila/`, the suite runner, burst, RERISE, V3g/logoff45, fosc_p glide/vibrato, right/F, the 14-song table) so numbers are comparable. Add: the 12-song median (all vanila songs except Apparition and Reminiscence) of the per-song 20-150/150-600 layer ratio — if the existing 14-song code only gives the pulsing statistic, compute the per-song layer ratio the same way p_primary does for whole songs or a fixed excerpt; fix which in CHOICES.md before results.

Decision (apply mechanically, write it in `decide_nf.py` before results):
- Main: pooled 7-window layer ratio vs v1.6-b ≥ +2 dB, ≥ 5 of 7 windows better than v1.6-b, and the 12-song median not worse than v1.6-b.
- Guards: the guard list of `A5P/decide_p.py` (attack V3a/rise90, V3b, V3i, V4b, LOGOFF R1, V3g noREL, body ≥ −2 dB, F) plus V3d pre-echo (margin +0.5 dB). A guard FAILS only if the row is worse than P1 on it AND worse than v1.6-b by more than its margin (19.2.1 item 1). V3c.enter, V3e beats, f_osc error, V6b, tails are REPORT-ONLY.
- If several qualify, the best layer ratio; ties within 0.5 dB → smaller nFuture.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test. Run suites in batches of ≤ 4 rows (memory). Long jobs in the background with logs. Report in concise Korean: tables (main, guards with P1 / v1.6-a / v1.6-b columns, report-only), the decision, MEASURED vs INTERPRETATION, file paths.
