# Brief S19-L — is the remaining "20-150 Hz" gap to P1 real low-band energy or filter leakage of steady partials above 150 Hz? (RESULTANT_CORE.md 19.3)

You are a Sonnet worker. OFFLINE measurement only: no engine source changes, no builds or git changes in `~/r3-work`, no commits, no downloads, never copy or commit the user's audio (keep only numbers). Work in `~/r3a-dev/plan16/S19/L/`. Other workers use `~/r3a-dev/plan16/S19/NF/` — do not touch it.

Context: `~/r3-work/docs/RESULTANT_CORE.md` 18.9, 18.11, 19.1, 19.3. The primary metric (`~/r3a-dev/plan16/A5P/p_primary.py`) is the 20-150 / 150-600 Hz layer ratio with `butter(4, [20,150], 'bandpass')` applied by `sosfiltfilt`; its magnitude above 150 Hz falls only about 11 dB at 170 Hz and 21 dB at 200 Hz, so steady k=2 partials of 75-130 Hz notes (150-260 Hz) can dominate it. The stage-0 oracle (19.3) found that even constant trajectories in sustain remove only ~1 dB of the "no-event" energy.

Rows: P1, v1.5, v1.6-a (b0p0), v1.6-b (b3p2), phase-pull-off f4 — render exactly as p_primary / `A5P/a5prows.py` do (library `~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so` for core rows; P1 as p_primary does). Data: the 7 user windows (Apparition, Reminiscence; `/mnt/c/Users/ksysh/Music/vanila/`, read in place) and, for a held-out check, the other 12 vanila songs (same excerpt convention as the 14-song table or a fixed 30 s excerpt; fix in CHOICES.md first).

Measure per row, pooled over the 7 windows and per window (fix details in CHOICES.md before results):
1. Reproduce the primary ratio (must match A5P numbers).
2. Leakage share: split the layer by FFT (brick-wall at 150 Hz) into a below-150 part and an above-150 part; pass each through the primary's sosfiltfilt band; report energy(above-part through band) / energy(layer through band).
3. Leakage-free spectrum: band energies from FFT bins of the whole window, in dB relative to 150-600 Hz: 20-60, 60-100, 100-130, 130-150, 150-200, 200-300, 300-600; and the ratio 20-140 / 150-600.
4. Steady vs dynamic inside 20-140 Hz: linear-phase FIR band 20-140 Hz (steep, transition ≤ 10 Hz), 5 ms box energies; report the median box level, p95, and the share of energy above 2× the 200 ms running median (bursts).
5. The same for 150-260 Hz (the k=2 region of low notes): level re 150-600, and its 2-12 Hz envelope modulation depth (the B1 pulse measure, `~/r3a-dev/plan16/B1/b1_mod.py`) minus the input's.
6. 12-song held-out medians of items 2, 3 (20-140 / 150-600) and 5.

Report in concise Korean: tables (rows P1 / v1.5 / v1.6-a / v1.6-b / f4), the answer to "how much of each row's primary 20-150 energy is leakage, and how far is each row from P1 on the leakage-free bands", MEASURED vs INTERPRETATION, file paths. No adoption decisions. Rules: never touch slakh2100/validation or slakh2100/test. Long jobs in the background with logs.
