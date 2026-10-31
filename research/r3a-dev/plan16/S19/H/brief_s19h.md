# Brief S19-H — offline oracle: a steep high-pass on the layer below 150 Hz (RESULTANT_CORE.md 19.6 candidate 1)

You are a Sonnet worker. OFFLINE only: no engine source changes, no builds or git changes in `~/r3-work`, no commits, no downloads, never copy or commit the user's audio (numbers only). Work in `~/r3a-dev/plan16/S19/H/`.

Context: RESULTANT_CORE.md 19.5 (leakage-free metric, S19-L method in `~/r3a-dev/plan16/S19/L/`) and 19.6 (the user hears the "쿠쿠쿵" reduced with v1.6-b, still partly present in Apparition's later windows; phone speaker; the layer's sub-150 Hz bypasses the input's 100 Hz LR4 high-pass in the app chain, `pvb_engine.h`).

Rows: v1.6-b (b3p2, render exactly as S19-L / `A5P/a5prows.py`, library `~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so`), and for reference P1 and v1.5. Counterfactual: apply to the rendered v1.6-b layer a causal high-pass (realizable in the engine): Butterworth / LR at fc ∈ {120, 135, 150} Hz × order ∈ {4, 8} (fix the exact set and filter form in CHOICES.md before results).

Measure (S19-L definitions; 7 user windows pooled and per window, 12 held-out songs median):
1. Sub-150 absolute level (dBFS) and the leakage-free ratio 20-140 / 150-600, and the 20-140 Hz burst share.
2. Body loss: 150-600 Hz level change, and 150-200 / 200-300 Hz level changes (k=2 of low notes).
3. Per-window residual after the cut, ranked — which windows (especially Apparition 2:03, 3:21-3:25) remain highest, compared with P1.
4. Phase/group delay of each filter at 150, 200, 300 Hz (the layer must stay aligned with the input's own partials; report the phase shift in degrees at k·f for f = 75, 100, 125 Hz).
5. Same metrics for v1.6-b without the cut, P1 and v1.5 as anchors.

Report in concise Korean: tables, MEASURED vs INTERPRETATION, file paths. No adoption decisions. Rules: never touch slakh2100/validation or slakh2100/test. Long jobs in the background with logs.
