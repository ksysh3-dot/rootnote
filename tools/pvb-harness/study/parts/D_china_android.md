# D: Chinese-market and emerging-market Android brands

Scope: Xiaomi, Redmi, POCO, OnePlus, OPPO, realme, vivo, iQOO, Honor, Huawei, Tecno/Infinix, nubia/RedMagic.
All values are RAW, as each source states them. No method offset has been applied. Written 2026-10-23 by researcher D.

**Bottom line:** no third-octave curve could be read for any model in this part, so the CSV has no per-band values.
The numbers that could be read are Bandicoot Lab scalars for four models, and two "low-end extension" Hz values.
Everything else is qualitative. The curves exist as JS charts or raster images, listed under "Images to digitize".

## Sources used

| Source | What it measures / conditions | Result |
|---|---|---|
| Bandicoot Lab (bandicootlab.com) | UMIK-1 with calibration file, REW, 20 Hz-20 kHz sine sweep at **50 cm**, phone at **100 % volume**, quiet room (not stated to be anechoic). Glossary: bass = 60-250 Hz, treble = 2-10 kHz, "f10 Low Cutoff" = the frequency where output is 10 dB below the midrange level (the mid band is not defined). | Phone and guide pages give text only: max dBA, THD, and sometimes "dB drop/decay from the mids to the bass band" or "low-end extension reaches down to N Hz". The curves are JS charts (page shows "Loading chart..."). The API needs a partner key (not worked around). 19 phone pages in my brands (from sitemap.xml), all read. |
| NotebookCheck | Pink-noise frequency diagram in each review's Speakers section. On a 2017 page I could read (Elephone S7), the chart data is a numeric table in the HTML: a frequency, then one dB value per device, plus "Bass 100-315 Hz ... % lower than median" summary lines. | **Not reachable.** WebFetch keeps only about 92-103k characters. Every review I tried (Xiaomi 17 Ultra, 15 Ultra, Redmi Note 14 Pro 5G, OnePlus 15, POCO F8 Ultra; also Italian, Turkish and Chinese editions) ends inside the benchmark tables, before Speakers. Offset doesn't help, because the stored text is already cut. Short NotebookCheck news articles gave qualitative text and one pink-noise PNG (POCO F8 Ultra). |
| DXOMARK audio | "Music playback frequency response", 1/12 octave, pure sine, anechoic. Volume and distance are not stated. | The graph is JS-rendered; there is no image or data in the fetched text. Qualitative timbre text only. DXOMARK is researcher E's part; I list only three models I had already read. |
| GSMArena (lowest priority) | Sweep "in an environment with controlled acoustic properties"; the chart runs from +30 to -30 dB with an undefined reference; LUFS loudness. | Used as a last resort for two popular models with no other evidence. Rows are labelled "GSMArena only, low trust": qualitative only, no numbers. |
| Chinese / Russian / other non-English sites | - | WebSearch (US-only) returned nothing usable for 外放 频响 (loudspeaker frequency response) queries: only Sina SEO pages and patents. No Chinese or Korean review site with published speaker measurements was found. Overclockers.ru has old (2016-18) Xiaomi reviews only. The shared web-search budget ran out partway through the work, so I made no further searches. |

## Calibrations

None. I did not see any chart: every curve is JS-rendered (Bandicoot, DXOMARK, NotebookCheck reviews) or is a raster
image the fetch tool cannot open (NotebookCheck PNG). I estimated nothing from descriptions.

## Per-model table

The 125-500 Hz columns are empty for every model: no source gave per-band values. "ten_db_down_hz" is empty as well.
Bandicoot's "low-end extension" Hz is probably its f10, but this is not confirmed, and f10 is referenced to "midrange", not
1 kHz. So it is quoted here and in the CSV notes, and not entered as ten_db_down_hz.

