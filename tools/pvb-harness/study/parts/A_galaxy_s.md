# Part A: Galaxy S series (S21-S26 lines)

Researcher A, 2026-10-23. Companion files: `A_galaxy_s.csv` (one row per model and source, raw values only)
and `anchor.md` (site-by-site comparison with our S26 Ultra measurement).

## Key findings

1. **No published third-octave curve could be read for any Galaxy S model.** NotebookCheck (pink-noise chart in
   every review) is cut by the fetch tool before the Speakers section; Bandicoot Lab and DXOMARK draw their
   curves with JavaScript. All of these are listed under "Charts to digitize" for the main session's browser.
2. **The only numeric frequency-response evidence is Bandicoot Lab's scalar "dB drop from the mids to the bass
   band"** (same rig for all models: UMIK-1, REW, sine sweep at 50 cm, 100 % volume, quiet room):

   | Model | Bass drop from mids (dB) | Difference vs S26 Ultra (dB) | Treble above mids (dB) | Loudness (dBA, 100 %) | THD |
   |---|---|---|---|---|---|
   | S26 Ultra | 18.4 | 0 | 8 | 75.3 | 3.3 % |
   | S26+ | 18.6 | +0.2 | n/a ("clear, moderately extended") | 71.7 | 3.85 % |
   | S26 | 20.1 | +1.7 | 7.2 | 72.5 | 3.44 % |
   | S25 Ultra | 21.8 | +3.4 | n/a ("clear, well-extended, flat") | 78.6 | 4.4 % |
   | S25+ | 26.4 | +8.0 | n/a ("moderately extended, uneven") | 77.2 | 4.54 % |
   | S25 Edge | 28.7 | +10.3 | n/a ("reasonably flat, uneven") | 76.3 | 5.2 % |
   | S25 | 29.0 | +10.6 | n/a ("clear, reasonably flat") | 76.7 | 5.7 % |

   (Incidental, outside part A: Bandicoot gives the iPhone 17 Pro Max 21 dB on the same metric.)
3. **S25 line (except the Ultra) has much less bass than the S26 line** in this metric: 8-11 dB more drop than the
   S26 Ultra. This agrees with the user report that S25+ bass is "barely there", and with Bandicoot's text
   ("loud but shallow"; S26+ has "fuller bass"). **S26, S26+ and S26 Ultra are within 1.7 dB of each other.**
4. Caveat on 3: Bandicoot measures at 100 % volume. The S25 phones are 4-5 dB louder at full volume than the S26
   phones while losing more bass, which looks like heavier bass limiting at full volume (S25 tuning) and/or
   different hardware. At normal listening volume the S25-vs-S26 gap may be smaller. Not separable from the data.
5. Older lines (qualitative, DXOMARK only, confidence C): the **base model is consistently the bass-weakest** in
   S23 and S24 ("quite bright, lacked some bass and low-midrange", "excessive treble boost"), while S23+/S23 Ultra/
   S24+/S24 Ultra are "good bass" / "all-in with bass power" with some upper-bass muddiness. S21 and S22 lines are
   "midrange-focused" with "lack of low-end extension" (S22 Ultra better low end than S22+).

## Sources used

| Source | What it measures / publishes | Conditions | Used for |
|---|---|---|---|
| Own measurement (anchor) | S26 Ultra third-octave curve | UMIK-1, 30 cm, volume 60/150, room, sweep, Atmos off | numbers (A) |
| Bandicoot Lab, https://bandicootlab.com/explainer/how-we-test-speakers-microphones and per-phone pages | Scalars in text: bass drop from mids (dB), treble above mids (some models), loudness dBA, THD. Curves drawn by JS ("Loading chart..."), API needs partner key. Band definitions NOT published. | UMIK-1 + REW, sine 20 Hz-20 kHz at 50 cm, 100 % volume, quiet room; loudness pink noise at 40 cm | scalars, model-to-model differences (B) |
| DXOMARK audio tests (S21-S24 lines) | Text verdicts + sub-scores; "Music playback frequency response" 1/12-octave, pure sine, anechoic, graph script-rendered | anechoic; distance/volume for the FR graph not stated | qualitative (C) |
| NotebookCheck reviews | Pink-noise frequency diagram + audio analysis box per review | not readable (truncated) | not used; charts listed below |
| Mobilissimo.ro (S26 Ultra acoustics) | loudness dBA only | not stated | not used (no FR) |
| SamMobile / PhoneArena news | subjective: S24 louder/fuller than S23; S25 Ultra fuller than S24 Ultra, slightly wider speaker cutout | listening | context only |
| GSMArena | not used (lowest priority; their speaker test is loudness only) | - | - |

