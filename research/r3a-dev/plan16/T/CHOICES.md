# Plan16 T: readings for the 16.14 attribution, fixed BEFORE any T number was computed

Spec: docs/RESULTANT_CORE.md 16.14 (+16.9 for the silent-voice definition / V6b, 16.13.2 hint).  Slakh TRAIN only (no validation/test path touched).  Offline; no engine/doc/other-folder edits.
Songs: Track00026 (primary), Track00024 (comparison).  Base = plan16/D `dcommon` + plan16/V `v_run.one_song` logic (core v1.5 voices, LAG = -0.012 s, SATruth stem-aware wrong `sa`, F gain, k<=8 synthesis, t > 0.5 s, 0-30 s excerpt).
Unit = wrong energy / R3 right energy (pooled R3R = 59.3507, same as V).

## Facts found while reading (orientation, before any attribution number)
* "No-bass song" in 16.9/V means: no bass-instrument MIDI note starts inside the 0-30 s excerpt (`segments` empty).  The bass STEM exists (T26: S07 Electric Bass (pick), first note 80 s; T24: S02/S07/S08, first note 36 s).  So "베이스 없는 곡" = "베이스가 아직 안 들어온 구간".
* Full train stems exist under /mnt/d/rootnote-data/slakh2100/extracted/slakh2100_flac_redux/train/TrackXXXXX/stems (the ~/datasets copy holds only the bass stem).  Criterion (c) therefore uses the REAL stems, not MIDI only.  Stems with audio_rendered:false are absent (T26 S00, T24 S09; both have no MIDI either).
* V6b "right" = voice f within 50 cent of 0.5/1/2/3 x ANY MIDI note sounding at the hop (all instruments, drum note numbers read as pitches, bass +tp).  Hence a silent voice that is `wrong` under V6b can NOT satisfy (a) k=1, or (b) k=2,3,0.5 against a non-drum note by construction; only k>=4 (and non-V6b ratios) can.  This is the expected "mismatch with 16.9"; it is reported by k.

## Time and hop alignment
* Hop grid = the truth grid of D: hop h <-> time t_h = tc[h] (sig.tc1) = MIDI/input time.  Voice samples at layer time tt map to h = rint((tt - LAG - tc0)/HOP_S) (exactly the D `comp_fn_factory` / V `fn` rule); the voice f of the hop = np.interp(tc[h], v['t'], v['f']) of the lag-shifted voice (same expression as D, reused so the silent-wrong set is bit-identical to V).
* Classification is made once per (voice, hop) at t_h and f_h, and applied to all render samples of that hop.  LAG enters only through the D rule above (12 ms; no extra shift for MIDI/stems/mix).
* "A note sounds" at hop h iff s_n <= t_h < e_n (MIDI start/end, no slack) = the V6b rule.  Note frequency f0 = 440 * 2^((p-69)/12), raw MIDI pitch, no tp (tp is a bass-only octave fix; the other stems are labelled raw in V6b).

## Tolerances and rule order (first match wins, per voice-hop)
Drum stems (is_drum) are excluded from (a)-(c) (a drum note number is not a frequency); they are kept in the diagnostics.  All tolerances +-50 cent (V6b).
* (a) some non-drum stem has a sounding note with |cents(f_h, f0)| <= 50.
* (b) some non-drum stem has a sounding note with |cents(f_h, m f0)| <= 50 for m in {2,3,4,5,6,7,8, 1/2}.  The reported k is the first m in that order that matches; the k-coverage table (non-exclusive) lists every m separately, plus informational 1/3, 1/4 (NOT part of the rule).
* (c) tail: exists a non-drum stem note n that ended 0 < t_h - e_n <= 1.0 s, with f_h within 50 cent of m f0_n for m in {1,2..8,1/2} (same set as a/b), and the STEM audio of that instrument has, near the voice f, a level at t_h that is >= (its own peak level near f during [s_n, e_n]) - 30 dB.  "Near f" = max of the STFT magnitude over bins within f +-50 cent (see below).  Pitch relation to the ended note is required (otherwise any stem noise would count as a tail).  Weakness (reported): a centred 256 ms window overlaps the last ~128 ms of the sounding note, so the first ~130 ms after a note end are biased towards "tail present".
* (d) no (a)-(c): the mix STFT frame nearest t_h has a local maximum inside f +-50 cent that is >= 6 dB above the median of the spectrum in [f - W, f + W] (W = max(30 Hz, 0.5 f), excluding +-10 Hz around the peak = Hann main lobe).  Secondary diagnostic (NOT used by the rule): engine-recipe `src_peaks` (q4: 384-sample Hann, FFT 2048, local max >= 10 dB over the +-27-bin median, band 20-200 Hz / -50 dB) run on my own 3 kHz decimation of the mix at the same frame, peak within max(4 Hz, 3 %).  (q4.py cannot be imported: it executes the whole experiment at import, so the function text is copied into t_run.py unchanged.)
* (e) everything else.
Spectral analysis: stems and mix are mono-mixed, resampled to 3 kHz with `resample_poly` (44.1 kHz -> up 10 / down 147), STFT = periodic Hann N = 768 (256 ms), hop 30 samples (10 ms), frame m centred at t = 0.01 m, FFT 4096 (0.73 Hz bins), bins <= 1 kHz kept, level = 20 log10 |X|.  The frame used for a hop is round(t_h / 0.01).

