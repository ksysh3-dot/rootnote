# Part C - Western / Japanese-market Android (+ iPhone context)

Researcher C. Brands: Google Pixel, Motorola, Sony Xperia, Nothing/CMF, ASUS (ROG, Zenfone), Fairphone,
other Western/Japanese-market Android. iPhone 16 Pro / 17 Pro rows are CONTEXT ONLY.
All values are RAW as published (dB re 1 kHz where a curve exists). No anchor offset applied.
Status: DONE for text sources (2026-10-23). Numeric curves pending: see "Images to digitize".
Anchor: anchor.md (researcher A, v0.1, 2026-10-23) was read; it gives no per-band offset for any site yet.

## Source access log (what could and could not be read)

| Source | What it measures | Access result |
|---|---|---|
| NotebookCheck reviews (notebookcheck.net and language editions) | Pink-noise "frequency diagram" per review, plus text summary (Bass 100-315 Hz / Mids 400-2000 Hz / Highs 2-16 kHz as % deviation from median) | WebFetch converts the page to text and cuts it at about 93,000 characters. On every review tried (Pixel 10 Pro, Motorola Edge 2020, Fairphone 5, Pixel 3 CN, Pixel 4 PT) the cut falls inside the benchmark tables, BEFORE the Emissions/Speakers section. The speaker chart and its data could not be read. |
| Bandicoot Lab (bandicootlab.com) | UMIK-1 with calibration file, REW, 20 Hz-20 kHz sine sweep at 50 cm, phone at 100 % volume, quiet room (not stated anechoic); loudness pink noise at 40 cm | Phone pages give text only (score, max dB, THD, wording on bass/treble). The frequency-response curve is only in the JS "Chart Builder" (Audio > Speaker Frequency Response) and in a partner-only API (key required; not worked around). |
| DXOMARK audio | 1/12-octave "music playback frequency response", pure sine, anechoic | The curve is JS-rendered; WebFetch shows only the caption. Qualitative timbre text readable. DXOMARK numbers are researcher E's part. |
| Android Authority Pixel 10 Pro XL speaker article | SPL meter, pink noise, loudness only | No frequency response. Qualitative only. |
| Sound & Vision, HTC One (2013) | Clio FW, pink noise RTA, mic about 10 mm from the speaker | Readable text: "230 Hz to 10 kHz, +/-3.5 dB" (Beats on). Historical only, no chart in the page. |
| GSMArena (lowest priority) | Since 2020: sweep recorded "in an environment with controlled acoustic properties"; chart +30 to -30 dB, 0 dB reference not defined; distance, volume, smoothing not stated | Not used for numbers (user rule). Every model in this part has a NotebookCheck and/or DXOMARK/Bandicoot chart to digitize, so no GSMArena-only row was needed. |
| Sony product pages (Xperia 1 VII) | Marketing | "extended treble and up to 10% richer mid-bass", no baseline, no numbers. Not used. |

### NotebookCheck: what was tried
Offset re-fetch (coordinator request): Pixel 10 Pro at offset 92000 and Pixel 9 Pro at offset 90000. In both, the
fetched text itself ends inside the benchmark tables (total 92,867 and 91,496 characters). The tool stores a cut
page, so a larger offset cannot reach the Speakers section. No numbers, unchanged.
The fetch tool cut every review at about 93k characters. Table of contents of the Pixel 9 Pro review confirms the
speaker section exists ("13. Emissions - Dual speakers inside the Pixel phone") but sections 13-15 are beyond the cut.
Short "Verdict on ..." articles carry no speaker data. One NotebookCheck news article quotes the review's audio
summary for the Motorola Moto G37 (bass 100-315 Hz "28.4 percent lower than the median", mids 10 %, highs 4.7 %),
which shows the summary format exists, but this metric is % of a dB median, not dB re 1 kHz, so it is not usable
as a curve. NotebookCheck speaker charts therefore all go to "images to digitize" below.

## Bandicoot Lab (text only; curves need screenshots)