DXOMARK note: scores from different protocol generations (S21/S22 vs S23/S24) are not directly comparable; S22 Ultra
was "retested in the latest version of our protocol". DXOMARK says within each of the S21, S22, S23, S24 series that
"all models ... are equipped with the same audio specs", yet its own base-model results differ (S23/S24 base: less
bass). "Same audio specs" therefore means spec sheet (stereo, Dolby Atmos), not identical acoustics.

## Calibrations

None performed: no chart could be viewed as an image or read as data with the tools available (WebFetch only;
shell has no web access; a reader-proxy fetch of NotebookCheck was declined by the permission system and not worked
around). Every chart is listed below for digitizing with the user's procedure (axis calibration first, cross-chart
consistency check, then third-octave sampling re 1 kHz).

## Per-model table

Level re 1 kHz (dB) only where a source gives it. "-10 dB" = frequency where the response is 10 dB below 1 kHz.
Treble tilt = mean of 2-5 kHz third-octaves re 1 kHz.

| Model | 125 | 160 | 200 | 250 | 315 | 400 | 500 | -10 dB | Treble tilt 2-5k | Evidence | Conf. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S26 Ultra | -20.2 | -14.0 | -8.9 | -4.9 | -6.0 | -5.6 | -4.7 | ~191 Hz (my interpolation) | +10.7 | own measurement; Bandicoot 18.4 dB / +8 dB | A |
| S26+ | - | - | - | - | - | - | - | - | - | Bandicoot 18.6 dB | B (scalar) |
| S26 | - | - | - | - | - | - | - | - | - | Bandicoot 20.1 dB, treble +7.2 dB | B (scalar) |
| S26 FE | - | - | - | - | - | - | - | - | - | none found (search budget ran out) | - |
| S25 Ultra | - | - | - | - | - | - | - | - | - | Bandicoot 21.8 dB | B (scalar) |
| S25+ | - | - | - | - | - | - | - | - | - | Bandicoot 26.4 dB; user report weak bass | B (scalar) |
| S25 | - | - | - | - | - | - | - | - | - | Bandicoot 29.0 dB | B (scalar) |
| S25 Edge | - | - | - | - | - | - | - | - | - | Bandicoot 28.7 dB | B (scalar) |
| S25 FE | - | - | - | - | - | - | - | - | - | none readable (NotebookCheck chart only) | - |
| S24 Ultra | - | - | - | - | - | - | - | - | - | DXOMARK: strong bass, upper-bass muddy | C |
| S24+ | - | - | - | - | - | - | - | - | - | DXOMARK: good bass | C |
| S24 | - | - | - | - | - | - | - | - | - | DXOMARK: bright, lacks bass/low-mids | C |
| S24 FE | - | - | - | - | - | - | - | - | - | none readable (NotebookCheck chart only) | - |
| S23 Ultra | - | - | - | - | - | - | - | - | - | DXOMARK: strong bass, upper-bass muddy | C |
| S23+ | - | - | - | - | - | - | - | - | - | DXOMARK: good bass, could be stronger | C |
| S23 | - | - | - | - | - | - | - | - | - | DXOMARK: bright, lacks bass/low-mids | C |
| S23 FE | - | - | - | - | - | - | - | - | - | DXOMARK: upper-bass presence, lacks low/high extension | C |
| S22 Ultra | - | - | - | - | - | - | - | - | - | DXOMARK: strong lack of low-end extension | C |
| S22+ | - | - | - | - | - | - | - | - | - | DXOMARK: midrange-focused, less low end than Ultra | C |
| S22 | - | - | - | - | - | - | - | - | - | DXOMARK: midrange-focused | C |
| S21 Ultra | - | - | - | - | - | - | - | - | - | DXOMARK: midrange-focused, poor bass | C |
| S21 / S21+ | - | - | - | - | - | - | - | - | - | DXOMARK: S21 identical results to S21 Ultra; S21+ series statement only | C |
| S21 FE | - | - | - | - | - | - | - | - | - | DXOMARK: lacks low- and high-end extension | C |

