# Brief A5 — amplitude slew limit against the "쿠쿠쿵" splatter (RESULTANT_CORE.md 18.9)

You are a Sonnet worker. Opus designs and judges; you implement and measure. Do not commit or push. Do not touch app Kotlin code or the docs. No downloads. Never copy or commit the user's audio.

Binding spec: `~/r3-work/docs/RESULTANT_CORE.md` section **18.9** (context 18.7 = the v1.6-a base, 18.8, and the diagnosis files in `~/r3a-dev/plan16/B1/b12/` — especially how the 20-150 vs 150-600 Hz layer levels and the per-hop jump counts were measured; reuse b12/b1 code for the primary metric so numbers are comparable).

Code: `~/r3-work` at 1e5ef4d (params 17-19 committed, default off). Add param 20 `ampSlewDb` (0 = off, else max |change| of the rendered per-voice amplitude amp = A·c·σ per hop, in dB; up and down; ON<->REL ramps also obey it) and param 21 `slewOnsetMode` (0 none; 1 strong births with SNR >= snrFastDb are exempt from the rise limit for their first 3 hops; 2 = 1 plus REL->ON after more than 50 ms in REL is exempt for 3 hops). Define precisely where in the render path the limit acts (on the per-hop amplitude target that the per-sample synthesis interpolates) and how a zero/near-zero previous amplitude is handled (state it in CHOICES.md). All new params 0 → identical to 5c1c62c behaviour; capRho = windowCreep = 0 etc. → bit-identical to v1.5 (re-run the V0 check from `~/r3a-dev/plan16/V16A/`). Build into `tools/pvb-harness/build_core16c/`, save `git diff` to `~/r3a-dev/plan16/A5/a5.diff`, sha256, leave uncommitted. Keep code style and comment density. Update `research_core_api.py` PARAMS/DEFAULTS.

Rows: P1; v1.5; v1.6-a base (17:1.5, 18:16, 19:2); v1.6-a + A5 for ampSlewDb {2, 4, 8} × slewOnsetMode {0, 1, 2} (9 rows).
Primary (user-confirmed times, read in place from `/mnt/c/Users/ksysh/Music/vanila/`): the 20-150 / 150-600 Hz layer ratio pooled over Apparition 0:52.0, 1:28.5, 2:03.5, 3:21-3:25 and Reminiscence 1:36, 1:53 (2 s windows), per window too; and the count of > 6 dB per-hop jumps of the rendered k=2 amplitude.
Guards (vs v1.6-a base): 18.9 list exactly, including the body check (150-600 Hz layer level at those windows ≥ base − 2 dB) and attack (V3a, rise90 bare / 25 dB ≤ +2 ms). Reuse the V16A suite/right-layer/burst/V3g scripts.
Report-only: tail, RERISE, V6b, a 14-song table of the 20-150 Hz layer (median over windows) for P1 / v1.5 / base / chosen A5, rest of suite.
Then apply the 18.9 decision rule mechanically; if no row qualifies, also report the oracle upper bound as 18.9 says.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test. Long jobs in the background with logs; work files in `~/r3a-dev/plan16/A5/`. Report in concise Korean: tables, decision, MEASURED vs INTERPRETATION, diff summary, file paths.
