# Brief S19-TR — layer level trim for the Resultant app models (RESULTANT_CORE.md 19.12)

You are a Sonnet worker. OFFLINE measurement only: no source changes, no commits, no downloads, never copy or commit the user's audio (read in place, numbers only), never touch slakh2100/validation or slakh2100/test, never create folders on the Windows C: drive. Work in `~/r3a-dev/plan16/S19/TR/`.

Spec: RESULTANT_CORE.md 19.12 (pre-registered rule). Library `~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so`. Rows: P1 (algo 6), v1.5 (algo 15 defaults), v1.6-c (15 + capRho 1.5, windowCreep 16, creepMode 2, betaMin .05, betaMax .1, psiSlew .03, layerHpHz 150, layerHpOrder 8, layerHpComp 1). Layer level 0 dB (the engine's vb_level_db 0), layer captured as in `~/r3a-dev/plan16/S19/L/` (also report the app-chain output difference if cheap: same chain as `~/r3a-dev/plan16/S19/LIM/`).

Songs: the 14 in `/mnt/c/Users/ksysh/Music/vanila/` and the 23 in `/mnt/c/Users/ksysh/Music/Rayark 10th Anniversary Concert Collection(Origina [214852792] [2022]/` (quote the path). Per song: a fixed excerpt (60 s from 30 s, or the whole song if shorter; fix in CHOICES.md first), only frames where P1's 150-600 Hz layer is above −70 dBFS.

Measure per song: layer 150-600 Hz level (energy, dB) core − P1 for v1.5 and for v1.6-c; also 150-200 Hz and 200-300 Hz differences; and a loudness-like check (the app-chain output, K-weighted or plain RMS, core − P1). Apply the rule: trim = −median over the 37 songs, rounded to 0.5 dB, separately for v1.5 and v1.6-c; report median, p10, p90, and the two collections separately.

Report in concise Korean: the trim values, the spread, MEASURED vs INTERPRETATION, file paths.
