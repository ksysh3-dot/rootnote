# Brief S19-R — review of the 19.2 structural change (missing AND removable items) + code questions

You are a Sonnet reviewer. READ-ONLY: no code changes, no builds, no commits, no downloads. Write only `~/r3a-dev/plan16/S19/R/review.md`.

Read: `~/r3-work/docs/RESULTANT_CORE.md` sections 0, 16.16 (the procedure: P1 is the baseline, only audible-harm guards, mixed-result rule, stage 0 stops only if even the oracle gains nothing, no post-hoc threshold changes), 18.9-18.16, 19, 19.1, 19.2. Code: the Resultant core in `~/r3-work` (`git grep -n` for pvb_resultant, vb_algo 15, betaMin, psiSlew, f_off, Np) and P1's synthesis in the same tree (pvb_vb.h / pvb_engine.h and what they include).

Answer the code questions with file:line citations, and mark each answer MEASURED (read in code) or INFERRED:
1. Timing: at the point where the core sets each voice's f_osc, θ and amplitude for a hop, how much future input (ms / hops) has the analysis seen, and how far behind analysis does synthesis run? Could synthesis be delayed by 1-4 hops to allow short zero-phase smoothing, and what would that add to the 146.9 ms total latency?
2. P1: how does P1 generate its harmonic layer — oscillators driven by tracked f and phase correction, a nonlinearity on the filtered input, or other? How are its per-partial frequency and amplitude smoothed or interpolated per sample? (This is the reference for why P1's 20-150 Hz skirt is ~5-7 dB lower.)
3. The Resultant core: how are A·c·σ, f_osc and θ interpolated between hops per sample (steps, linear ramps, other)?
4. Rough cost of a second oscillator per voice during crossfades (relative to the measured ~18 % phone load).
5. Where would the onset reset hook in (voice state machine, the θ pull, the f_off PLL), and what could break bit-identity (V0) when the new params are 0?

Then the design review of 19.2 (stage 0 and stage 1): what is MISSING that could make it fail or mislead (measurement validity of the offline oracle on the reconstruction, the segment-edge join, the decision rule, the reset hysteresis, phase alignment loss, tail/attack effects of crossfades), and what is REMOVABLE (over-strict, unnecessary, or defensive items that cost work without protecting anything audible). Be concrete; rank by impact. Concise Korean.
