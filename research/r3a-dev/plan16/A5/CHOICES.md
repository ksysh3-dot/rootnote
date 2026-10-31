# Plan16 A5 (RESULTANT_CORE.md 18.9): choices

## Where the limit acts (code: `ResultantCore::slewLimit`, called from `amplitudes`)
* On the per-voice amplitude `base = A c sigma` that `amplitudes()` turns into the harmonic targets `a_k = G_L g w_k R_k base`, i.e. on the hop-end value that `synthesize()` interpolates linearly to from the previous hop-end value. Every harmonic of the voice gets the same factor. Up and down, `ampSlewDb` dB per hop (5.33 ms), measured against the amplitude *rendered* at the end of the previous hop (`Voice::ampR`, after the limit), so the limit is a true rate limit on the rendered track, not on the fit.
* ON<->REL ramps obey it because they are only changes of `c` inside `base`.
* Params 20 `ampSlewDb` (0 = off, else 0.1..40) and 21 `slewOnsetMode` (0, 1, 2); `kParams` 19 -> 21. All off = bit identical (V0, `v0_check_a5.log`: 235 cases True, none False; 16c with 20/21 = 0 equals 5c1c62c for (0,0,0), (1.5,8,0), (1.5,16,2) and equals v1.5 for (0,0,0), whole output + 22-field trace, blocks 256 / 1 / 480).

## Zero / near-zero previous amplitude
* The previous amplitude counts as at least `kRSlewFloor` = 1e-5 (-100 dBFS). So a voice (or a REL voice that has decayed) rises from silence at the slew rate; it is not free for its first hop. A target under the floor is taken as it is once the limit has come down to the floor (no endless approach to zero).
* The hop in which a REL voice is freed (`u.dead`, c forced to 0) is not limited: it ends at zero exactly as before (otherwise a limited tail would be cut off by the slot being freed).
* Births: `Cand` voices have `base = 0`, so `ampR = 0` and a birth with `slewOnsetMode = 0` climbs from -100 dBFS at the slew rate (this is the attack risk of 18.9; mode 0 is expected to fail the attack guards).

## slewOnsetMode
* 1: at birth (CAND -> ON) `slewFree = 3` when `snr >= snrFastDb` (22 dB, the SNR of that hop): the rise limit is waived in the birth hop and the next two (3 `amplitudes()` calls); the fall limit is never waived.
* 2: 1 plus REL -> ON after more than 50 ms in REL (`relHops * 16/3000 s > 0.050`, counted hop by hop from entering REL, reset at each entry into REL incl. the merge path) also sets `slewFree = 3`.

## Primary metric (`a5_primary.py`, `primary_*.json`, `primary_summary.json`)
* Whole songs (Apparition, Reminiscence; `/mnt/c/Users/ksysh/Music/vanila/`, read in place, polyphase to 48 kHz, no audio kept), diagnostic layer capture (after the output filter), engine latency removed, mono mean of the two layer channels, zero-phase 4th-order Butterworth 20-150 / 150-600 Hz on the whole layer (as `b12common.py`), mean square over each 2 s window. Windows (input time): Apparition 52.0, 88.5, 123.5, 201.0 and 203.0 (3:21-3:25 as two 2 s windows), Reminiscence 96.0, 113.0.
* Ratio = 10 log10(sum of the 20-150 band energies / sum of the 150-600 band energies) over the 7 windows (energy pooled), per window too.
* Jumps: from the voice trace field `a_2` (rendered k=2 amplitude at the hop end), same slot and same voice id in two consecutive hops, state ON/REL in both, both amplitudes > 1e-7, |change| > 6 dB; summed over the 7 windows.
* Body check: pooled mean-square level of the 150-600 Hz layer (dBFS) >= base - 2 dB (per-window values are in `primary_summary.json`).

## Guards (`decide_a5.py`, all against the v1.6-a base unless stated)
V3a, rise90 bare and 25 dB <= +2 ms; V3b <= +1 dB; V3i.trans <= 0.5 /s (absolute); V4b both items <= +1 %p; LOGOFF 4.73 s R1 <= max(3, P1 + 1) (absolute, `burst_a5.py`); V3e.df10.beat <= +1 dB; V3g 35/45 noREL <= v1.5 + 5 hops; right-layer F >= base - 0.5 dB; body (above). Suite = `research_core_metrics` via `fmetrics_a5.py` (16c library, P1 column from `core_results/p1_baseline`).
* The right-layer F is trace-based (la0/rows.py reads A c sigma from the trace). With the slew limit the trace A, c, sigma are not what is rendered, so F is measured with a **diagnostic library** (`dbgsrc/F`, not part of the diff) whose trace carries (A, c, sigma) = (ampR, 1, 1). Base F with it = +0.444 dB = the value of plan16/V16A (ii16a2). V6b (suite) is also trace-based and therefore does not change with the slew (10.94 for all A5 rows); it is reported only.

## Report-only diagnostics beyond the 9 rows (not part of the decision)
* Oracle rows = slew alone (mode 0) at 1, 0.5, 0.25, 0.1 dB (primary only).
* Oracle K (`dbgsrc/K`, slewOnsetMode 3 in a scratch copy): the same limit on every harmonic amplitude a_k instead of on A c sigma (4, 2, 1, 0.5 dB).
* `a5_spec.py`: pooled periodogram band energies of the 7 windows (20-40 ... 300-600 Hz) for P1 / v1.5 / base / s2m0 / K 0.5 / oracle 0.5.
* Diagnostic rows b1, b2, b4: base with slower phase pull (existing params betaMin / betaMax = .05/.1, .1/.2, .1/.45) to test whether the 20-150 Hz skirt is phase noise.
* 14-song table (`a5_song14.py`, `song14_table.txt`): the B1 `b1_rank_lo.py` measure (2-12 Hz pulse excess of the 20-150 Hz layer dB envelope minus the input's, eligible windows), P1 and v1.5 from the B1 cache, base / s2m0 / s2m1 rendered here. No A5 row was chosen, so s2m0 and s2m1 (strongest limit) stand in.
