# Brief S19-HP — implement and measure the layer high-pass + phase compensation (RESULTANT_CORE.md 19.7, 19.7.1)

You are a Sonnet worker. Opus reviews and commits. Do NOT commit or push. No downloads. Never copy or commit the user's audio (numbers only). Never touch slakh2100/validation or slakh2100/test.

Binding spec: `~/r3-work/docs/RESULTANT_CORE.md` **19.7 and 19.7.1** (context 19.5, 19.6.1; review `~/r3a-dev/plan16/S19/H/review_19_7.md`). Tree: `~/r3-work` (branch research/resultant-core-20261030; `git status` must show no source changes before you start). Keep the code style and comment density.

Code (app/src/main/cpp/libpvb/pvb_resultant.h/.inc, and pvb_vb52.cpp only if the filter must sit there):
- Params 20 `layerHpHz` (0 = off), 21 `layerHpOrder` (4 or 8, Butterworth), 22 `layerHpComp` (0/1): kParams 19 → 22, setParams validation, `tools/pvb-harness/research_core_api.py` PARAMS/DEFAULTS.
- A causal Butterworth high-pass on the whole 3 kHz core output, in series with kOutSos; state cleared on reset.
- With 22 = 1, subtract the filter's phase at k·f_osc (3 kHz digital response) in BOTH branches of the ψ target (present / psi52 constant). Verify the sign with one pure sinusoid (the output partial's phase vs the input partial must match the unfiltered case within 0.05 rad in steady state).
- Params 20-22 at 0 → bit-identical to the current HEAD (V0 like `~/r3a-dev/plan16/V16A/v0_check16b.py`: several signals, block sizes, plus the v1.6-b set). Build into `tools/pvb-harness/build_core19/`. Save `git diff` to `~/r3a-dev/plan16/S19/HP/hp.diff`. Leave uncommitted.

Measure (rows on v1.6-b: BW8 150 comp 1, BW8 135 comp 1, BW8 150 comp 0; anchors P1, v1.5, v1.6-b), reusing the S19-L / S19-H code (`~/r3a-dev/plan16/S19/L/`, `.../H/`) for the main metric and the A5P suite (`~/r3a-dev/plan16/A5P/`) for V2, V3a/rise90:
- Main: sub-150 absolute (Hann FFT 20-140 Hz) and leakage-free ratio, 7 user windows pooled and per window, 12-song median.
- Guards per 19.7.1: onset ringing (20-140 Hz energy 0-100 ms after onsets — define onsets from the trace births / REL→ON, fix in CHOICES.md first), body 150-600, V2.k2/k3, analysis trace (voice states, f, A) bit-identical to v1.6-b.
- Report: the phone-speaker excursion proxy (dry after the app's HP100 LR4 + layer, 20-400 Hz peak amplitude and 2-12 Hz pulsing; P1 / v1.5 / v1.6-b / rows), attack, 150-200 Hz change, per-window residual.
- Apply the 19.7/19.7.1 decision mechanically (write decide script before results).

Work files in `~/r3a-dev/plan16/S19/HP/`. Run suites in batches of ≤ 4 rows. Long jobs in the background with logs. Report in concise Korean: diff summary, V0, sign check, tables, decision, MEASURED vs INTERPRETATION, file paths.
