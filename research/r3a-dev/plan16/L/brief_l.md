# Brief L — core v1.5 vs P1 blind on Track00025 / Track00026 (Resultant core, section 16.11)

You are a Sonnet worker. Opus designs and judges; you build the listening set. Do not edit C++/engine code, existing files in other plan16 folders, or the docs. Do not commit.

## Goal
The user hears whether core v1.5's "voices where no bass is sounding" (16.9 silent-voice wrong energy, 54 % of it in Track00025, most of the rest in Track00026) are audibly harmful compared with P1, in the real full output.

## Inputs (reuse, do not modify)
- Renders: the engine via `~/r3-work/tools/pvb-harness/research_core_api.py` (vb_algo 15 = core v1.5, defaults; P1 = the same build with the algo not set to 15, which is bit-identical to P1 per RESULTANT_CORE.md section 1) or the reference build in `tools/pvb-harness/build_core` / `build_ref_core` — record which library file and its sha256. Follow the full-output convention of `tools/pvb-harness/research_blind_pairs.py` and the latest `research_r4l6c_render_pairs.py` (what the app plays: mix + layer through the output chain, same output gain for both). If those scripts use a phone-speaker simulation or a fixed loudness target, use the same.
- Silent-voice locations: `~/r3a-dev/plan16/V/` (v_run.py cause tags) and `~/r3a-dev/plan16/D/` (dcommon.py, ref_rows.py). Slakh TRAIN only. Never touch any path containing slakh2100/validation or slakh2100/test (no ls/glob).

## Set (8 pairs)
1. Choose the excerpts BEFORE rendering any pair, and write them to `L/CHOICES.md` with the rule and numbers.
   - Per song (T25, T26): within the same 30 s analysis excerpts used in 16.9, slide a 9 s window (hop 0.25 s) and score it by core v1.5 silent-voice wrong energy (all causes). Take the top 3 non-overlapping windows per song. These are 6 test windows.
   - Two null windows: the 4th-best window of each song (non-overlapping with the others; if none, the best remaining window of either song). One null pair is core|core, the other P1|P1, chosen by the seeded RNG.
2. Per pair, render core v1.5 and P1 on the same 9 s window (render with enough pre-roll so the engine is settled, then cut). File = A (9 s) + 1 s silence + B (9 s), 48 kHz, same format as `listen/blind_inj`.
   - A/B side and pair order: seeded RNG (seed recorded in the key).
   - Loudness: match B to A by full-band RMS within each pair (report the correction in dB; if it exceeds 1 dB report the pair to Opus, do not hide it). Common scale so the pair peak ≤ 0.95.
3. Listening spots: 3 non-overlapping 1 s windows (hop 0.25 s) per pair, ranked by core v1.5 silent-voice wrong energy in that window. Use the same rule for test and null pairs, so the spots do not reveal which pairs are nulls or which side is core.
4. Key: `~/r3a-dev/plan16/L/key.json` with per pair: track, window start, A and B names (core / P1), loudness correction, spots, seed. Compute sha256 of the sorted-key JSON and write it in the sheet. The key stays OUTSIDE the listening folder.

## Output
- `C:\Users\ksysh\rootnote-duo\listen\blind_core\` (WSL: /mnt/c/Users/ksysh/rootnote-duo/listen/blind_core/): `core_1.wav` .. `core_8.wav` + `listen.md` in Korean, same layout as `listen/blind_inj/listen.md`, with these answers per pair:
  - 더 거슬리는 쪽 (A / B / 같음) + 거슬림 1–5
  - 베이스가 더 좋은 쪽 (A / B / 같음)
  - 메모
  The sheet says: listening is not used as an adoption verdict; it ranks harm. It must not mention core, P1, nulls, or which windows are which.
- Build script and log in `~/r3a-dev/plan16/L/`.

## Report (concise Korean)
Library path + sha256, the 8 windows (song, start), per-pair loudness correction and peak, key sha256, file paths. MEASURED vs INTERPRETATION separated. Do not report which side is core.
