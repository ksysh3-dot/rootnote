# Plan16 A5'' (RESULTANT_CORE.md 18.15): choices (written before any result)

## What changes (C++, uncommitted in ~/r3-work, build `tools/pvb-harness/build_core16d/`, base HEAD 93d9cfb = code of 5c1c62c)
* New params (spec order, 1-based 20, 21, 22 = array index 19, 20, 21; `kParams` 19 -> 22): `betaSusMin`, `betaSusMax`, `betaOnsetMs`. Defaults 0 / 0 / 0.
* Sustain pair on = `betaSusMin > 0 || betaSusMax > 0`. Then `betaOnsetMs` must be > 0 (library refuses 0), range of 20/21 is 0..1, of 22 is 0..1000. Sustain pair off: `betaOnsetMs` is ignored (accepted, any value 0..1000), behaviour = 5c1c62c.

## Which beta uses switch: BOTH
* In `ResultantCore::updatePhase` there is exactly one beta per voice and hop: `beta = clamp((snr - 10) / 20, lo, hi)` with `[lo, hi] = [betaMin, betaMax]`. It is used for (1) the theta pull `theta = pred + beta * e` and (2) the f_off gain `gamma = min(0.2, 0.5 / c_b) * beta` (v1.3 relation kept; the `snr < 12 -> gamma = 0` rule and the `ae < 0.2 -> f_off *= 0.98` leak are untouched).
* With the sustain pair on and the voice outside its onset period, `[lo, hi] = [min, max](betaSusMin, betaSusMax)` instead, so theta AND f_off both slow down together (gamma follows beta). Nothing else changes (psiSlew stays a separate existing parameter, set to .03 in the A5'' rows).
* The snr ramp `(snr - 10) / 20` is the same, only the clamp range moves.

## Onset period
* Per voice `onsetAt` (hop count). Set at: (a) birth CAND -> ON (same place as `onHop`), (b) REL -> ON (the 3-hop revive in `transitions`), (c) in `updatePhase` when the voice's `f_track` (`u.f`, the track frequency or the coasting extrapolation) differs by more than 50 cent from its value at the end of the previous hop (`fPrev`) or of the hop before (`fPrev2`) = "moved by > 50 cent within the last 2 hops". (c) re-arms the period at every hop in which the condition holds (a long fast move keeps the fast pair on).
* Fast (onset) pair = `betaMin / betaMax` (the .2/.9 of the row) while `(hopCount_ - onsetAt) * 16/3000 s * 1000 < betaOnsetMs`, i.e. the onset hop counts as time 0; the sustain pair afterwards. In the birth hop itself `updatePhase` takes the measured phase (born voices skip the pull), so at 30 ms (5.6 hops) the pull is fast on hops 1..5 after birth, at 60 ms 1..11, at 100 ms 1..18.
* `fPrev2` is a new Voice field (set with `fPrev` at spawn, shifted at the end of every hop). It is only read when the sustain pair is on.
* Cand/Empty voices have no pull; the check (c) is made for every other voice (ON, REL, Fade-state slots), whether or not it is in the LS set this hop (so a pitch move during a coast also re-arms the period).

## V0 (`v0_check16d.py`, `v0_check16d.log/.json`)
* A: 16d with 19/20/21/22 values (params 20-22 = 0, also with `betaOnsetMs = 60` and the sustain pair off), v1.5 and v1.6-a (1.5/16/2) settings, six signals (LOGOFF 37-49 s, Slakh TRAIN Track00060/00001/00020 excerpts, gated 25 dB pink line, low notes), blocks 256 / 1 / 480: output and 22-field trace bit-identical to build_core16b (5c1c62c).
* C: sustain pair = (.2, .9) with onset 30 / 100 ms is also bit-identical to off (the sustain branch is a no-op when the pairs are equal).
* D: a real pair (.05, .1, 60 ms) changes output and trace. Parameter checks: sustain on with onset 0 refused, values out of range / NaN refused, 23 values refused.

## Rows and measurement (same code as A5', `plan16/A5P/`, copied with paths/library changed; numbers comparable)
* Library for every row `build_core16d` (params 20-22 sent as 0 for non-A5'' rows; verified bit identical to 16b by V0 A). Rows: P1 (algo 6), v1.5, b0 = v1.6-a base (17:1.5 18:16 19:2, psiSlew .12), bb = A5' best (betaMin/Max .05/.1, psiSlew .03), A5'': psiSlew .03, sustain A = (.05, .1) or B = (.1, .2) x betaOnsetMs 30 / 60 / 100 = sA30 sA60 sA100 sB30 sB60 sB100.
* Primary: 7 user windows, 20-150 / 150-600 Hz layer ratio (`pp_primary.py`, `a5pp_table.py`). Guards (`decide_pp.py`): 18.9 list + V3c.enter <= +5 ms, V3e.df4 beat <= +1 dB, V3e 10 Hz beat <= +1 dB, f_osc median error (synthetic glide / vib30 / vib60, clean + 25 dB SNR) <= +10 cent, all vs the v1.6-a base b0. Suite batches of 4 rows. Decision = 18.15 mechanically (sum >= +3 dB, >= 5 of 7 windows, all guards; best ratio, 0.5 dB tie -> shorter betaOnsetMs).
* Report only: V6b, tail (all-band too), RERISE, LOGOFF 4.12 s, 14-song table (a5pp_song14.py), jumps > 6 dB.
* Slakh TRAIN only (V0 uses Track00001/00020/00060 of train, the 14-song set is the user's songs read in place; none copied). No downloads, no commits.
