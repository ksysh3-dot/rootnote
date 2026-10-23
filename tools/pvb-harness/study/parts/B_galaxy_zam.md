# Part B: Galaxy Z Fold / Z Flip, A series, M series (Tab low priority)

Status: IN PROGRESS (written incrementally; partial results are kept).

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
