# Part B: Galaxy Z Fold / Z Flip, A series, M series (Tab low priority)

Status: DONE for this pass (2026-10-23). No third-octave curve could be read for any part-B model; what exists is
one measured scalar per model from Bandicoot Lab (Z Fold7, Z Flip7), qualitative DXOMARK / NotebookCheck text, and
a list of charts and pages for the main session to read with a browser. The shared web-search budget ran out
near the end, so Galaxy Tab and the M series were not searched further.

All values are RAW as the source shows them, re 1 kHz where numeric. No anchor offset is applied here.

## Access log (what could and could not be read)

- NotebookCheck review pages (.net): WebFetch converts only the first ~50-90k characters of a review.
  The "Speakers" / audio-analysis block sits after the Performance section and is cut off on every
  review tried so far (Galaxy Z Fold6: text ends at 90,520 chars inside the PCMark table; Galaxy A55:
  ends inside the BaseMark table). The shell has no web access (proxy 403).
- A third-party reader proxy (r.jina.ai) to get past the truncation was declined by the permission
  system. Not retried, no other workaround attempted.
- DXOMARK audio pages: the 1/12-octave frequency-response chart is drawn by JavaScript; WebFetch sees the
  caption only (no image URL, no numbers). Text statements (timbre, bass, treble) are readable.
- NotebookCheck German, Spanish and Chinese editions (Z Flip8 .com, A55 .org, Z Flip3 -cn): same cut, inside the
  benchmark tables. Researchers C and D report the same cut (~90-93k chars) on their brands.
- NotebookCheck NEWS articles are short and are read in full, but show the pink-noise chart only as a raster
  image (or not at all) and give no per-frequency numbers.

## Evidence log (filled as read)

### NotebookCheck news / comparison articles (qualitative, plus chart images)

- "Samsung is miles ahead of Motorola..." (Galaxy Z Flip8 vs Razr 70 Plus / 70 Ultra), notebookcheck.net,
  https://www.notebookcheck.net/Samsung-is-miles-ahead-of-Motorola-smartphones-Galaxy-Z-Flip8-is-best-choice-for-audio-fans.1397676.0.html
  States: pink-noise measurement; Flip8 max "nearly 92 dB(A)", Razrs below 84 dB(A); Flip8 "significantly more
  linear" across the audible range, "some bass response", treble "much more linear" than the Razrs, which
  "roll off very early". No per-frequency numbers. Chart image (raster): see "Images to digitize" #1.
  Links the full Flip8 review (German):
  https://www.notebookcheck.com/Superleichtes-Smartphone-Kraftpaket-mit-6-9-Zoll-OLED-Screen-Test-Samsung-Galaxy-Z-Flip-8.1373784.0.html
- "What is the key drawback of the Galaxy Z Fold8 compared to the Ultra smartphone for audio enthusiasts"
  (M. Herbrich, 2026-09-13),
  https://notebookcheck.net/What-is-the-key-drawback-of-the-Galaxy-Z-Fold8-compared-to-the-Ultra-smartphone-for-audio-enthusiasts.1390197.0.html
  States: Galaxy Z Fold8 Ultra frequency response "very linear" with "a noticeable amount of bass", max
  "over 87 dB(A)"; "Even the Galaxy S26 Ultra performs slightly worse in our pink-noise test than the premium
  foldable"; "The standard Fold even exhibits a slightly smaller dip in the ultrahigh frequencies."
  Standard Fold8: audible left-biased stereo image in landscape. No chart image in the fetched text,
  no numbers. Full review: https://www.notebookcheck.net/The-thinnest-Samsung-smartphone-ever-takes-on-the-iPhone-Ultra-Galaxy-Z-Fold-8-Ultra-Review.1390192.0.html
  Relevance: the only source found that compares a part-B phone directly with our anchor model (S26 Ultra)
  under one method. Inference (mine, not stated): Fold8 Ultra is at least as linear as the S26 Ultra in the
  NotebookCheck pink-noise test, so an S26U-like starting point is not too bass-heavy for it.

