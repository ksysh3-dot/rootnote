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

