# Resultant core metrics: ii8a2

spec docs/RESULTANT_CORE.md v1.4 (4b8eb73); lib `/home/ksysh/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so` algo 15 resultant {'voicing': 0.0, 'ampSource': 0.0, 'capRho': 1.5, 'windowCreep': 8.0, 'creepMode': 2.0}; source commit unknown; ref lib /home/ksysh/r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so (f32bdfbfaa41)

| id | what | value | limit | P1 | pass |
|---|---|---|---|---|---|
| V1a | trace A / P1 tr.a (median dB) | -0.000993 | abs<= 0.5 | n/a | PASS |
| V1b | layer 150-600 Hz level re P1 (dB, voicing 0) | 0.00182 | abs<= 1 | n/a | PASS |
| V2.k2 | |dphi| layer vs original, 2x100 Hz (rad) | 0.000475 | abs<= 0.3 | -7.88e-05 | PASS |
| V2.k3 | |dphi| layer vs original, 3x100 Hz (rad) | -0.00238 | abs<= 0.3 | -0.000107 | PASS |
| V3a | 150-600 Hz cycle-mean peak (ms) | 41 | in [11, 31] | 21 | FAIL |
| V3b | 300 Hz layer/input range 40-440 ms (dB) | 1.55 | <= 4 | 40.2 | PASS |
| V3c.enter | stepwise 25 dB: f_osc within 2 % of new note, median (ms) | 35 | <= 30 | inf | FAIL |
| V3c.range | stepwise 25 dB: in-note ratio range 15-110 ms, median (dB) | 2.03 | <= 6 | 21.5 | PASS |
| V3c.lowbin | stepwise 25 dB: notes with a 20 ms bin > 6 dB under the note median | 0 | <= 0 | 35 | PASS |
| V3d | pre-echo rise [t0-30, t0] ms (dB, median) | 0.31 | <= 1 | -0.479 | PASS |
| V3h.bare.rise90 | bare 100 Hz note (from silence) 90 % rise (ms) | 29.7 | <= 25 | 39.8 | FAIL |
| V3h.bare.tail | bare note -20 dB tail (ms) | 4.92 | <= 40 | 0 | PASS |
| V3h.25.rise90 | line SNR 25 dB 90 % rise (ms) | 28.4 | <= 25 | 33.5 | FAIL |
| V3h.25.tail | line SNR 25 dB tail (ms) | 9.78 | <= 40 | 3.17 | PASS |
| V3h.6.rise90 | line SNR 6 dB 90 % rise (ms) | 50.4 | <= 70 | 40.1 | PASS |
| V3h.6.tail | line SNR 6 dB tail (ms) | 69.1 | <= 90 | 17.6 | PASS |
| V3e.df4.A | two tones 4 Hz apart: worst voice median |A error| (dB) | inf | <= 1.5 | inf | FAIL |
| V3e.df4.beat | two tones 4 Hz apart: layer beating depth - input depth (dB) | 2.17 | <= 3 | 39.1 | PASS |
| V3e.df10.A | two tones 10 Hz apart: worst voice median |A error| (dB) | inf | <= 1.5 | inf | FAIL |
| V3e.df10.beat | two tones 10 Hz apart: layer beating depth - input depth (dB) | 4.14 | <= 3 | 26.4 | FAIL |
| V3f | weak tail + 110 Hz attack: layer 90 % time (ms) | 34.4 | <= 25 | 26.8 | FAIL |
| V3g.35.on | 35 Hz note: ON within 2 hops of the track's first appearance (hops) | 10 | <= 2 | 0 | FAIL |
| V3g.35.noREL | 35 Hz note: hops without an ON voice after first ON | 12 | <= 0 | 0 | FAIL |
| V3g.45.on | 45 Hz note: ON within 2 hops of the track's first appearance (hops) | 10 | <= 2 | 13 | FAIL |
| V3g.45.noREL | 45 Hz note: hops without an ON voice after first ON | 1 | <= 0 | 0 | FAIL |
| V3i.trans | chatter tone on SNR 8 dB: ON/REL transitions per second | 0 | <= 1 | 7.31 | PASS |
| V3i.c | c < 0.5 for <= 10 % of the time (or continuously below) | 0 | <= 0.1 | 0.315 | PASS |
| V4a.bass+pink | bass+pink: std of per-note mean layer/input (dB) | 0.214 | <= 1.5 | 7.13 | PASS |
| V4b.bass+pink | bass+pink: bins > 6 dB under the note median | 0 | <= 0.02 | 0.329 | PASS |
| V4c.bass+pink | bass+pink: std of A after the known envelope (dB) | 0.571 | <= 1 | 0.412 | PASS |
| V4a.bass+kick+pink | bass+kick+pink: std of per-note mean layer/input (dB) | 0.599 | <= 1.5 | 4.78 | PASS |
| V4b.bass+kick+pink | bass+kick+pink: bins > 6 dB under the note median | 0.0393 | <= 0.02 | 0.314 | FAIL |
| V4c.bass+kick+pink | bass+kick+pink: std of A after the known envelope (dB) | 1.23 | <= 1 | 1.19 | FAIL |
| V5a | Track00060: bass-present 20 ms bins > 6 dB under the local median | 0.0885 | <= 0.05 | 0.182 | FAIL |
| V5b | Track00060: layer level re P1 where P1 has no gap (median dB) | 0.546 | abs<= 2 | n/a | PASS |
| V6a | pitch coverage (core - P1, percentage points) | 0.608 | >= 5 | 79.7 | FAIL |
| V6b | wrong-note energy share (core - P1, percentage points) | 11.2 | <= 2 | 17.8 | FAIL |
| V7a.T60 | T60: layer energy >1.5 kHz re 150-600 Hz at out_db -18 (dB) | -51.5 | <= -50 | -50.1 | PASS |
| V7a.LOGOFF | LOGOFF: layer energy >1.5 kHz re 150-600 Hz at out_db -18 (dB) | -58.7 | <= -45.2 | -46.2 | PASS |
| V7a.bass+kick+pink | bass+kick+pink: layer energy >1.5 kHz re 150-600 Hz at out_db -18 (dB) | -68.8 | <= -50 | -56.8 | PASS |
| V7b | phone-model roughness re P1: worst item (%) | 0.983 | <= 5 | n/a | PASS |
| V7c | phone-model low-band GR max re P1: worst item (dB) | 0.296 | <= 0.5 | n/a | PASS |
| V7d.4.12 | LOGOFF hit 4.12 s: layer 150-600 Hz energy re P1 (dB) | 13.1 | <= 1 | n/a | FAIL |
| V7d.4.73 | LOGOFF hit 4.73 s: layer 150-600 Hz energy re P1 (dB) | 51.5 | <= 1 | n/a | FAIL |
| V9e.pink_only | pink_only: sustained-path energy re P1 (dB) | -70.4 | <= 3 | n/a | PASS |
| V9b.pink_only | pink_only: births per second | 0 | <= 57.7 | 57.7 | PASS |
| V9e.music_silence_noise | music_silence_noise: sustained-path energy re P1 (dB) | 2.34 | <= 3 | n/a | PASS |
| V9b.music_silence_noise | music_silence_noise: births per second | 0.145 | <= 29.7 | 29.7 | PASS |

