# Brief R19.13 — short review of the 19.13 pre-registration (A5 slew re-test + nFuture 48 on v1.6-c)

You are a Sonnet reviewer. READ-ONLY. Write `~/r3a-dev/plan16/S19/SL/review_19_13.md` and return it, concise Korean, at most ~35 lines.

Read `~/r3-work/docs/RESULTANT_CORE.md` 16.16, 18.9, 18.11, 19.5, 19.11, 19.12, 19.13; the preserved diff `~/r3a-dev/plan16/A5/a5.diff` and its results `~/r3a-dev/plan16/A5/` (what broke the attack at low slews, which modes passed); the current core `~/r3-work/app/src/main/cpp/libpvb/pvb_resultant.h/.inc` (kParams 22, params 20-22 layer high-pass).

Answer, ranked by impact:
1. Does the main metric measure the remaining complaint (75-130 Hz notes' k=2 event-bound energy below 150 Hz on a phone speaker)? Anything better or additional (e.g. the 150-260 Hz envelope jump rate itself)?
2. Baselines and guards right under 16.16? Missing or over-strict?
3. What rows/guards/report items can be removed?
4. Porting pitfalls of a5.diff onto the current core (param indices 23-24, interaction with the layer high-pass and its phase compensation, slew applied to A·c·σ vs to each a_k, bit-identity at 0, the k=2 jump definition in 19.11 vs what the slew limits).
