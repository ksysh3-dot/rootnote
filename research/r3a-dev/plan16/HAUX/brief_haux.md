# Brief H-aux — stage 0: the input's upper harmonics as a parallel decision aid (RESULTANT_CORE.md 18.10)

You are a Sonnet worker. Opus judges. OFFLINE analysis only: no engine changes, no builds or git changes in `~/r3-work` (another worker is editing C++ there now), no commits, no downloads, never copy or commit the user's audio. Write only to `~/r3a-dev/plan16/HAUX/`.

Spec: `~/r3-work/docs/RESULTANT_CORE.md` section **18.10** (context: 16.9 silent voices and cause tags, 16.10.2 the weak 3 kHz K2 cue, 16.14 ghost attribution, 18.9 the "쿠쿠쿵" cause).

Inputs and reuse (read/import, do not modify):
- v1.5 core traces and truth for the 10 Slakh-train dev songs: `~/r3a-dev/plan16/D/` (dcommon.py, ref_rows.py), `~/r3a-dev/plan16/V/v_run.py` (silent-voice cause tags), `~/r3a-dev/plan16/T/` (16.14 attribution code), `~/r3a-dev/la0/` (data/caches; 48 kHz mix and stems; check how the trace time maps to input time — LAG/latency conventions are in 16.x and dcommon).
- User windows (Apparition 0:52.0, 1:28.5, 2:03.5, 3:21-3:25; Reminiscence 1:36, 1:53) and the k=2 jump analysis: `~/r3a-dev/plan16/B1/b12/` (its b12_*.py reconstruct the rendered a_2 per voice and count >6 dB jumps — reuse it). Audio read in place from `/mnt/c/Users/ksysh/Music/vanila/`.
- Library read-only: `~/r3-work/tools/pvb-harness/build_core/libpvbcapi.so` (v1.5).

Auxiliary channel: for each trace hop and voice f (f_track), LS-fit sinusoids at k·f, k = 2..12 (stop at 2 kHz), on the 48 kHz input (mono), window within the engine's budget (past + future ≤ the future the core already uses; try two lengths, e.g. ~40 ms and ~85 ms; fix them in CHOICES.md first). Features: H_sal (fitted harmonic energy k=2..K over the local floor between partials), f_h (comb-refined f0), a_h(t) (k=2..6 envelope).

Questions (18.10): Q1 per-song AUC real-bass vs ghost voices using H_sal (and the best simple combination), compared with the 3 kHz K2 cue of 16.10.2; Q2 pitch error vs MIDI and hop-to-hop jitter of f_h vs f_track on matched voices, and the count of >2 Hz/hop jumps of f_h vs f_osc in the user windows; Q3 at each >6 dB per-hop jump of the rendered v1.5 a_2 in the user windows, the change of the input's own partial at the same k·f — report the share of jumps the input does not support (input change < 2 dB). Also a rough real-time cost estimate for a decimated (8-12 kHz) version.

Apply the 18.10 stop rule mechanically (stop only if all three are useless) and report. Report in concise Korean: tables per question, MEASURED vs INTERPRETATION, file paths, and one paragraph on what an H-aux-based fix should key on. No adoption decisions.
