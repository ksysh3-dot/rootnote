# Brief S19-SL — oracle: smoothing a_2 in sustain, and nFuture 48 on v1.6-c (RESULTANT_CORE.md 19.13.1)

You are a Sonnet worker. OFFLINE measurement + existing engine parameters only: no source changes, no commits, no downloads, never copy or commit the user's audio (read in place, numbers only), never touch slakh2100/validation or slakh2100/test, never create folders on the Windows C: drive. Work in `~/r3a-dev/plan16/S19/SL/`.

Binding spec: `~/r3-work/docs/RESULTANT_CORE.md` 19.13 and **19.13.1** (review `review_19_13.md` in this folder). Fix all open details in CHOICES.md before results.

Library `~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so`. Base row v1.6-c = capRho 1.5, windowCreep 16, creepMode 2, betaMin .05, betaMax .1, psiSlew .03, layerHpHz 150, layerHpOrder 8, layerHpComp 1 (research_core_api.set_resultant). Reuse: S19-BY code (`~/r3a-dev/plan16/S19/BY/`: renders, traces, per-voice k=2/k=3 reconstruction with the layer HP, 20-140 linear-phase band, top windows), S19-L metric code, the A5P suite for the attack guard.

Part A — oracle on the v1.6-c traces (per-voice reconstruction, k=2 and k=3, layer HP applied as in S19-BY):
- Variants: a_2 (and a_3) zero-phase smoothed over 30 and 50 ms; causal one-pole/2nd-order of the same time scale; applied only in sustain segments (from 30 ms after birth / REL→ON / note change until the next of those or ON→REL; joins continuous), onsets untouched.
- Dev windows: the 7 user windows + the top-4 absolute windows of Beyond and of Last Carnival (19.11). Paths: vanila `/mnt/c/Users/ksysh/Music/vanila/`, Beyond `/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/10. Beyond.flac`, Last Carnival `/mnt/c/Users/ksysh/Downloads/Norihiro_Tsuru_-_Last_Carnival_Acoustic_Cafe_(mp3.pm).mp3`.
- Metrics: (1) 20-140 Hz (Hann FFT) change; (2) 150-260 Hz envelope 2-30 Hz modulation energy minus the input's own (same band of the input), change; (3) a_2 jump rate > 6 dB/hop (per s); (4) body 150-600 change. Projected values = measured v1.6-c − (reconstruction baseline − reconstruction variant).
- Apply the 19.13.1 rule mechanically (fold A5 or not).

Part B — nFuture 48 on v1.6-c (engine render, no code change):
- Same metrics (1), (2), (4) on the dev windows; held-out = the other 12 vanila songs + the 23 Rayark songs (`/mnt/c/Users/ksysh/Music/Rayark 10th Anniversary Concert Collection(Origina [214852792] [2022]/`), 30-90 s excerpts, medians.
- Guards per 19.13/19.13.1 (16.16 rule vs P1 and v1.6-c): attack V3a/rise90 +2 ms, V3i, V4b +1 %p, LOGOFF R1, body −1 dB, V3d pre-echo +0.5 dB. Report-only: V3g, tail, RERISE, V6b, V3c.enter.
- Apply the 19.13 / 19.13.1 adoption rule mechanically (dev −2 dB, 5/7 user windows, held-out median not worse by more than 0.5 dB and the same sign as dev).

Report in concise Korean: tables, decisions, MEASURED vs INTERPRETATION, file paths. Long jobs in the background with logs; suites in batches of ≤ 4 rows.