### DXOMARK audio (qualitative text + playback sub-scores; curve not readable)

Method as DXOMARK states it: "A 1/12 octave frequency response graph, which measures the volume of each
frequency emitted by the smartphone" with a pure sine "in an anechoic environment"; listening clips at
60 LAeq, two mics A-B at 30 cm. Volume/distance for the graph itself are not stated in the page text.
The graph is JS-rendered: no image URL and no numbers reach WebFetch (see "Images to digitize").
Sub-scores are DXOMARK's current-protocol numbers from the summary box (older pages also show a
different, older-scale set in the detail sections; those are noted only where they are the only set).
DXOMARK did not publish audio tests for Z Fold6 / Z Flip6 or later (searches find only display/camera tests).

| Model | Date | Playback / Timbre | What DXOMARK says about bass / mids / treble (verbatim fragments) | URL |
|---|---|---|---|---|
| Z Fold2 5G | 2021-04-28 | summary 111 / 104 (detail-section, older scale: Timbre 61) | "timbre clearly lacks upper content; as a result, the tonal balance is very muffled"; "misses low-end extension, and the minimal bass feeling is provided only by low-mids"; "muffled in all tested volumes" | https://www.dxomark.com/?p=76740 |
| Z Fold3 5G | 2021-11-10 | 121 / 122 (summary) | "good treble, natural midrange and a correct amount of bass"; "slight lack of both high and low-end extension and of low-mids warmth"; "aggressive high-mids" at max volume | https://www.dxomark.com/?p=97776 |
| Z Fold4 | 2022-10-19 | 134 / 130 | "sonority that is similar to more conventional Galaxy phones, such as the S22 Ultra"; "satisfying treble rendition, solid midrange, and decent bass"; "some more depth in low-end extension would not hurt" | https://www.dxomark.com/samsung-galaxy-z-fold4-audio-test |
| Z Fold5 | 2023-09-19 | 132 / 129 | tonal balance like Z Fold4, "satisfying treble rendition", "solid midrange and bass" | https://www.dxomark.com/samsung-galaxy-z-fold5-audio-test |
| Z Flip4 | 2022-10-17 | 128 / 120 | "similar to other Galaxy phones, such as the A52 or S22 Ultra"; "midrange is less consistent ... slightly thinner tonal balance"; "lack of low-midrange support" | https://www.dxomark.com/samsung-galaxy-z-flip4-audio-test |
| Z Flip5 | 2023-09-19 | 128 / 121 | "emphasized midrange"; "Treble was slightly thin but clear, while bass was decent but lacked low-end extension"; con "Lack of low-end extension" | https://dxomark.com/?p=156083 |
| A52 5G | 2021-06-09 | 127 / 120 | "lack of bass and low-end extension"; "consistent and full midrange", "slight lack of low mid"; treble "respectable"; low end weaker still at soft/max volume | https://www.dxomark.com/samsung-galaxy-a52-5g-audio-review-new-top-score-for-artifacts |
| A52s 5G | 2021-11-17 | 127 / 120 | sub-scores and pros/cons identical to A52 5G ("Lack of bass and low end ...") | https://www.dxomark.com/samsung-galaxy-a52s-5g-audio-review/ |
| A33 5G | 2022-05-12 | 125 / 128 | "Bass performance is surprisingly solid"; "Treble sounds clear and quite brilliant"; con "Lacks sufficient bass"; slight bass loss at soft volume; treble "piercing" at max | https://www.dxomark.com/samsung-galaxy-a33-5g-audio-test |
| A53 5G | 2022-05-20 | 128 / 128 | "consistent midrange and satisfying bass"; "lower treble ... sometimes sounds slightly harsh or resonant"; con "Limited bass"; tonal balance kept "regardless of volume level" | https://www.dxomark.com/samsung-galaxy-a53-5g-audio-test/ |
| A54 5G | 2023-03-20 | 132 / 129 | "richer and bulkier tonal balance than the predecessors"; "Bass was pleasantly warm but lacked some depth in the low-end"; treble "slightly lacked high-end extension"; cons "Performance too volume-dependent", "Tinny resonance and harshness" | https://www.dxomark.com/samsung-galaxy-a54-5g-audio-test |

