# Brief S19-D — where does the remaining "쿠쿠쿵" splatter come from? (RESULTANT_CORE.md 19.1)

You are a Sonnet worker. Diagnosis only: no engine source changes, no commits, no downloads, never copy or commit the user's audio. Work in `~/r3a-dev/plan16/S19/`.

Spec: `~/r3-work/docs/RESULTANT_CORE.md` section **19.1** (context 18.9, 18.11–18.16; the A5' measurement code in `~/r3a-dev/plan16/A5P/` and the B1-2 per-voice reconstruction in `~/r3a-dev/plan16/B1/b12/`).

Rows (library `~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so`, 5c1c62c, PARAMS from `research_core_api.py` at HEAD): (1) v1.6-a base (capRho 1.5, windowCreep 16, creepMode 2, β .2/.9, psiSlew .12); (2) A5'-best (same + β .05/.1, psiSlew .03). Optionally (3) phase pull off (β 0/0, psiSlew .01) as the A5' oracle row.

Data: the 7 user windows (Apparition 0:52.0, 1:28.5, 2:03.5, 3:21-3:25 as two 2 s windows; Reminiscence 1:36, 1:53) and all 14 songs of `/mnt/c/Users/ksysh/Music/vanila/` read in place.

Method (fix details in CHOICES.md before results):
- The rendered layer from the diagnostic capture (as A5/A5P), 20-150 Hz band, 5 ms box energy.
- Per hop and voice event tags from the 22-field trace: birth, REL→ON, ON→REL, release (voice end), window change (N_v or N_J, field Np; > 25 %), f_osc jump > 2 Hz/hop, amplitude (A·c·σ) jump > 6 dB/hop, f_track note change > 50 cents within 2 hops. Map trace hop time to the layer time with the conventions used in A5P.
- Attribute each 5 ms box of 20-150 Hz energy to the first matching event (list order) within ±10 ms over the voices that carry most of the k=2 energy in that box; report the share per event type and the share with no event. Do it for each row, pooled over the 7 windows and over each song.
- Also report the event rates (per second) per row, and the 20-150 Hz energy per event (energy share / event share) so frequent-but-mild and rare-but-heavy events can be told apart.

Report in concise Korean: per-row attribution tables (user windows pooled; 14-song median), what remains after the phase pull is slowed (row 2 vs 1), MEASURED vs INTERPRETATION, file paths. No design decisions.

Rules: Slakh not needed (do not touch slakh2100/validation or slakh2100/test). Long jobs in the background with logs.
