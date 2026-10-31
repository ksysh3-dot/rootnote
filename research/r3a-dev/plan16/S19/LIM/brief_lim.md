# Brief S19-LIM — the full app chain at the user's strength (+6 dB): does the output limiter pump with the layer's low band? (RESULTANT_CORE.md 19.8)

You are a Sonnet worker. OFFLINE measurement only: no source changes, no commits, no downloads, never copy or commit the user's audio (numbers only), never touch slakh2100/validation or slakh2100/test, never create folders on the Windows C: drive. Work in `~/r3a-dev/plan16/S19/LIM/`.

Context: the user listens on a phone speaker with the virtual-bass strength at **+6 dB**; all earlier measurements used the default layer level. The app chain (`~/r3-work/app/src/main/cpp/libpvb/pvb_engine.h` header comment): input → LR4 high-pass (100 Hz) → low-mid bell → treble bell → + layer → output gain → look-ahead true-peak limiter. The app's listening defaults are in `~/r3-app/app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb/PvbAbConditions.kt` (`v11` / `v11vb`) and PvbSettings.kt; use the same values (hp 100, low-mid 220 Hz +3 dB Q 1, treble 4.5 kHz −3 dB Q 0.6, output gain and limiter ceiling as the app defaults — read them, write them in CHOICES.md).

Library: `~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so` (has params 20-22). Engine wrapper: `tools/pvb-harness/test_engine.py` Engine (check its kwargs for vb_level_db, hp, bells, out gain, limiter) and `research_core_api.set_resultant`. Rows: P1 (algo 6), v1.5 (algo 15 defaults), v1.6-b (15 + capRho 1.5, windowCreep 16, creepMode 2, betaMin .05, betaMax .1, psiSlew .03), v1.6-c (v1.6-b + layerHpHz 150, layerHpOrder 8, layerHpComp 1); and "layer off" (vb off, same chain). Strengths: +6 dB (main) and 0 dB.

Data: the 7 user windows (Apparition 0:52.0, 1:28.5, 2:03.5, 3:21, 3:23; Reminiscence 1:36, 1:53; 2 s each, rendered from the whole song as before so the state is warm), and the 12 other vanila songs (60 s + 30 s) as held-out. Files in `/mnt/c/Users/ksysh/Music/vanila/`, read in place.

Measure per row × strength (fix definitions in CHOICES.md before results):
1. Limiter gain reduction over time (from a diagnostic/meter if the engine exposes it; otherwise output / pre-limiter ratio): share of time with GR > 1 dB and > 3 dB, and the 2-12 Hz modulation depth of the GR (pumping).
2. The output 20-400 Hz peak and 2-12 Hz envelope pulsing (excursion proxy) relative to "layer off".
3. Correlation of GR events with the layer's 20-150 Hz bursts (does the layer's low band trigger the limiter?).
4. Per window, especially Apparition 3:21 / 3:23 vs the others.

Report in concise Korean: tables, MEASURED vs INTERPRETATION, file paths. No adoption decisions. Long jobs in the background with logs.