| Brand | Model | Bass evidence | Treble / tilt evidence | Source | Conf. |
|---|---|---|---|---|---|
| Xiaomi | Xiaomi 15 Ultra | mids-to-bass drop **13.6 dB**; low-end extension **173 Hz** | "clear, well-extended" treble | Bandicoot page + 17U vs 15U guide | B- |
| Xiaomi | Xiaomi 17 Ultra | drop **17.3 dB**; low-end extension **184 Hz**; "leans toward bass" | HF clarity "below average"; less HF detail than iPhone 17 Pro Max | Bandicoot | B- |
| Xiaomi | Xiaomi 17 | "warm and bass-forward"; much fuller bass than OnePlus 15 | HF "less pronounced"; more even than OnePlus 15 | Bandicoot | C |
| Xiaomi | Xiaomi 17T Pro | "bass response is limited" | "thin and forward" | Bandicoot | C |
| Xiaomi | Xiaomi 15T Pro | "leans heavily toward bass and midrange" | "notably weak high-frequency response" | Bandicoot | C |
| Xiaomi | Xiaomi 17T | less bass and depth than 15T and 17 (pink-noise test) | 15T has the more balanced treble | NotebookCheck news | C |
| Xiaomi | Xiaomi 13 Ultra / 14 | "lacked bass" / "lack of low-end" | 13U: natural treble, "slightly tinny" | DXOMARK | C |
| Xiaomi | Redmi Note 14 Pro 5G | "some minor bass presence" | "well-balanced", highs well presented | GSMArena only, low trust | C |
| POCO | POCO F9 Ultra | "meaningful output down to around 180 Hz" (criterion undefined); fuller than typical | midrange even | Bandicoot | C |
| POCO | POCO F9 Pro | "bass is thin" | high end "fine" | Bandicoot | C |
| POCO | POCO F8 Ultra | **rear 1620 subwoofer** plus front 1115F pair; "strong bass" | "highs largely precise" | NotebookCheck news (chart to digitize) | C |
| OnePlus | OnePlus 15 | "bass response is limited"; thinner than S26 Ultra (same-lab guide) | "leans toward the higher end", treble-forward | Bandicoot | C |
| OnePlus | OnePlus 15R | less bass than Galaxy S26 | mid/treble leaning; "flatter" per Honor 600 page | Bandicoot | C |
| OnePlus | OnePlus 13 | "thin"; cannot reach the bass the 15 reaches | "skews toward the upper register", but limited HF | Bandicoot | C |
| OnePlus | OnePlus Open | drop **20.2 dB** | highs "below the mids" (rolled off) | Bandicoot | B- |
| OnePlus | OnePlus 8 | weak low end and low mids | upper-mid emphasis | DXOMARK | C |
| Honor | Magic8 Pro | "bass response is thin"; less than Xiaomi 17 Ultra | "tilts toward the higher frequencies" | Bandicoot | C |
| Honor | Magic7 Pro | "decent bass output for a phone"; less than S26 Ultra | "not particularly rich in treble" | Bandicoot | C |
| Honor | Honor 600 | "low-frequency extension is limited" | upper mids and highs | Bandicoot | C |
| Honor | Magic V5 | drop **22.7 dB**, uneven | "clear and flat" treble | Bandicoot | B- |
| Honor | Magic V6 | "bass presence is limited" | midrange-leaning | Bandicoot | C |
| vivo | X300 Pro | - | "tinny at higher volumes" | NotebookCheck news | C |
| vivo | X100 Pro | Galaxy S23 Ultra "a bit more bass" | "balanced", "treble is clean" | GSMArena only, low trust | C |
| Infinix | Note Edge | "present but thin" | mids-forward, limited HF | Bandicoot | C |
| nubia | RedMagic 11S Pro / 11 Air | "very little bass" / "thin" | "tinny" / HF "lacks clarity" | Bandicoot | C |