## Interpretations

- V1: A/tr.a is the median over hops with tc in 0.5-3.8 s of 20log10(A of the ON voice within 5 Hz of 100 Hz / tr.a of the same-run tracker track within 5 Hz of 100 Hz) and is compared with the P1 reference run by core index in make_checks. Layer level = 10log10(mean square of post_filter (stage column), band-passed 150-600 Hz, core indices 2100-10500)
- V2: layer = out(-120 dB) subtracted from out(0 dB) at out_db -18; "original" = the dry engine output (vb_level -120), so EQ/latency phase is shared; dphi_k = circular mean over 200 ms Hann frames (hop 100 ms, input time 0.7-3.5 s) of angle(layer_k * conj(dry_k)) at exactly k*100 Hz. Pass requires BOTH |dphi_2| and |dphi_3| <= 0.3 rad (stricter reading of "average")
- V3b: bins [40+20j, 60+20j) ms, j=0..19 (the last full 20 ms bin before 450 ms); 300 Hz band 285-315, Hilbert power cycle-averaged over notes 1..15 (research_r4l_timing_layer.py); input partial = dry engine output (vb_level -120); ratio floored at -100 dB
- V3d: layer power with a causal 10 ms boxcar; baseline line = least squares of its dB over [t0-150, t0-50] ms extrapolated to the centre of [t0-30, t0] ms; rise = dB of the mean power over [t0-30, t0] minus that line; reattacks 1.0..7.5 s (14); pass uses the median
- V3h bare: layer amplitude envelope = sqrt(5 ms boxcar of layer^2). The repeating decaying bare bass has no steady level and no silence before the attack, so its peak-referenced rise (max envelope in the first 150 ms of notes 1..14) is only REPORTED (v3h_bare.rise50_ms/rise90_ms); the PASS values come from a separate isolated flat 1 s 100 Hz note (tail_note, attack from silence): ref = mean envelope 1.2-1.45 s, rise = time from the attack (0.5 s) to 50/90 % of ref, tail = time after the note end (1.5 s) to fall to -20 dB (10 %) of ref
- V3c: f_osc entering time = first hop (analysis-centre time tc >= note start) at which the DOMINANT ON voice (largest (A*c*sigma)^2; core: state ON; P1: fade>=0.5 track, (a*fade)^2) is within +-2 % of the new note; inf (never within 125 ms) counts as a miss in the median. Variant (enter_ms_median_anyvoice): any ON voice within 2 %, ignoring voices that already matched on the last hop before the note start. In-note ratio at 3f of the note: layer vs the clean line through the dry engine path, 20 ms Hann projections centred at 25,45,65,85,100 ms (= the 20 ms bins tiling 15-110 ms, the last overlapping); range = max-min; "no bin > 6 dB below the note median" is counted per note; the range pass uses the median over notes
- V3h line: measured on the GATED stepwise line (125 ms note, 125 ms gap, same pink bed at in-band SNR 25 / 6 dB) because the back-to-back line has no tail and no rise from silence; ref = mean layer envelope 60-110 ms into the note; rise = time from the note start to 50/90 % of ref, tail = time from the note end to <= 10 % (-20 dB) of ref (cap 120 ms); medians over notes 2..39
- V3e: truth for a voice = median tr.a of the same-frequency tone alone (0.5 x V1 tone, same lib, tracker track within 3 Hz) over tc 1-3.8 s (the engine amplitude unit); a voice belongs to the nearer tone if within 3 %; error = median over hops of |20log10(A/truth)| with missing hops counted as infinite; beating depth = 10log10(P95/P5) of the 10 ms boxcar Hilbert power of the 150-600 Hz band over 1-3.8 s (layer vs the raw input); pass needs both pairs, both voices
- V3f: total layer amplitude envelope (5 ms) of the whole layer (the old 80 Hz note is ~18 dB weaker); 90 % time = first time after T_a=1.4 s at which it reaches 0.9 x its mean over 1.7-2.6 s. SNRs are set on the input with the engine's 5.4 definition (not the engine's own snr_db)
- V3g (v1.4): a voice "at the note" = tracker/oscillator frequency within 5 % of the fundamental; ON = core state ON (P1: fade>=0.5); the "2 hops" are counted from the first hop at which any voice/track at the note exists (tc difference / 5.33 ms; non-measured hops are not distinguished); the tc-onset reading is dropped (first_appearance_after_onset_ms is information); "never REL" = no hop with tc from the first ON to note end - 50 ms lacks an ON voice at the note
- V4: ratio = layer (noisy mix, out(0)-out(-120)) / the CLEAN bass partial at 300 Hz through the dry engine path; 20 ms Hann projections tiling 40-440 ms of notes 2..15, floored at -80 dB; std between the 14 per-note means uses ddof=1; V4c = std (pooled over notes, per-note mean removed) of 20log10(A) + 8.686*u/0.35 over 40-450 ms (A = ON voice within 5 Hz of 100 Hz; P1: tr.a)
- V5 (v1.3): bins = 20 ms from 39.00 s of Track00060 (rendered 36-48 s, 3 s warm-up); bass-present = MIDI bass note sounding at the bin centre (octave from the YIN agreement as research_resultant_pitch_truth.py) and the sum of the bass stems 40-220 Hz within 20 dB of its p95 over the whole song; ratio = layer 150-600 Hz energy / bass-stem-sum 150-600 Hz energy per bin; local = +-250 ms among present bins; (b) compares the layer energy per bin with P1 over bins where P1 is within 3 dB of its local max
- V6: hop time = analysis centre tc (no lag search); loud-bass hops = MIDI bass note sounding and bass stem 40-220 Hz within 10 dB of its p95 over the sounding hops, tc>0.5 s; "right" voice (core: ON, non-subordinate, c>0.5; P1: fade>=0.5) = frequency (f_osc / track f) within 50 cent of f0, 2f0 or 3f0 of the lowest sounding MIDI bass note (octave tp from YIN agreement; bass MIDI from the original train path). Wrong-note energy (v1.4): weight (A*c*sigma)^2 (P1 (a*fade)^2) over voices with weight>0 per hop with tc>0.5 s; "right" if within 50 cent of 0.5,1,2,3 x any note sounding at tc in ANY MIDI file of the track (drums included; the bass MIDI also octave-shifted by tp), from ~/datasets/slakh2100_midi/train. Variants reported: b = +-60 ms note tolerance, c = drum MIDI excluded, w23 = weights a_2^2+a_3^2. Primary = a
- V7a (v1.4): layer = out(0)-out(-120) with BOTH renders at out_db -18 (no limiter); energy above 1.5 kHz / 150-600 Hz energy, over input time 3-11 s of the 12 s renders (bass+kick+pink: 1-7 s); per item <= -50 dB, or <= P1 + 1 dB on an item where P1 itself is above -50 dB. (The out_db -5 values are kept as information in a_d; V7d still uses the -5 renders.) V7b/c: research_r4_roughness.py (phone model -1) ported unchanged, total roughness and the phone model gain reduction "low band max" (gr_low max); items = Slakh 30-40 s of Track00060/40/31/01 and every 12th MUSDB7 train excerpt (7 s), cold start; pass rule: each item and also reported as median. V7d: layer 150-600 Hz energy within +-50 ms of 4.12 s and 4.73 s of the 40-48 s LOGOFF excerpt
- V9: births = new tracks reaching fade>=0.5 (P1) / voices entering ON from empty or CAND (core) with tc in the scored window; energy = 10log10 mean square of the stage-capture column tonal_after_gain (sustained path only, v1.3) over the window mapped with core index n -> input time (16(n-398)+1359)/48000 s, floored at -140 dB; composite scored on input time 4-10.9 s; pink-only on 0.5-9.9 s