Reading of this table (inference, not stated by DXOMARK): every Z/A model tested is described as lacking
low-end extension to some degree, none as bass-heavy; Z Fold4 and Z Flip4 are explicitly likened to the
S22 Ultra sound. Z Fold2 is the outlier (muffled, little treble). DXOMARK's own reference here is a
Samsung S-series phone, not our S26 Ultra, so these statements cannot be turned into dB.

### Bandicoot Lab (bandicootlab.com) - measured, summary numbers only

Method: glossary says "Our speaker tests measure SPL at a fixed 50-centimeter distance from the device";
Bass band = 60-250 Hz, Treble = 2-10 kHz, "f10 Low Cutoff" = "the frequency at which a speaker's output drops
10dB below its midrange level on the low end". Mid band limits are not defined anywhere public. Per
researcher C's notes (not re-checked by me): UMIK-1 with calibration file, REW, 20 Hz-20 kHz sweep, phone
at 100 % volume, quiet room. The curve itself and the f10 value are only in the JS Chart Builder / key-only
API (not worked around). The Methodology page gives only the score weight (speaker = 7.5 %).
Page texts look template-generated and are sometimes inconsistent (see Fold8 Ultra); treat wording as weak,
the dB/dBA/% figures as measured.

| Model | Speaker score | Bass: "drop from the mids to the bass band" | Treble statement | Max loudness | THD | Date | URL |
|---|---|---|---|---|---|---|---|
| Z Fold7 | 745/897 (#22 of 60) | 24 dB ("similar to the Honor Magic V5's 22.7 dB") | "clear and reasonably extended" (no number) | 76.6 dBA | 5.82 % | 2026-05-01 | https://bandicootlab.com/phone/samsung-galaxy-z-fold-7 |
| Z Flip7 | 704/897 (#25) | 27.5 dB | "clear but the treble response was uneven" | 77.2 dBA | 5.35 % | 2026-05-01 | https://bandicootlab.com/phone/samsung-galaxy-z-flip-7 |
| Z Fold8 | 691/897 (#31) | no dB figure; "Bass rolls off below roughly 190 Hz" | "the high end is unremarkable" | 78.5 dBA | n/s | 2026-09-19 | https://bandicootlab.com/phone/samsung-galaxy-z-fold-8 |
| Z Fold8 Ultra | 698/897 (#29) | no figure; "Bass is thin" | "High-frequency response is decent" | 77.4 dBA | 4.68 % (guide) | n/s | https://bandicootlab.com/phone/samsung-galaxy-z-fold-8-ultra |
| (context, part A) S26 Ultra | 857/897 (#3) | "18.4 dB of decay from the mids" (S25 Ultra 21.8 dB) | "8 dB above the mids" | 75.3 dBA | 3.3 % | n/s | https://bandicootlab.com/phone/samsung-galaxy-s26-ultra |

Comparison guides (same lab): Z Fold7 vs Z Flip7: "The Fold 7's speakers have fuller bass"; "The Flip 7 extends
higher frequencies further" (https://bandicootlab.com/guide/samsung-galaxy-z-fold-7-vs-galaxy-z-flip-7).
Z Fold8 Ultra vs Z Fold7: "The Fold 7's speakers have a fuller low end and a flatter, more even response
through the midrange"; "The Ultra reaches further at both frequency extremes but with a lumpier response
overall" (https://bandicootlab.com/guide/samsung-galaxy-z-fold-8-ultra-vs-samsung-galaxy-z-fold-7). The second
quote contradicts the Fold8 Ultra page ("Bass is thin").
Not found on Bandicoot (404): Z Flip8, A56, A57. Only Samsung Z models above; no A/M/Tab pages found.

Inference (mine): under one method, the bass-band drop is 18.4 dB for the S26 Ultra, 24 dB for Z Fold7 and
27.5 dB for Z Flip7, i.e. Z Fold7 about 5.6 dB and Z Flip7 about 9.1 dB less bass (60-250 Hz band average vs
mids) than the S26 Ultra. Band averages hide the slope, so this does not give per-band third-octave values;
"roughly 190 Hz" for Z Fold8 is not defined as f10 and is NOT entered as ten_db_down_hz.

## Charts and anchoring

- No chart could be calibrated or digitized: every curve found is either JS-rendered (DXOMARK, NotebookCheck
  review charts, Bandicoot Chart Builder) or a raster image WebFetch cannot open (the NotebookCheck
  Flip8-vs-Razr image fetch failed with a server error). So there are no calibration records in this part.
- anchor.md (researcher A, v0.1, PRELIMINARY) existed when I checked midway. It finds no per-band method offset for
  any site; Bandicoot scalars are "rough", usable for model-to-model differences (B), C for mapping to our bands.
  This part therefore records raw text and scalars only.

## Per-model summary

Level columns (125-500 Hz re 1 kHz), 10 dB-down frequency and 2-5 kHz tilt: **not obtainable for any model**
from readable sources. The table gives what each model does have.

| Model | Readable evidence | Bass relative to S26 Ultra | Treble | Confidence |
|---|---|---|---|---|
| Z Fold (2019) | none found | - | - | - |
| Z Fold2 5G | DXOMARK text | less (no low-end extension) | muffled, lacks upper content | C |
| Z Fold3 5G | DXOMARK text | similar or a bit less ("correct amount of bass") | good, slight lack of extension | C |
| Z Fold4 | DXOMARK text | "similar to S22 Ultra", wants more low-end | satisfying | C |
| Z Fold5 | DXOMARK text | same as Fold4 per DXOMARK | satisfying | C |
| Z Fold6 | none readable (NotebookCheck review cut off; no DXOMARK audio) | - | - | - |
| Z Fold7 | Bandicoot scalar | bass-band drop 24 dB vs 18.4 dB for S26U, same lab: about 5.6 dB less bass | "clear and reasonably extended" | B (difference only) |
| Z Fold8 | Bandicoot text, NotebookCheck news | "rolls off below roughly 190 Hz" (undefined cutoff) | "unremarkable" (Bandicoot); smaller ultra-high dip than Ultra (NBC) | C |
| Z Fold8 Ultra | Bandicoot text, NotebookCheck news | conflicting: "Bass is thin" (Bandicoot) vs "noticeable amount of bass", pink noise slightly better than S26U (NotebookCheck) | "decent" | C |
| Z Flip (2020) / Flip3 | NotebookCheck reviews exist, cut off | - | - | - |
| Z Flip4 | DXOMARK text | less ("lack of low-midrange support", thinner) | - | C |
| Z Flip5 | DXOMARK text | less ("lacked low-end extension") | "slightly thin but clear" | C |
| Z Flip6 | none readable | - | - | - |
| Z Flip7 | Bandicoot scalar | bass-band drop 27.5 dB vs 18.4 dB: about 9.1 dB less bass than S26U, 3.5 dB less than Fold7 | "clear but ... uneven" | B (difference only) |
| Z Flip7 FE | none found | - | - | - |
| Z Flip8 | NotebookCheck news (+ chart image) | "some bass" / "leichten Bass"; far more linear than Razr 70 Plus/Ultra | "much more linear" than Razr | C |
| A52 5G / A52s 5G | DXOMARK text (A52s = A52 per DXOMARK) | less ("lack of bass and low-end extension") | respectable | C |
| A33 5G, A53 5G | DXOMARK text | "satisfying" but con "limited/lacks sufficient bass" | bright, lower treble harsh at times | C |
| A34 5G | DXOMARK score only | - | - | C |
| A54 5G | DXOMARK text | warm, "lacked some depth in the low-end" | lacks high-end extension | C |
| A55, A56, A36, A26, A16 5G/4G | NotebookCheck reviews exist, cut off | - | - | - |
| M series (M55, M35, M15 ...) | none found; NotebookCheck has device pages but no own review of M55 | - | - | - |
| Galaxy Tab | not researched (low priority, search budget gone) | - | - | - |

Grouping supported by the data: A52 5G and A52s 5G (DXOMARK: results match, identical scores); Z Fold4 and
Z Fold5 (DXOMARK: same tonal balance). Z Fold4 / Z Flip4 are likened by DXOMARK to the S22 Ultra and A52, which
suggests a family sound but not a shared speaker. No other grouping is supported.

## Inference for starting settings (mine, NOT data)

- Direction: every source that compares a part-B model with a Samsung S-series phone puts its bass at or below
  the S-series (the one exception is NotebookCheck's Fold8 Ultra vs S26 Ultra, contradicted by Bandicoot).
  Flip models come out thinner than Fold models in both DXOMARK (Flip4/5 vs Fold4/5) and Bandicoot (Flip7 vs Fold7).
- Size, Bandicoot only (100 % volume, 50 cm, band edges of "mids" unknown): Fold7 about 5.6 dB and Flip7 about
  9.1 dB less 60-250 Hz output than the S26 Ultra relative to the mids. ILLUSTRATION ONLY: if that extra drop were
  spread evenly over 125-250 Hz of our S26U curve, the 10 dB-down point would move from about 190 Hz to about
  255 Hz (Fold7) and about 280 Hz (Flip7, assuming 315 Hz unchanged). A real roll-off moves in frequency rather
  than shifting flat, so treat these as order-of-magnitude. Practical reading: for Fold/Flip, a high-pass and
  virtual-bass crossover at or above the S26U values is safer than lower ones; no source supports boosting
  low bass on these phones.
- Treble: no number for any part-B model. Bandicoot's S26U "8 dB above the mids" has no Fold/Flip counterpart.

## Images / charts to digitize (main session, browser screenshots)

1. NotebookCheck pink-noise comparison, Galaxy Z Flip8 vs Razr 70 Plus / 70 Ultra (raster jpg, thumbnail):
   https://www.notebookcheck.com/fileadmin/_processed_/1/2/csm_sound-comparision_4a30edd023.jpg
   (in https://www.notebookcheck.com/Samsung-um-Welten-besser-als-Motorola-Smartphones-fuer-Audio-Fans-ist-Galaxy-Z-Flip8-die-beste-Wahl.1388378.0.html ;
   German caption says "Flip9", a typo). WebFetch could not open the image.
2. Bandicoot Lab Chart Builder (JS), "Audio > Speaker Frequency Response": overlay S26 Ultra with Z Fold7, Z Flip7,
   Z Fold8, Z Fold8 Ultra. Same lab, same mic and distance for our anchor model, so this is the most direct route to
   per-band differences: https://bandicootlab.com/chart-builder
3. DXOMARK "Music playback frequency response" (JS graph, 1/12 octave, anechoic) on each page in the DXOMARK table
   above: Z Fold2, Fold3, Fold4, Fold5, Flip4, Flip5, A52 5G, A33, A53, A54 (10 pages). No S26U on DXOMARK, so
   these give shapes but need their own offset (anechoic, no room gain).
4. NotebookCheck review "Speakers" sections (JS pink-noise chart; A reports it as interactive, possibly with a data
   table to copy). Pages, all cut off for WebFetch:
   - Z Fold8 Ultra https://www.notebookcheck.net/The-thinnest-Samsung-smartphone-ever-takes-on-the-iPhone-Ultra-Galaxy-Z-Fold-8-Ultra-Review.1390192.0.html
   - Z Fold8 https://www.notebookcheck.net/Shooting-to-the-top-with-a-new-form-factor-Samsung-Galaxy-Z-Fold8-review.1394389.0.html
   - Z Flip8 https://www.notebookcheck.net/Ultra-lightweight-smartphone-powerhouse-with-a-6-9-inch-OLED-screen-Samsung-Galaxy-Z-Flip-8-review.1398173.0.html
   - Z Fold7 https://www.notebookcheck.net/The-market-leader-strikes-back-Samsung-Galaxy-Z-Fold7-review.1093384.0.html
   - Z Flip7 https://www.notebookcheck.net/Compact-Flip-phone-loses-ground-Samsung-Galaxy-Z-Flip7-review.1102761.0.html
   - Z Fold6 https://www.notebookcheck.net/Samsung-Galaxy-Z-Fold-6-review-The-dustproof-foldable-smartphone-with-an-S-Pen-gets-throttled.877030.0.html
   - Z Flip6 https://www.notebookcheck.net/Samsung-Galaxy-Z-Flip6-5G-review-An-almost-unrivalled-flip-phone-continues-to-improve.890376.0.html
   - Z Fold5 https://www.notebookcheck.net/Samsung-Galaxy-Z-Fold5-review-Small-steps-toward-being-the-best-foldable-smartphone.743358.0.html
   - Z Flip5 https://www.notebookcheck.net/Samsung-Galaxy-Z-Flip5-5G-review-The-foldable-phone-with-a-large-cover-display.742501.0.html
   - Z Flip3 https://www.notebookcheck.net/Samsung-Galaxy-Z-Flip3-5G-in-review-High-tech-foldable-smartphone.563197.0.html
   - Z Flip (2020) https://www.notebookcheck.net/Samsung-Galaxy-Z-Flip-review-The-better-foldable-smartphone.458678.0.html
   - A56 https://www.notebookcheck.net/Loads-of-innovations-in-the-premium-mid-range-Samsung-Galaxy-A56-5G-review.1020512.0.html
   - A55 https://www.notebookcheck.net/Samsung-Galaxy-A55-5G-review-A-lot-of-premium-features-in-a-midrange-smartphone.835803.0.html
   - A36 https://www.notebookcheck.net/Samsung-Galaxy-A36-5G-review-The-affordable-smartphone-focuses-on-security-a-premium-feel.1013221.0.html
   - A26 https://www.notebookcheck.net/The-new-Galaxy-A-smartphone-brings-a-breath-of-fresh-air-to-the-mid-range-Samsung-Galaxy-A26-5G-review.1015052.0.html
   - A16 5G https://www.notebookcheck.net/Samsung-Galaxy-A16-5G-smartphone-review-The-particularly-inexpensive-Galaxy-with-6-years-of-updates.948868.0.html
   - A16 4G https://www.notebookcheck.net/Samsung-Galaxy-A16-4G-Review-OLED-display-smartphone-for-under-180-Euros.1002095.0.html
   The S26 Ultra review (in anchor.md) is on the same chart, so these would give same-method differences.

Count: 1 raster image + 1 Bandicoot chart view + 10 DXOMARK graphs + 17 NotebookCheck review charts = 29.

## Not used

- GSMArena: not used. It measures loudness only, and no model was left where it would have been the only
  evidence and still searchable (M series / Tab searches stopped when the shared search budget ran out).
- Mobilissimo.ro acoustics articles (Z Fold7, Fold5, Fold8, Fold8 Ultra, Fold2, Flip6, Flip3, A72): dBA loudness
  and listening impressions only, no frequency response, no conditions.

## Open gaps

- No third-octave data for any part-B model; everything numeric depends on the browser work listed above.
- Bandicoot band edges (mids) and smoothing are unpublished; its 100 % volume brings in each phone's bass protection.
- M series and Galaxy Tab: no evidence collected.
- Z Fold6 / Z Flip6 / A55-A56 generation: only NotebookCheck exists, unread.