Same-lab context (from anchor.md and Bandicoot's S26 Ultra page, not my measurement): S26 Ultra drop 18.4 dB, treble +8 dB
above mids. On that one metric, Xiaomi 15 Ultra and 17 Ultra lose less bass than the S26 Ultra, and OnePlus Open and Magic V5
lose more. All of this is at 100 % volume, where phone-side bass protection is fully active.

Not covered (no page found, or search budget exhausted): OPPO (Find X9 Pro has a NotebookCheck review, but it was not readable),
realme (GT 8 Pro, same), iQOO, Huawei (Pura 80 Ultra, same), Tecno, Redmi Note 15 series.

## Grouping

None. The data do not support shared-speaker groups. The one hardware fact that matters: POCO F8 Ultra has a dedicated
rear subwoofer (1620), so it must NOT inherit settings from other POCO/Xiaomi models.

## Interpretation (my inference, not source statements)

- Most models are described as thinner in bass than the S26 Ultra, and treble-leaning: OnePlus 13/15, Honor Magic8 Pro/600,
  RedMagic, POCO F9 Pro. A neutral profile is a fair start there; the S26U EQ is not.
- Xiaomi Ultra / 17 / 15T Pro are the exception: same or more bass than the S26 Ultra, with weaker treble.
- No dB size can be given for any model from wording alone.

## Images to digitize (main session, real browser)

Priority 1 - NotebookCheck pink-noise charts (in a browser the chart's value table may be copyable instead of reading pixels):
1. POCO F8 Ultra (raster PNG; WebFetch could not open the file): https://www.notebookcheck.net/fileadmin/Notebooks/Xiaomi/Poco_F8_Ultra/Poco_F8_Ultra_Pink_Noise.png
   (thumbnail https://www.notebookcheck.net/fileadmin/_processed_/3/4/csm_Poco_F8_Ultra_Pink_Noise_96854e663c.png; article .../Poco-F8-Ultra-The-2-1-sound-system-from-Bose-sets-new-standards.1189324.0.html)
2. POCO F8 Ultra review: https://www.notebookcheck.net/Affordable-flagship-with-Bose-subwoofer-Xiaomi-Poco-F8-Ultra-review.1189651.0.html
3. Xiaomi 17 Ultra: https://www.notebookcheck.net/Xiaomi-17-Ultra-review-Best-overall-package-in-the-smartphone-sector-meets-Leica-APO-zoom.1211793.0.html
4. Xiaomi 15 Ultra: https://www.notebookcheck.net/Review-Xiaomi-15-Ultra-Leica-powered-powerhouse.975197.0.html
5. Xiaomi 17: https://www.notebookcheck.net/Xiaomi-17-review-A-compact-Android-smartphone-heralding-a-new-era.1150243.0.html
6. Xiaomi 17 Pro: https://www.notebookcheck.net/Xiaomi-17-Pro-review-The-compact-top-smartphone-disappoints-in-one-key-area.1151302.0.html
7. Redmi Note 15 Pro (4G): https://www.notebookcheck.net/Xiaomi-Redmi-Note-15-Pro-smartphone-review-Pro-even-without-5G.1243402.0.html
8. Redmi Note 15 Pro 5G: https://www.notebookcheck.net/Xiaomi-Redmi-Note-15-Pro-5G-Smartphone-Review-Near-bezel-less-mid-range-phone-with-IP68-rating-and-30-hour-battery-life.1212512.0.html
9. Redmi Note 14 Pro 5G: https://www.notebookcheck.net/Redmi-Note-14-Pro-5G-review-A-feature-focused-smartphone-for-bargain-hunters.961821.0.html
10. OnePlus 15: https://www.notebookcheck.net/OnePlus-15-smartphone-review-Gaming-at-165fps-despite-being-slower-than-the-predecessor.1171622.0.html
11. OPPO Find X9 Pro: https://www.notebookcheck.net/Ingenious-smartphone-with-camera-innovation-SoC-dilemma-Oppo-Find-X9-Pro-review.1158701.0.html
12. OPPO Find X9: https://www.notebookcheck.net/Oppo-Find-X9-smartphone-review-High-end-for-under-900-but-with-SoC-problems.1173149.0.html
13. vivo X300 Pro: https://www.notebookcheck.net/More-than-just-an-unusual-camera-setup-Vivo-X300-Pro-review.1184298.0.html
14. vivo X300: https://www.notebookcheck.net/Brilliant-Zeiss-camera-in-a-compact-smartphone-Vivo-X300-review.1192262.0.html
15. Honor Magic8 Pro: https://www.notebookcheck.net/Flagship-power-with-an-XXL-battery-Honor-Magic8-Pro-smartphone-review.1204159.0.html
16. realme GT 8 Pro: https://www.notebookcheck.net/The-most-unusual-smartphone-design-of-2026-including-Ricoh-camera-Realme-GT-8-Pro-review.1237926.0.html
17. Huawei Pura 80 Ultra: https://www.notebookcheck.net/Huawei-Pura-80-Ultra-Smartphone-Review-Camera-monster-with-compromises.1209229.0.html

Priority 2 - Bandicoot Lab JS charts (same rig as their S26 Ultra test):
18. https://bandicootlab.com/guide/samsung-galaxy-s26-ultra-vs-oneplus-15 (S26 Ultra and OnePlus 15 in one chart: most direct)
19. https://bandicootlab.com/guide/xiaomi-17-ultra-vs-xiaomi-15-ultra
20. https://bandicootlab.com/guide/xiaomi-17-ultra-vs-honor-magic8-pro
21. https://bandicootlab.com/guide/oneplus-15-vs-xiaomi-17
22. https://bandicootlab.com/guide/oneplus-15-vs-oneplus-13
23. https://bandicootlab.com/guide/xiaomi-17t-pro-vs-oneplus-15
24. https://bandicootlab.com/chart-builder (Audio > Speaker Frequency Response): add S26 Ultra plus POCO F9 Ultra/F9 Pro,
    Xiaomi 15T Pro, Honor 600/Magic7 Pro/V5/V6, OnePlus 15R/Open, Infinix Note Edge, RedMagic 11S Pro/11 Air

Priority 3 - DXOMARK cross-check (E's part): Xiaomi 13 Ultra, Xiaomi 14, OnePlus 8 audio-test pages (URLs in the CSV).

Count: 24 chart items (17 NotebookCheck, of which one is a raster PNG; 7 Bandicoot), plus 3 DXOMARK cross-references.

## Open gaps

- No numeric curve for any model. All per-band values depend on the screenshots above.
- NotebookCheck method details (distance, volume) could not be read. Read them next to the chart.
- No usable Chinese, Korean or Russian measurement site was found. Search coverage was weak (US-only engine, budget exhausted).
- Not reached at all: iQOO, Tecno, Huawei Mate, OPPO Reno, realme numbered series.
- anchor.md (researcher A, v0.1) existed when checked. It gives no per-band offset for any site; Bandicoot is "rough" (scalars only).