## Groupings (only where the data supports it)

- **S26, S26+, S26 Ultra**: Bandicoot bass drop 18.4-20.1 dB, treble +7.2/+8 dB where given. Supports treating
  them as one bass family to within about 2 dB at 100 % volume. Nothing says the drivers are identical.
- **S25, S25+, S25 Edge**: 26.4-29.0 dB, a weak-bass group. S25 Ultra (21.8) sits between them and the S26 line.
- **S23+ / S23 Ultra / S24+ / S24 Ultra**: DXOMARK timbre 135 for all four; the S24 Ultra text nearly copies the
  S23 Ultra text. Qualitative grouping only (C).
- **S23 / S24 base**: DXOMARK timbre 126, identical "bright, lacked some bass and low-midrange" wording. (C)
- **S21 / S21 Ultra**: DXOMARK states identical results. (C)

## Inferred implications for starting settings (INFERENCE, not source data)

Labelled inference from the Bandicoot differences applied to our S26 Ultra curve. Assumption: the extra bass
drop is a frequency shift of the S26 Ultra's low-end slope (about 15 dB/octave between 125 and 250 Hz). Under that
assumption the -10 dB point would move from ~191 Hz to roughly: S26+ ~190, S26 ~205, S25 Ultra ~220,
S25+ ~260-300, S25 / S25 Edge ~285-350 Hz (range from assuming 12-18 dB/octave). Confidence C: the bass band
behind Bandicoot's number is unknown, and it is measured at 100 % volume.

- S26 / S26+: the S26 Ultra profile is a reasonable start (bass and treble scalars match within ~2 dB).
- S25 Ultra: S26 Ultra profile with a slightly higher speaker floor (order of 170-200 Hz) is plausible.
- S25 / S25+ / S25 Edge: the speaker floor is probably well above 150 Hz (order 200-250 Hz); a +3 dB low-mid
  boost at 220 Hz would mostly feed the dynamics processor, so virtual bass matters more than EQ for these.
  Verify with the NotebookCheck S25+ chart before shipping any value.
- S23 / S24 base: DXOMARK's "excessive treble boost" supports keeping a treble cut like the S26 Ultra's -3 dB.

## Charts to digitize (main session, real browser)

