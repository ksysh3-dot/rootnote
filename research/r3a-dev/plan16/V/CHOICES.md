# Plan16 V: reading choices for the "silence" wrong-energy split, fixed BEFORE any V number was computed

Spec: docs/RESULTANT_CORE.md 16.9, 16.8.1 B1/B2; brief_v.md.  Slakh TRAIN only (no validation/test path touched).  Offline; no engine code edited.
Base: plan16/D `dcommon` (SATruth stem-aware wrong `sa`, `annotate` B2 classes, `render_multi`, same layer = core v1.5, lag = LAGS['core'], F gain, k<=8 synthesis, kOutSos, t>0.5 s, 10 V6 songs 0-30 s).
Unit = wrong energy / R3 right energy (59.3507 pooled). Silence wrong energy = samples with sa-wrong = True of voices whose B2 class is silence (occupancy winner -1; for songs without bass MIDI that is every voice).
Samples are the 3 kHz render samples at input time tt (voice time axis after the lag shift = MIDI time axis); f = the voice f interpolated at tt, a = its amplitude.

## Data available (checked)
* Every Slakh train dir has ONLY the bass stem on disk (stems/ holds one file). Non-bass stems do not exist -> the stem clause of test 4 ("non-bass stem has 40-300 Hz within 10 dB of its p95") CANNOT be evaluated. Test 4 uses the MIDI clause only. Reported as a limitation; no substitute (the mix is not a stem).
* All-instrument MIDI (non-drum notes, drum hits, bass notes) is read through `common16.ref` (rf): bass notes ss/es/ps(+tp), non-drum notes nd_*, drum onsets drum_on (every drum pitch).

## Tests (first match wins, in this order; applied per sample)
1. NO-BASS SONG: the song has no bass MIDI note in the excerpt (= `segments` empty; Track00023, 24, 26). All its silence wrong energy -> cause 1.
2. DRUM: let delta = tt - d for a drum hit d (any drum pitch). Sample qualifies iff exists hit d with delta in [-20, +150] ms AND the voice is "hit-linked" to d: (a) the voice's birth time (first hop with amp > 0) lies in [d, d+60 ms], or (b) the voice amplitude rises by more than 6 dB inside 60 ms after the hit: max of a over (d, d+60 ms] > 2 x a(d) with a(d) > 0 (a(d) = 0 with the voice alive later in the window counts as an onset). Time axis: shifted voice time (as rendered).
3. BASS-REVERB/LATE: exists a bass note n (all bass MIDI notes, pitch + tp) with end e_n <= tt < e_n + 400 ms, voice f within 50 cent of 0.5/1/2/3 x f_n, and the bass stem (sum, 40-220 Hz, 10 ms boxcar RMS envelope as in `act15`, 3 kHz grid) satisfies: env(tt) < P_n - 15 dB (P_n = max env inside [s_n, e_n]), env(tt) >= P_n - 50 dB ("still there"), and env(tt) <= env(tt - 30 ms) ("decaying"). Info only (not an energy cause): pitch-matched within 400 ms after a note end but failing the stem condition.
4. OTHER-INSTRUMENT (MIDI clause only): a non-bass, non-drum MIDI note sounds at tt (nd_s <= tt < nd_e, bass notes removed by exact (s,e,p) match; raw MIDI pitch, no tp) and, for f0 = its frequency, some k in {1,2,3} and g in {f0, 2 f0} has |cents(f/k, g)| <= 100. (Stem clause unavailable, see above.)
5. OTHER: the rest.

## Also reported
* Per song: share of silence-voice lifetime (span of amp > 0) with no bass MIDI note sounding (median over silence voices carrying silence wrong energy).
* Energy-weighted deciles of the voice f over silence wrong samples (weight a^2 = energy proxy), pooled; and the number of distinct voices (runs) carrying 80 % of the silence wrong energy (proxy: sum a^2 over silence wrong samples per voice), plus total silence voices and the proxy share per cause.
* Cause totals come from layers rendered per cause (exact energy; cross terms mean the five causes need not sum to the rendered silence total exactly; reported next to B2's 0.2121). Pooled all 10, pooled without the 3 no-bass songs (denominator R3R unchanged: it already excludes them), and without Track00040.
