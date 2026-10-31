# Brief APP16 — experimental app model 16 "Resultant 코어 v1.6 (실험)" = v1.6-b, for the user's ear check (RESULTANT_CORE.md 19.2.2, 19.5)

You are a Sonnet worker. Opus reviews and commits; you implement and verify. Do NOT commit or push. No downloads. Never copy or commit the user's audio.

Tree: the WSL worktree `~/r3-app`, branch `research/resultant-app-20261031`, HEAD daf9bba (the v1.6 core code is merged in; `git status` must be clean before you start). Pattern to copy: commits e178a9b and d481259 (`git show`), which added app model 15 (v1.5). Keep the code style and comment density of the surrounding code.

What v1.6-b is: algorithm 15's Resultant core with these research parameters instead of the `pvb_resultant.h` defaults — capRho 1.5, windowCreep 16, creepMode 2, betaMin 0.05, betaMax 0.1, psiSlew 0.03; everything else at the defaults (names/order: `tools/pvb-harness/research_core_api.py` PARAMS, which match `ResultantCore::setParams`).

Do:
1. C++ (`app/src/main/cpp/libpvb/`): add `VB_RESULTANT_V16 = 16` before `VB_ALGO_COUNT` in pvb_vb.h. Everywhere algorithm 15 gets its Resultant-profile behaviour (pvb_vb.cpp setAlpha2Profile and friends, `resultantOn_`, the stage/gen/p1Plus flag fixing, latency, pvb_engine.h `vbMods_` mapping to the same module instance as 15), make 16 behave identically, except that entering 16 applies the v1.6-b parameter set to `resultant_` and leaving 16 for any other algorithm restores the `pvb_resultant.h` defaults. Algorithms 0-15 must stay bit-identical, including the research host flow (select algo 15, then `pvb_set_resultant`). Update the P_VB_ALGO comment in pvb_engine.h and the enum comment in pvb_vb.h.
2. Kotlin (`app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb/`):
   - PvbModels.kt: `const val RESULTANT_V16 = 16` and a Model right after the v1.5 entry: key `resultant_core_v16`, title `Resultant 코어 v1.6 (실험)`, description (plain Korean, same tone as the v1.5 entry): v1.5보다 낮은 현악곡에서 들리던 "쿠쿠쿵" 같은 기저음의 원인(위상을 빠르게 당기던 동작)을 줄였습니다: 150 Hz 아래 번짐이 약 11 dB 줄었습니다(연구 측정, 14곡). 음 끝의 꼬리도 v1.5보다 짧습니다. 음이 바뀔 때 새 음높이에 붙는 시간이 약 9 ms 늦습니다. 지연은 P1과 같습니다.
   - LiveAbComparisons.kt: sides for model 15 and 16 at the user's level (like P1/D2), and two comparisons: "Resultant v1.5 vs v1.6 (실험)" and "P1 vs Resultant v1.5 vs v1.6 (셋)", with the existing MODEL_NOTE/TRIM_NOTE.
3. Tests: `tools/pvb-harness/jvm/Alpha2JniTest.kt` (model count 12 → 13 and whatever lists the ids), `Alpha3SettingsTest.kt` (id order: insert 16 right after 15), `LiveAbTest.kt` (new comparisons), and any test that enumerates algorithms or VB_ALGO_COUNT. Run whatever of these runs locally (check how CI runs them: `.github/workflows/build.yml`); if the JVM tests need the Android toolchain that is not available, say so.
4. Verify with a host build of the engine from this tree (the harness CMake in `tools/pvb-harness/`; build into a NEW directory `tools/pvb-harness/build_app16/`, do not overwrite existing build dirs):
   - V0: algorithms 0-15 bit-identical to the pre-change tree (build the pre-change HEAD daf9bba into `build_app16_ref/` via a temporary `git worktree` under `~/r3a-dev/plan16/APP16/`, removed afterwards) on several signals and block sizes, including a 15 → other → 15 switch and the research flow 15 + `pvb_set_resultant`. Reuse `~/r3a-dev/plan16/V16A/v0_check16b.py` style.
   - E1: algorithm 16 output and trace bit-identical to algorithm 15 + `pvb_set_resultant(v1.6-b set)` on the same signals.
   - E2: switching 16 → 15 gives the v1.5 output again (bit-identical to a fresh 15 after the switch fade, or state the exact rule you checked).
   - Latency of 16 equals 15.
5. Save `git diff` to `~/r3a-dev/plan16/APP16/app16.diff`, list changed files, leave everything uncommitted.

Rules: never touch slakh2100/validation or slakh2100/test. Work files in `~/r3a-dev/plan16/APP16/`. Report in concise Korean: diff summary, verification table (V0/E1/E2/latency/tests), anything not verified, file paths.
