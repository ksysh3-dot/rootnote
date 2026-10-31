# Brief B1 — diagnose the "쿠쿠쿵" on the user's string music (RESULTANT_CORE.md 18.6)

You are a Sonnet worker. Opus judges. Diagnosis only: no engine changes, no builds in `~/r3-work` (another worker is editing C++ there right now — do NOT run build scripts or git commands that modify it), no commits, no downloads.

Spec: `~/r3-work/docs/RESULTANT_CORE.md` section **18.6** (read 16.15 for the diagnostic-capture layer and 18.4 for context).

Audio: the user's folder `/mnt/c/Users/ksysh/Music/vanila/` (14 FLAC files; the target is `08. Apparition.flac`). Read in place with soundfile; never copy them into a repo, never commit audio; write only to `~/r3a-dev/plan16/B1/`.

Libraries (use as they are, read-only):
- v1.5 and P1: `~/r3-work/tools/pvb-harness/build_core/libpvbcapi.so` (algo 15 defaults = v1.5, algo 6 = P1).
- v1.6-a base: `~/r3-work/tools/pvb-harness/build_core16a/libpvbcapi.so` with algo 15 and capRho = 1.5 (param 17; see `research_core_api.py` PARAMS — if the checked-out api file changes under you, copy the 084ea45 version of `research_core_api.py` into B1 and import that copy).
- Render and capture conventions: `~/r3a-dev/plan16/P/` (pcommon.py, p_render.py — the diagnostic capture = layer after the output filter, before mixing) and `~/r3a-dev/plan16/L/build.py`. Run from `~/r3-work/tools/pvb-harness` with PYTHONPATH=.:study (read-only use is fine).

Do:
1. CHOICES.md before results: envelope, the 2-12 Hz modulation measure, the input-subtraction, window/hop, how windows are ranked.
2. Apparition: render the three engines (whole track, mono or stereo as the convention says), compute the pulsing-excess series, rank windows where v1.5 exceeds P1, take the top 3 (non-overlapping).
3. For each window: song time (mm:ss) for the user to check by ear; input low-band spectral peaks over time (what notes/instruments: low strings? vibrato?); the trace (voice ids, f_track/f_osc, A, state, coasting, pairs within 14 Hz, births/REL cycles per second, the rate of the layer pulsing in Hz); classify the mechanism (a)-(e) per 18.6 with the evidence; and say whether v1.6-a base (capRho 1.5) changes it.
4. All 14 songs: table of pulsing excess per song for P1 / v1.5 / v1.6-a base (median and 95th percentile over windows), plus time of each song's worst v1.5 window.

Report in concise Korean: per-window findings with timestamps, mechanism with evidence, the 14-song table, MEASURED vs INTERPRETATION, file paths. No adoption decisions.
