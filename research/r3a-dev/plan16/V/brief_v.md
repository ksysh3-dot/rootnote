# Brief V — where do the core's "silent" voices come from? (Resultant core, section 16.9 next step)

You are a Sonnet worker. Opus designs and judges; you measure. OFFLINE Python only, read existing caches; do not edit engine code, do not commit. Small diagnostic: aim well under one hour.

Context: ~/r3-work/docs/RESULTANT_CORE.md section 16.9 (and 16.8.1 B1/B2 for definitions). The B2 breakdown in ~/r3a-dev/plan16/D/ (ref_rows.py, ref_rows_raw.json, ref_rows_report.txt) found that 0.212 of the core v1.5 stem-aware wrong energy (0.360, F, 10 songs pooled, units = wrong energy / R3 right energy) is class "silence" (core ON/REL voice sounding while no bass note sounds). Reuse that code and the caches in plan16/A, plan16/S, plan16/D. Outputs to ~/r3a-dev/plan16/V/.

Task: split the "silence" wrong energy (time-sample level, energy-weighted, F gain, same layer as B2) into these causes, first match wins, and record the exact tests in V/CHOICES.md BEFORE computing:
1. NO-BASS SONG: the song has no bass MIDI in the excerpt (Track00023, 24, 26) — report separately how much of 0.212 this is.
2. DRUM: a drum hit (MIDI drum notes, any) within [−20, +150] ms of the sample, and the voice was born within 60 ms after that hit or its amplitude rose > 6 dB within 60 ms after it.
3. BASS-REVERB/LATE: within 400 ms after a bass note end, at that note's pitch (0.5/1/2/3×, 50 cent) — stem below −15 dB but still decaying.
4. OTHER-INSTRUMENT: some non-bass, non-drum MIDI note is sounding whose f0 or 2·f0 is within 100 cent of the voice f / k for k=1..3 (looser than v6b), or a non-bass stem has its 40–300 Hz energy within 10 dB of its excerpt p95 at that time.
5. OTHER.

Also report: per song, the share of the voice's lifetime spent in silence for silence voices (median), and the voice f distribution of silence wrong energy (deciles), and how many distinct voices carry 80 % of it.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob). Report concise Korean: table of shares (with and without no-bass songs), MEASURED vs INTERPRETATION, file paths.
