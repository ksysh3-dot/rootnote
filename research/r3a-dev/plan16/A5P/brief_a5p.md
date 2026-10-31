# Brief A5' — slow the phase pull against the "쿠쿠쿵" skirt (RESULTANT_CORE.md 18.12)

You are a Sonnet worker. Opus judges. NO engine code changes (only existing resultant parameters), no builds that modify `~/r3-work` sources, no commits, no downloads, never copy or commit the user's audio. Work in `~/r3a-dev/plan16/A5P/`.

Spec: `~/r3-work/docs/RESULTANT_CORE.md` sections **18.11 and 18.12** (context 18.7 = the v1.6-a base: capRho 1.5, windowCreep 16, creepMode 2).

Library: `~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so` (5c1c62c code, 19 params; PARAMS order in `~/r3-work/tools/pvb-harness/research_core_api.py` at HEAD). All rows use the v1.6-a base settings and vary only betaMin/betaMax and psiSlew: (betaMin, betaMax) ∈ {(.2,.9) base, (.1,.45), (.1,.2), (.05,.1)} × psiSlew ∈ {.12 base, .06, .03}.

Reuse: the A5 worker's measurement code in `~/r3a-dev/plan16/A5/` (primary layer-ratio over the 7 user windows from `/mnt/c/Users/ksysh/Music/vanila/`, the guard suite runners, F via the debug library approach — note F needs the rendered amplitude; for this grid the trace A·c·σ is the rendered value since no slew limit exists, but confirm), `~/r3a-dev/plan16/V16A/` (suite, burst, RERISE, V3g, logoff45).

Measure per 18.12: primary (pooled + per window), guards (18.9 list + V3c.enter ≤ +5 ms, V3e.df4 beat ≤ +1 dB, and an f_osc error check on synthetic glide and vibrato signals ≤ +10 cents median — use existing suite signals if they exist, otherwise generate them and document), report-only items (phase-alignment / same-peak coherence if the suite defines it, tail, RERISE, V6b, 14-song 20-150 Hz table for base and the best row). Apply the 18.12 decision rule mechanically; if nothing qualifies, report the phase-side oracle upper bound as 18.12 says (f_osc and θ pinned to a smoothed input reference) as an offline estimate.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test. Long jobs in background with logs. Report in concise Korean: tables, decision, MEASURED vs INTERPRETATION, file paths.