Method (from https://bandicootlab.com/explainer/how-we-test-speakers-microphones): UMIK-1 + individual calibration
file, REW, 20 Hz-20 kHz sine sweep at 50 cm, phone at 100 % volume, quiet room (anechoic not claimed); loudness =
pink noise, dBA at 40 cm. Bass and clarity sub-scores come from the sweep ("where the bass sits relative to the
midrange", evenness); band edges and smoothing are not published. Page texts read like generated prose; one page
and one guide disagree on the Pixel 11 (page: "low frequencies roll off early"; Pixel 11 vs 10 guide: "reaches
lower into the bass region"). Treat wording as rank-order hints, confidence C.

Important for the merge: Bandicoot also tests the Galaxy S26 Ultra on the same rig. Its page states "Bass extension
improved to 18.4 dB of decay from the mids, better than the Galaxy S25 Ultra's 21.8 dB" (metric undefined). The
S26 Ultra vs Pixel 10 Pro XL guide has both curves in one chart, which is the most direct same-rig comparison found.
Caveat: 100 % volume, so phone-side bass protection is fully active (our anchor is volume 60/150).

| Model | Speaker score /897 (rank of 60) | Max level | THD avg | Bass / tilt wording (verbatim fragments) | Page |
|---|---|---|---|---|---|
| Pixel 10 | 781 | 76.0 dBA | 6.28 % | "clear mids and decent body"; vs 10: Pro has "slightly fuller bass, extending lower" | guide google-pixel-10-vs-pixel-10-pro-vs-pixel-10-pro-xl |
| Pixel 10 Pro | 774 (#17) | 75.6 dB | 6.5 % | "leans toward the upper frequencies"; "Bass response is present but not as full-bodied as some competitors" | /phone/google-pixel-10-pro |
| Pixel 10 Pro XL | 645 (#39) | 75.8 dBA | 10.1 % | "leans toward the higher registers ... relatively thin bass"; "lighter than ... iPhone 17 Pro Max or Galaxy S26 Ultra"; "Bass extension is similar to the Pixel 10, but the overall frequency response is more even" | /phone/google-pixel-10-pro-xl |
| Pixel 11 | 735 (#23) | 76.6 dBA | not given | "Bass is thin ... Low frequencies roll off early" (page) vs "reaches lower into the bass region" than Pixel 10 (guide) | /phone/google-pixel-11 |
| Pixel 11 Pro | 699 (#28) | 77.2 dBA | 6.77 % | "typical phone speaker with a better-than-typical top end"; "bass rolls off early" | /phone/google-pixel-11-pro |
| Pixel 11 Pro XL | 897 (#1) | 76.6 dBA | not given | "bass is fuller than typical phone speakers manage"; "High-frequency response is excellent" | /phone/google-pixel-11-pro-xl |
| Nothing Phone (3) | 652 (#38) | 73.1 dB | 3.46 % | "leans toward the upper registers"; "bass is thin" | /phone/nothing-phone-3 |
| Nothing Phone (3a) | 589 (#48) | 71 dB | 10.15 % | "leans toward the upper range ... thin bass" | /phone/nothing-phone-3a |
| Nothing Phone (3a) Pro | 568 (#51) | 71.3 dB | 10.9 % | "leans toward the higher end"; "Bass response is thin" | /phone/nothing-phone-3a-pro |
| Nothing Phone (4a) Pro | 612 (#43) | 71.8 dBA | 8.39 % | "leans toward the upper frequencies ... thin bass response" | /phone/nothing-phone-4a-pro |
| iPhone 17 Pro (context only) | 823 (#5 of 59) | 75.2 dBA | 4.696 % | "balanced profile with strong high-end clarity and solid bass presence"; vs Pixel 11 Pro: "noticeably flatter through the critical midrange" | /phone/apple-iphone-17-pro |
| Galaxy S26 Ultra (anchor phone, for wording scale) | 857 (#3) | 75.3 dBA | 3.3 % | "Bass extension improved to 18.4 dB of decay from the mids" | /phone/samsung-galaxy-s26-ultra |

Only Pixel and Nothing models (plus Samsung, Apple, Chinese brands) appear on Bandicoot. No Motorola, Sony, ASUS
or Fairphone page was found (the device list is JS-rendered, so absence is not proven).
Same-site pairwise statements (guides, verbatim): iPhone 17 Pro vs Pixel 10 Pro: "The iPhone also delivers fuller
bass"; "The Pixel counters with slightly better clarity in the high frequencies". iPhone 17 Pro vs Pixel 11 Pro:
"the iPhone's frequency response is noticeably flatter through the critical midrange"; Pixel "thin bass".
S26 Ultra vs Pixel 10 Pro XL: "The Pixel's speaker has less bass presence and less clarity in the upper frequencies".
iPhone 17 series vs Pixel 10 series: Pixel 10 Pro XL has "thinner bass and more distortion than its siblings".

## Calibrations

None performed. No chart could be seen: every frequency-response chart found for this part is either JS-rendered
(Bandicoot, DXOMARK, NotebookCheck review charts) or a raster image (NotebookCheck news article). Per the rules,
nothing was estimated from descriptions. Calibration must be done by the main session on screenshots, following the
user's order (axes first, then 2-3 chart consistency check, then digitize). Notes for that work:
- Bandicoot: all charts come from one chart component (guides and Chart Builder), so one calibration may be reusable,
  but check it on 2-3 charts (for example guide S26U vs Pixel 10 Pro XL, guide Pixel 10/10 Pro/10 Pro XL, guide
  Pixel 11 Pro vs iPhone 17 Pro). Y-axis label, reference and smoothing are not published; read them off the chart.
- NotebookCheck: review charts are interactive (researcher A: "JS chart with third-octave-like bands"); if the
  browser shows a data table or tooltips with values, prefer those over pixel reading. The news-article chart
  (sound-comparision jpg) is a raster export of the same chart type and can serve as the consistency check.

## Per-model table

No model in this part has numeric third-octave data that could be read. The level columns of the requested table
(125-500 Hz re 1 kHz, 10-dB-down frequency, 2-5 kHz tilt) are therefore all "not available"; the table below gives the
qualitative evidence instead, kept apart from inference. Confidence: A = numeric curve read from a calibrated chart
or table; B = numeric from a less-defined source; C = qualitative only. Everything here is C.

| Brand | Model | Bass evidence (source states) | Treble / tilt evidence (source states) | Sources | Conf. |
|---|---|---|---|---|---|
| Google | Pixel 8 | "significant lack of low-end extension and depth"; bass "decent, with a clear focus on its upper section" | "clear treble and an emphasis on lower treble"; midrange lacks "warmth and fullness" | DXOMARK audio | C |
| Google | Pixel 9 Pro XL | Pixel 10 Pro XL gives "way more" of the lowest notes than the 9 Pro XL (listening) | top speaker of the 10 Pro XL "clearer ... far less distorted" than the 9 Pro XL | Android Authority (listening + SPL meter only) | C |
| Google | Pixel 9 / 9 Pro / 9a / 8 Pro / 10a | none read | none read | NotebookCheck charts only (to digitize) | none |
| Google | Pixel 10 | "clear mids and decent body"; Pro has "slightly fuller bass, extending lower" than the 10 | "good high-frequency detail" | Bandicoot guides | C |
| Google | Pixel 10 Pro | "present but not as full-bodied as some competitors"; less than iPhone 17 Pro | "leans toward the upper frequencies"; highs slightly clearer than iPhone 17 Pro | Bandicoot page + guides | C |
| Google | Pixel 10 Pro XL | "relatively thin bass"; "thinnest bass" of Pixel 10 series; less than S26 Ultra; "Bass extension is similar to the Pixel 10"; vs 9 Pro XL more low end | "leans toward the higher registers"; response "more even - less peaky" than 10/10 Pro; less upper clarity than S26 Ultra | Bandicoot; Android Authority | C |
| Google | Pixel 11 | page: "Low frequencies roll off early"; guide: "reaches lower into the bass region" than Pixel 10 (contradiction) | "High-frequency response is a strength" | Bandicoot | C (conflicting) |
| Google | Pixel 11 Pro | "bass rolls off early and music sounds thin below the midrange"; thinner than iPhone 17 Pro | "better-than-typical top end" | Bandicoot | C |
| Google | Pixel 11 Pro XL | "bass is fuller than typical phone speakers manage" (speaker score #1 of 60) | "High-frequency response is excellent" | Bandicoot | C |
| Motorola | Edge 40 Pro | "Bass was inconsistent and weak" | "harshness zone in treble and a piercing resonance"; cons: "too much focus on midrange" | DXOMARK audio | C |
| Motorola | Razr 70 Plus, Razr 70 Ultra | "virtually no depth"; outclassed "in the low- and high-frequency ranges" by the Z Flip8 | "the Razr's speakers roll off very early" (direction of roll-off not stated); max below 84 dB(A) pink noise | NotebookCheck news (pink-noise chart = raster image, to digitize) | C |
| Motorola | Moto G37 | NotebookCheck audio summary: bass 100-315 Hz "28.4 percent lower than the median" (mono speaker + earpiece) | mids deviate 10 %, highs 4.7 % from median | NotebookCheck news quoting its review | C (metric is % of a dB median, not convertible) |
| Motorola | Edge 60 Pro, Edge 50 Ultra, Moto G86 / G86 Power | none read | none read | NotebookCheck charts only (to digitize) | none |
| Sony | Xperia 1 IV | "low-midrange and upper bass are quite upfront"; "lack of bass and low end extension" | "high-midrange and treble appear lackluster"; "dark and almost muffled"; "Missing information between high-midrange and lower treble" | DXOMARK audio | C |
| Sony | Xperia 1 VII, Xperia 10 VI | none read (Sony marketing: "up to 10% richer mid-bass", no baseline) | none read | NotebookCheck charts only (to digitize) | none |
| ASUS | ROG Phone 7 | "bass rendition was powerful"; "Emphasis on upper bass can induce resonances"; "Bass distortion even at nominal volume" | "Lower treble presence was nice but ... high-end extension to be slightly insufficient" | DXOMARK audio | C |
| ASUS | ROG Phone 8 Pro, ROG Phone 9 Pro, Zenfone 12 Ultra | none read | none read | NotebookCheck charts only (to digitize) | none |
| Fairphone | Fairphone 4 | "Kick and bass information are not well rendered at all"; "lack of low-end extension is the most obvious defect" | "Very midrange-focused timbre, lacking low- and high-end extension"; "treble is a positive, even if lacking high end" | DXOMARK audio | C |
| Fairphone | Fairphone 5, Fairphone (Gen. 6) | none read | none read | NotebookCheck charts only (to digitize) | none |
| Nothing | Phone (1) | "almost absent bass and low-midrange" | "focuses on the high-midrange and lower treble, resulting in a thin and nasal sound" | DXOMARK audio | C |
| Nothing | Phone (3) | "bass is thin" | "leans toward the upper registers" | Bandicoot | C |
| Nothing | Phone (3a) | "thin bass"; "Low-end presence is weak" | "leans toward the upper range" | Bandicoot | C |
| Nothing | Phone (3a) Pro | "Bass response is thin" | "leans toward the higher end" | Bandicoot | C |
| Nothing | Phone (4a) Pro | "thin bass response" | "leans toward the upper frequencies" | Bandicoot | C |
| CMF | Phone 2 Pro (mono) | "The mono speaker cannot really inspire with its sound" | "slightly tinny" | NotebookCheck review text (first part of page only) | C |
| HTC | One (2013, historical) | numeric statement: "roughly +/-3.5 dB from 230 Hz to 10 kHz" (Beats on); "much more upper bass response, between 150 and 230 Hz" with Beats on | within the same +/-3.5 dB to 10 kHz | Sound & Vision (Clio, pink noise, mic ~10 mm) | B for the statement; near-field 10 mm, not comparable to 30 cm |
| Apple (context only) | iPhone 17 Pro | "solid bass presence"; fuller than Pixel 10 Pro and Pixel 11 Pro; "isn't as full as the Galaxy S26+ or Pro Max" | "balanced profile with strong high-end clarity"; "noticeably flatter through the critical midrange" than Pixel 11 Pro | Bandicoot | C |
| Apple (context only) | iPhone 16 Pro | none read | none read | NotebookCheck chart only (to digitize) | none |

Grouping by shared speaker design: not supported by data. The Nothing Phone (3a) and (3a) Pro have near-identical
Bandicoot loudness (71.0 / 71.3 dB) and THD (10.15 / 10.9 %) and the same wording, which is consistent with a shared
speaker but does not prove it (inference). Pixel 10 and 10 Pro are reported with different bass (Pro "slightly
fuller"), so they are not grouped. Researcher F's module file may settle the Nothing (3a) pair.

### Main qualitative findings (inference, not measured values)
- Pixel (8, 10, 10 Pro, 10 Pro XL, 11, 11 Pro) and every Nothing model checked are described by two independent
  labs (DXOMARK, Bandicoot) as treble-leaning with thin bass. On Bandicoot's same rig, the Pixel 10 Pro XL has less
  bass AND less upper clarity than the S26 Ultra. Direction for a starting profile: no extra bass boost beyond
  neutral; the treble-leaning wording suggests the same or more treble tilt than the S26 Ultra, but its size is unknown.
- Exceptions with opposite tilt: Sony Xperia 1 IV ("dark", upper bass/low-mid upfront, weak treble) and ASUS ROG
  Phone 7 (powerful upper bass, high-end extension "slightly insufficient"). These are older models.
- Pixel 11 Pro XL is the one Pixel described with fuller-than-typical bass.
- No size (dB) can be given for any of these. No numbers were interpolated.

## Images to digitize (for the main session, by screenshot)

Priority 1 - Bandicoot Lab, same rig as their S26 Ultra test (UMIK-1, 50 cm, 100 % volume). All JS charts ("Loading
chart..." in fetched text), so they need a browser screenshot:
1. https://bandicootlab.com/guide/samsung-galaxy-s26-ultra-vs-google-pixel-10-pro-xl (S26 Ultra + Pixel 10 Pro XL in one chart)
2. https://bandicootlab.com/guide/google-pixel-10-vs-pixel-10-pro-vs-pixel-10-pro-xl (Pixel 10, 10 Pro, 10 Pro XL)
3. https://bandicootlab.com/guide/samsung-galaxy-s26-series-vs-google-pixel-10-series (S26, S26+, S26 Ultra + three Pixel 10)
4. https://bandicootlab.com/guide/google-pixel-11-pro-vs-apple-iphone-17-pro (Pixel 11 Pro + iPhone 17 Pro)
5. https://bandicootlab.com/guide/apple-iphone-17-pro-vs-google-pixel-10-pro (iPhone 17 Pro + Pixel 10 Pro)
6. https://bandicootlab.com/guide/google-pixel-11-vs-google-pixel-10
7. https://bandicootlab.com/guide/google-pixel-11-pro-vs-google-pixel-10-pro
8. https://bandicootlab.com/guide/google-pixel-11-pro-xl-vs-google-pixel-10-pro-xl
9. https://bandicootlab.com/guide/apple-iphone-17-series-vs-google-pixel-10-series
10. https://bandicootlab.com/chart-builder : Audio > "Speaker Frequency Response", select Galaxy S26 Ultra + Nothing Phone (3),
    (3a), (3a) Pro, (4a) Pro (no Nothing guide page was found).

Priority 2 - NotebookCheck review speaker charts (pink noise, interactive chart in the "Emissions"/"Speakers" section;
not reachable by the fetch tool). If the browser exposes the chart's value table, copy it instead of reading pixels.
11. Pixel 8: https://www.notebookcheck.net/Google-Pixel-8-smartphone-review-Compact-and-with-7-years-of-updates.768436.0.html
12. Pixel 8 Pro: https://www.notebookcheck.net/Google-Pixel-8-Pro-review-Powerful-Android-smartphone-with-seven-years-of-updates.765989.0.html
13. Pixel 9: https://www.notebookcheck.net/Google-Pixel-9-review-The-small-Google-smartphone-has-taken-the-wrong-path.907380.0.html
14. Pixel 9 Pro: https://www.notebookcheck.net/Google-Pixel-9-Pro-smartphone-review-The-compact-flagship-with-great-cameras.927082.0.html
15. Pixel 9 Pro XL: https://www.notebookcheck.net/Google-Pixel-9-Pro-XL-review-Top-smartphone-with-more-of-a-high-end-feeling-also-in-terms-of-price.911586.0.html
16. Pixel 9a: https://www.notebookcheck.net/Great-battery-life-and-a-handy-size-Google-Pixel-9a-review.1039364.0.html
17. Pixel 10 (German): https://www.notebookcheck.com/Google-Pixel-10-Smartphone-im-Test-Immer-noch-empfehlenswert.1269674.0.html
18. Pixel 10 Pro: https://www.notebookcheck.net/Google-Pixel-10-Pro-Smartphone-Review-Compact-AI-monster-with-top-cameras.1129342.0.html
19. Pixel 10 Pro XL: https://www.notebookcheck.net/Google-Pixel-10-Pro-XL-Smartphone-Review-Gorgeous-flagship-that-offers-a-great-Android-experience-with-one-Achilles-heel.1100253.0.html
20. Pixel 10a (German): https://www.notebookcheck.com/Braucht-es-ueberhaupt-mehr-Smartphone-Test-Google-Pixel-10a.1318381.0.html
21. Pixel 9 Pro Fold: https://www.notebookcheck.net/The-best-foldable-photo-smartphone-Google-Pixel-9-Pro-Fold-review.922485.0.html
22. Motorola Edge 60 Pro: https://www.notebookcheck.net/Lightweight-curved-smartphone-with-great-endurance-and-a-strong-price-performance-ratio-Motorola-Edge-60-Pro-review.1051238.0.html
23. Motorola Edge 50 Ultra (German): https://www.notebookcheck.com/Test-Motorola-Edge-50-Ultra-Smartphone-Periskop-Zoomer-mit-riesigem-Speicher.827710.0.html
24. Moto G86: https://www.notebookcheck.net/The-brightest-star-in-the-midrange-Motorola-Moto-G86-smartphone-review.1069107.0.html
25. Moto G86 Power: https://www.notebookcheck.net/Motorola-Moto-G86-Power-review-bright-OLED-display-and-massive-battery-for-long-runtimes.1132774.0.html
26. Razr 70 Plus / 70 Ultra vs Galaxy Z Flip8 (raster image, same as researcher B's item #1):
    https://www.notebookcheck.net/fileadmin/_processed_/1/2/csm_sound-comparision_4a30edd023.jpg
    (article: https://www.notebookcheck.net/Samsung-is-miles-ahead-of-Motorola-smartphones-Galaxy-Z-Flip8-is-best-choice-for-audio-fans.1397676.0.html)
27. Sony Xperia 1 VII: https://www.notebookcheck.net/Sony-Xperia-1-VII-review-A-dream-smartphone-for-content-creators-and-photo-enthusiasts.1121056.0.html
28. Sony Xperia 10 VI: https://www.notebookcheck.net/Sony-Xperia-10-VI-smartphone-review-Compact-lightweight-waterproof-and-with-remarkable-endurance.873521.0.html
29. Nothing Phone (3): https://www.notebookcheck.net/Nothing-Phone-3-smartphone-review-Top-class-hardware-combined-with-unrivaled-design-and-secondary-display.1096614.0.html
30. Nothing Phone (3a): https://www.notebookcheck.net/The-elegant-all-rounder-presses-all-the-right-buttons-Nothing-Phone-3a-review.994680.0.html
31. Nothing Phone (3a) Pro: https://www.notebookcheck.net/More-megapixels-Nothing-Phone-3a-Pro-smartphone-review.999161.0.html
32. Nothing Phone (2a): https://www.notebookcheck.net/Nothing-Phone-2a-Review-The-first-affordable-Nothing-smartphone.830990.0.html
33. CMF Phone 2 Pro: https://www.notebookcheck.net/Less-modular-but-still-exceptional-CMF-Phone-2-Pro-review.1041306.0.html
34. ASUS ROG Phone 9 Pro: https://www.notebookcheck.net/Asus-ROG-Phone-9-Pro-review-This-smartphone-is-the-first-choice-for-every-gamer.924300.0.html
35. ASUS ROG Phone 8 Pro: https://www.notebookcheck.net/Asus-ROG-Phone-8-Pro-review-From-gaming-smartphone-to-premium-smartphone.801753.0.html
36. ASUS Zenfone 12 Ultra: https://www.notebookcheck.net/Fast-smartphone-with-plenty-of-AI-power-Asus-Zenfone-12-Ultra-review.998630.0.html
37. Fairphone 5: https://www.notebookcheck.net/Fairphone-5-review-Sustainable-smartphone-with-8-years-updates-and-5-years-warranty.775970.0.html
38. Fairphone (Gen. 6): https://www.notebookcheck.net/Fairphone-6-review-The-smartphone-built-with-sustainability-in-mind.1115153.0.html
39. iPhone 16 Pro (context only): https://www.notebookcheck.net/Apple-iPhone-16-Pro-smartphone-review-The-small-Pro-phone-with-the-big-display.899301.0.html
40. iPhone 17 Pro (context only): https://www.notebookcheck.net/Apple-iPhone-17-Pro-review-Faster-longer-further-Is-that-enough.1140998.0.html

Priority 3 - DXOMARK (researcher E's part; listed only so the main session can cross-check; JS-rendered
1/12-octave sine response, anechoic, volume and distance not stated on the page):
41. Pixel 8: https://www.dxomark.com/google-pixel-8-audio-test/
42. Motorola Edge 40 Pro: https://www.dxomark.com/motorola-edge-40-pro-audio-test
43. Sony Xperia 1 IV: https://www.dxomark.com/sony-xperia-1-iv-audio-test
44. ASUS ROG Phone 7: https://www.dxomark.com/asus-rog-phone-7-audio-test/
45. Fairphone 4: https://www.dxomark.com/fairphone-4-audio-test/
46. Nothing Phone (1): https://www.dxomark.com/nothing-phone-1-audio-test/

Unverified raster images (may not be charts; no captions): audioXpress ROG Phone 5 / Dirac article images
"20210318141531_Dirac-ROG-Phone5-SpeakersWeb.jpg" and "...Dirac-ROG-Phone5-AudioWizardWeb.jpg" at
https://audioxpress.com/news/dirac-makes-the-new-dual-speaker-asus-rog-phone-5-the-best-sounding-smartphone-available
(the article text gives no frequency numbers). Low priority.

Count: 40 priority-1/2 charts (10 Bandicoot, 30 NotebookCheck), plus 6 DXOMARK cross-references and 2 unverified images.

## Open gaps
- No readable numeric curve for any model in this part. Everything numeric depends on the screenshots above.
- NotebookCheck method details (distance, volume, smoothing, whether the y-axis is absolute SPL) could not be read
  for any review; read them from the review text next to the chart when screenshotting.
- Bandicoot measures at 100 % volume; our anchor is at 60/150. Bass protection at full volume will make Bandicoot's
  bass roll-off look steeper than at our volume, for any brand.
- Not found: NotebookCheck English reviews for Sony Xperia 1 VI, Motorola Razr 60 Ultra (only spec pages),
  Nothing Phone (2), CMF Phone 1, Zenfone 10/11 Ultra (not searched individually), HMD and Japanese-only brands
  (Sharp AQUOS: only older NotebookCheck reviews, e.g. Aquos V 2020, whose speaker text is one sentence; no curve).
- GSMArena was not used (every model here has at least one higher-priority chart to digitize).
- Anchor: anchor.md (researcher A, v0.1) existed when checked; it reports no per-band method offset for any site yet.

