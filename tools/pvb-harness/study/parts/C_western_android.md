# Part C - Western / Japanese-market Android (+ iPhone context)

Researcher C. Brands: Google Pixel, Motorola, Sony Xperia, Nothing/CMF, ASUS (ROG, Zenfone), Fairphone,
other Western/Japanese-market Android. iPhone 16 Pro / 17 Pro rows are CONTEXT ONLY.
All values are RAW as published (dB re 1 kHz where a curve exists). No anchor offset applied.
Status: IN PROGRESS (written incrementally).

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

