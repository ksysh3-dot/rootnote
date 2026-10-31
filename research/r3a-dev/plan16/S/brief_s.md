# Brief S — candidate vs segmentation split (Resultant core, section 16.7)

You are a Sonnet worker. Opus designs and judges; you measure. OFFLINE Python only: do not edit C++/engine code, do not commit.

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.7** (read it fully). Context: 16.3 (ladder rows, metrics, gain variants), 16.5 (results), 16.6 (new V5a criterion), 14 (LA candidate pool and segments).

Reuse ~/r3a-dev/plan16/A/ (synth16.py, ladder.py, ladder_report.py, stems.py, cache/) and ~/r3a-dev/la0/ (cache/, segment and candidate code) and the core v1.5 voice traces already cached (research_core_api.py / plan16/A or la0 caches). Do not re-render what is cached. Another worker is concurrently using ~/r3a-dev/plan16/A2/ — do not write there. New code and outputs go to ~/r3a-dev/plan16/S/.

Tasks:
1. Build rows S1, S2-LA, S2-core exactly as 16.7 specifies, with both matched (M) and fixed (F) gain, on the same 10 tracks / 0–30 s excerpts and T60 V5a excerpt as 16.3. Reuse R1, R2, R3 values from plan16/A (recompute only if needed for consistency; say so).
2. Report all 16.3 metrics plus "missing" share and boundary error distributions (vs MIDI and vs stem activity; median, p10, p90).
3. Apply the 16.7 decision rule mechanically (shares, the 10 % missing override) and state the outcome.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Record any reading choice for ambiguous spec text (e.g. what exactly is "the tracker candidate pool" inside a MIDI segment, how core ON–REL intervals map to segments) in S/CHOICES.md BEFORE computing results. Keep runtime modest; long jobs in background with logs.

Report (concise, Korean): tables, decision outcome, MEASURED vs INTERPRETATION separated, file paths.
