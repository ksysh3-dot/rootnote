# Brief B — error-injection blind set (Resultant core, section 16.4)

You are a Sonnet worker. Opus (the coordinator) designs and judges; you build. Do not edit engine code, do not commit (audio is never committed).

Binding spec: ~/r3-work/docs/RESULTANT_CORE.md **section 16.4** (read it fully; context sections 3 and 16 common: engine harmonic set k = 2..8 up to 700 Hz with the engine `lookup()` weights and voicing-0 rolloff — see app/src/main/cpp/libpvb/pvb_resultant.inc:780 `amplitudes()`).

Look at how earlier blind sets were rendered and packaged and follow the same conventions (levels, file naming, key hashing, listening-spot sheet): tools/pvb-harness/research_r4l2_render_pairs.py, research_r4l6b_render_pairs.py / research_r4l6c_render_pairs.py, and the previous sets under C:\Users\ksysh\rootnote-duo\listen\ (WSL: /mnt/c/Users/ksysh/rootnote-duo/listen/).

Build:
- Reference layer: oracle pitch (bass MIDI lowest note, octave by the existing YIN agreement rule as in research_resultant_pitch_truth.py) and MIDI boundaries, amplitude by single-voice LS of the clean bass stem sum at the true f (the same as section 16.3 R3), synthesized with the engine harmonic set, at the engine voicing-0 default level; mixed with the original track mix. 6 excerpts of 8–10 s from Slakh TRAIN tracks (include kick+bass passages; you may use the 10 V6 tracks).
- Pairs: E1–E6 as specified (one error type per pair; error energy −6 dB re the reference layer over the active time; E5 = 30 ms delay) plus 2 null pairs. Assign excerpts to error types so each error type appears once (8 pairs total); randomize A/B per pair with a fixed seed.
- Package into C:\Users\ksysh\rootnote-duo\listen\blind_inj\ : WAV files (48 kHz, same loudness for A/B within a pair), a sheet `listen.md` in Korean with pair numbers, listening spots (time ranges where the error is active, identical for A and B, which never reveals the key), and the question per pair: "어느 쪽이 더 거슬리나 (A/B/같음) + 거슬림 1–5".
- Key: write the key file OUTSIDE the listen folder (~/r3a-dev/plan16/B/key.json), and put only its sha256 into listen.md. Do not print the key in your report.

Rules: Slakh TRAIN only — never touch any path containing slakh2100/validation or slakh2100/test. Code in ~/r3a-dev/plan16/B/. Report: what was built, levels, the key hash, any deviation from 16.4 and why — not the key itself.
