# Brief R19.7 — short review of the 19.7 pre-registration (layer high-pass + phase compensation)

You are a Sonnet reviewer. READ-ONLY (no code changes, builds, commits, downloads). Write `~/r3a-dev/plan16/S19/H/review_19_7.md` and return it as your report, concise Korean, at most ~40 lines.

Read `~/r3-work/docs/RESULTANT_CORE.md` 16.16, 19.5, 19.6, 19.6.1, 19.7, and the code where the core's layer is synthesized and leaves the core (`app/src/main/cpp/libpvb/pvb_resultant.inc` synthesize(), `out_`, and how `pvb_vb52.cpp` takes it: sample rate of the core output, kOutSos, resampling).

Answer, each with file:line where code is involved:
1. Does the main metric measure the complaint? (sub-150 absolute level and leakage-free ratio; the user hears "쿠쿠쿵" on a phone speaker; is there a better or additional measure of what a phone speaker would turn into audible thumps, e.g. excursion-weighted low-band energy?)
2. Is the baseline right under 16.16 (P1 for guards, v1.6-b for the main criterion), and are any guards missing or over-strict?
3. What can be removed (rows, guards, report items) without losing protection against audible harm?
4. Implementation pitfalls: where exactly the high-pass should sit (core output rate, before or after kOutSos, both channels), whether the phase compensation at k·f_osc is correct for changing f and for the filter's own state at onsets, group-delay effect on attack, bit-identity when params 20-22 are 0.
Rank by impact.
