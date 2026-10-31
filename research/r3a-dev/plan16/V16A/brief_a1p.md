# Brief A1' — cause-conditioned window-growth limit (RESULTANT_CORE.md 18.5)

You are a Sonnet worker. Opus designs and judges; you implement and measure. Do not commit or push. Do not touch app Kotlin code or the docs.

Binding spec: `~/r3-work/docs/RESULTANT_CORE.md` sections **18.4 and 18.5** (context 13.1 Q5 = the tail cause, 13.5 F5). Start from HEAD 232e46a (params 17 capRho and 18 windowCreep already in `pvb_resultant.h/.inc`, committed in 084ea45, default off). You implemented them yourself in `~/r3a-dev/plan16/V16A/` — reuse all its scripts (V0 check, suite, RERISE, burst, ρ, right layer F, logoff45).

Change: the growth limit acts only while the voice's SNR is falling — "falling" = the voice's `snr` is more than 3 dB under its maximum over the last 30 ms (about 6 hops); otherwise the window grows at once as in v1.5. Variant (i): only the stage-2 voice window N_v. Variant (ii): N_v, and N_J when the maximum SNR over the LS set is falling by the same test. Choose the cleanest parameter encoding (e.g. param 19 `creepMode`: 0 = unconditional as in 084ea45, 1 = variant (i), 2 = variant (ii)) — document it; all new params at 0 must keep the 084ea45 behaviour, and capRho = windowCreep = 0 must stay bit-identical to v1.5 (re-run the V0 check). Keep code style and comment density. Build into `tools/pvb-harness/build_core16b/`, save `git diff` to `~/r3a-dev/plan16/V16A/a1p.diff`, record sha256, leave uncommitted.

Rows (all with capRho 1.5 except v1.5): v1.5; v1.6-a base (A2 only); A1 8 unconditional (reference); A1' (i) 8, (i) 16, (ii) 8, (ii) 16. Primary: V3h tail at the 25 dB line, RERISE (output layer, as in V16A). Guards: the 18.3 four-category set plus **V3g 35/45 Hz noREL ≤ v1.5 + 5 hops**. Report-only: V3e.df4, V9e, V5a, the rest of the suite, ρ, LOGOFF 4.12/4.73 R1, logoff45 ON/gaps. Apply the 18.5 decision rule mechanically.

Also, as a quick diagnostic (report-only, no decision): for the A1 8 unconditional row, show for the 35 Hz synthetic note how N_v / N_J and SNR evolve over the first 300 ms after onset versus v1.5, to confirm or refute the 18.4 interpretation (slow window growth at deep-note onsets).

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). No downloads. Never commit audio. Long jobs in the background with logs. Report in concise Korean: tables, decision, MEASURED vs INTERPRETATION, diff summary, file paths.