All are JavaScript charts, not images; read them in a browser (screenshot, or the chart's data table on hover).
Priority order: S26 Ultra (anchor) first, then S25+, S25, S26, S25 Ultra.

NotebookCheck pink-noise frequency diagrams (Speakers section near the end of each review):
1. S26 Ultra: https://www.notebookcheck.net/Blocks-prying-eyes-Samsung-Galaxy-S26-Ultra-review.1278349.0.html
2. S25+: https://www.notebookcheck.net/Samsung-Galaxy-S25-review-Still-one-of-the-best-Android-smartphones-despite-an-innovation-standstill.978765.0.html (German: https://www.notebookcheck.com/Test-Samsung-Galaxy-S25-Trotz-Innovationsstau-immer-noch-eines-der-besten-Android-Smartphones.966648.0.html)
3. S25: https://www.notebookcheck.net/Samsung-Galaxy-S25-review-The-star-among-compact-smartphones-is-losing-ground.989246.0.html
4. S26: https://www.notebookcheck.net/Exynos-and-more-battery-power-make-it-a-star-Samsung-Galaxy-S26-review.1284566.0.html
5. S25 Ultra: https://www.notebookcheck.net/Samsung-Galaxy-S25-Ultra-review-The-AI-phone-relies-fully-on-artificial-intelligence-and-small-hardware-upgrades.968346.0.html
6. S25 Edge: https://www.notebookcheck.net/A-5-8-millimeter-thin-endurance-marvel-Samsung-Galaxy-S25-Edge-smartphone-review.1042425.0.html
7. S25 FE: https://www.notebookcheck.net/The-most-affordable-Galaxy-S25-has-cut-corners-in-the-wrong-area-Samsung-Galaxy-S25-FE-smartphone-review.1136160.0.html
8. S24 Ultra: https://www.notebookcheck.net/Samsung-Galaxy-S24-Ultra-review-The-ultimate-smartphone-becomes-an-AI-smartphone.809187.0.html
9. S24+: https://www.notebookcheck.net/Samsung-Galaxy-S24-smartphone-review-The-big-Galaxy-S24-inches-closer-to-the-S24-Ultra.811860.0.html
10. S24: https://www.notebookcheck.net/Samsung-Galaxy-S24-review-The-best-small-Android-smartphone-gets-cheaper-but-not-better.809474.0.html
11. S24 FE: https://www.notebookcheck.net/Samsung-Galaxy-S24-FE-review-Fans-have-redefined-the-Galaxy-smartphone.915112.0.html
12. S23 Ultra: https://www.notebookcheck.net/Samsung-Galaxy-S23-Ultra-review-The-smartphone-with-galactic-power-and-a-200-MP-camera.698336.0.html
13. S21 FE: https://www.notebookcheck.net/Samsung-Galaxy-S21-FE-5G-review-The-fan-edition-smartphone-goes-into-the-next-round.598090.0.html

Bandicoot Lab frequency-response charts (same rig for all; also the best anchor candidate because it is a UMIK-1
room measurement like ours, at 50 cm and 100 % volume):
14. S26 Ultra: https://bandicootlab.com/phone/samsung-galaxy-s26-ultra
15. S26+: https://bandicootlab.com/phone/samsung-galaxy-s26-plus
16. S26: https://bandicootlab.com/phone/samsung-galaxy-s26
17. S25 Ultra: https://bandicootlab.com/phone/samsung-galaxy-s25-ultra
18. S25+: https://bandicootlab.com/phone/samsung-galaxy-s25-plus
19. S25: https://bandicootlab.com/phone/samsung-galaxy-s25
20. S25 Edge: https://bandicootlab.com/phone/samsung-galaxy-s25-edge
(Comparison guides with overlaid charts: https://bandicootlab.com/guide/samsung-galaxy-s26-series-vs-galaxy-s25-series , https://bandicootlab.com/guide/samsung-galaxy-s26-plus-vs-galaxy-s25-plus)

DXOMARK "Music playback frequency response" graphs (1/12 octave, anechoic sine):
21. S24 Ultra: https://www.dxomark.com/samsung-galaxy-s24-ultra-audio-test/
22. S24+: https://www.dxomark.com/samsung-galaxy-s24-audio-test/
23. S24: https://www.dxomark.com/samsung-galaxy-s24-audio-test-2/
24. S23 Ultra: https://www.dxomark.com/samsung-galaxy-s23-ultra-audio-test/
25. S23+: https://www.dxomark.com/samsung-galaxy-s23-audio-test-2/
26. S23: https://www.dxomark.com/samsung-galaxy-s23-audio-test/
27. S23 FE: https://www.dxomark.com/samsung-galaxy-s23-fe-audio-test/
28. S22 Ultra: https://www.dxomark.com/samsung-galaxy-s22-ultra-exynos-audio-test-retested/
29. S22+: https://www.dxomark.com/samsung-galaxy-s22-plus-exynos-audio-test-2/
30. S22: https://www.dxomark.com/samsung-galaxy-s22-snapdragon-audio-test/
31. S21 Ultra: https://www.dxomark.com/samsung-galaxy-s21-ultra-5g-exynos-audio-review-excellent-on-artifacts/
32. S21: https://www.dxomark.com/samsung-galaxy-s21-5g-exynos-audio-review/
33. S21 FE: https://www.dxomark.com/samsung-galaxy-s21-fe-5g-audio-review/

## Open gaps

- No per-band numbers for any model except our S26 Ultra; everything else waits on the charts above.
- Bandicoot's band definitions (bass band, mids) are unpublished; scalars cannot be placed on a frequency axis.
- NotebookCheck review URLs not found for S26+, S23, S23+, S23 FE, S22 line, S21/S21+/S21 Ultra (the shared web
  search budget ran out). S26 FE status unknown for the same reason.
- No S24 FE or S25 FE evidence beyond the unread NotebookCheck charts; GSMArena not consulted for them.
- No teardown or paper found explaining driver/enclosure differences between models.