## How energy is attributed (the "share")
* Exact path: the silent-wrong render samples (sa-wrong, silence-class voices; for these two songs every voice) are rendered exactly like `D.render_multi` (same gains, k<=8, OUT_SOS) into one layer per (category, instrument) with the sample's amplitude x split EQUALLY over the matching stems (weights sum to 1, so the sum of layers == the V `E_sil` layer exactly before cross terms).  Share = layer energy / sum of the category layer energies (cross terms between layers make the sum differ from E_sil by a few %; both are printed).  The rule uses this share.
* Proxy path: per (voice, hop) weight = sum of a^2 over the hop's render samples; used for the k-coverage table, the sensitivity variants and for cross-checks (the proxy ignores filter and harmonic gains).
* Instrument = metadata `inst_class` and `midi_program_name` of the stem(s).  For (d)/(e) there is no MIDI instrument, so a diagnostic "dominant stem at f" (argmax of stem level near f, drums included) is reported instead; it does not change the category.
* Extra diagnostics (not in the rule): fraction of each category within [-150, +20] ms of a drum hit; voice-f deciles per category.

## Decision rule (verbatim, applied mechanically to Track00026 first; T24 and pooled shown for context)
(a)+(b)+(c) >= 60 % -> metric-definition problem; (e)+(d) >= 50 % -> engine defect; neither -> mixed.
Sensitivity variants (reported, never override the base): note window widened +-60 ms; (c) window 0.5 s / 2 s; (c) reference = peak at the note's own f0 instead of at f; (d) threshold 3 / 10 dB; STFT N = 1536.

## POST-RESULT ADDITIONS (2026-10-31, added AFTER the first (a)-(e) table was seen; everything above this line was written before any T number)
The (a)-(e) rule, tolerances (+-50 cent), the pitch tie and the -30 dB reference (peak near f during the note) of (c), the (d) +6 dB test, the hop alignment, and the energy attribution were NOT changed after seeing results.  The pre-announced sensitivity variants (slack, tail window, (c) reference, (d) threshold, N = 1536) were NOT run: the base shares (a+b+c) 5.9 % / (d)+(e) 94.1 % (T26) are far from 60 / 50 %.
Added after the first table (diagnostics only, they never feed the category or the rule):
1. `mix_nearest` (cents from f to the nearest mix local maximum, >= 6 dB over the median, +-300 cent search) and its signed version (`t_variant.py`).
2. Chance baselines: the same measures with f shifted +-0.25 octave (c2t null, mix-peak null, octave-folded null).
3. `snd_f0` (sounding non-drum note f0 per hop) and the octave-folded distance from f to the nearest sounding note class.
4. Stable-voice flags per hop (`gcommon.stable_scan`, D_s = 100 / 150 ms) and the stable / unstable split (this was requested at planning time but is not in the pre-registered text).
5. Variant "(c) without the pitch tie" (`t_variant.py`), asked for by the reviewer.  Result: T26 (c) would be 95.5 %, T24 14.7 %, BUT a control with f shifted +-0.25 octave on the same hops gives +88.3 / +90.6 pp (T26) and +15.1 / +13.9 pp (T24): the tie-free test passes on shifted frequencies as often as on the real one, i.e. it does not discriminate.  The base verdict is kept; whether the spec means a pitch tie in (c) is a spec-reading question for Opus.
