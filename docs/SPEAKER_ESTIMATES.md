# Speaker response estimates for unmeasured phones

Status: research result, 2026-10-23. Not yet used by the app. Proposals at the end need the maintainer's decision.

## What this is

Rootnote has measured exactly one phone: the Galaxy S26 Ultra (UMIK-1, 30 cm, volume 60/150, Dolby Atmos off, one
room). Every other phone starts from the neutral profile. This document estimates how other phones' built-in
speakers differ from the S26 Ultra, so that starting values can be better than "flat", without measuring each phone.

Distortion and the phone's own protection behaviour are out of scope: they are assumed to behave like the S26 Ultra.

## Sources used, and sources set aside

| Source | Used for numbers? | Why |
|---|---|---|
| NotebookCheck review pages | **Yes** | Each review shows a pink-noise speaker table (third-octave, dB(A)) as text on the page; same method for every phone. |
| Papers, TI app notes, component datasheets (parts E, F) | Yes, as limits | Explain why the bass limit sits where it does; no per-phone curves. |
| Bandicoot Lab | **No** | Its curves are sold as licensed data (bulk/API). Not used until permission is asked. The numbers read earlier are kept out of this repository. |
| DXOMARK | Wording only | Its charts are script-drawn; its audio tests stop at the S24 series. |
| GSMArena | No | Lowest priority by decision; no numeric use. |

The NotebookCheck tables themselves are not copied into this repository either. Only the derived differences below
are, each with the NotebookCheck article id so it can be checked. The script is
`tools/pvb-harness/study/nbc_transfer.py`; it reads the tables from a private folder.

## Method: difference transfer

1. Read each phone's table from the review page (numbers, not a chart). 22 bands, 100 Hz to 12.5 kHz.
2. Reference every curve to the mean of 630-2000 Hz (a single 1 kHz band ripples by a few dB).
3. Take the difference "phone minus Galaxy S26 Ultra" inside NotebookCheck's data. A-weighting, distance, room and
   their measurement volume are the same for both phones, so they cancel.
4. Add that difference to our own S26 Ultra curve. The result is the phone's estimated curve in our measurement
   frame, from which the bass level and the -10 dB point (re the mids) are read.

Why not use NotebookCheck's curve directly: on the S26 Ultra their curve and ours differ by 7-9 dB at 125-160 Hz and by
5-10 dB at 2.5-6.3 kHz (room, distance, volume, weighting). Differences between phones are far more trustworthy than
either lab's absolute curve.

## Limits (read before using the numbers)

- **One sample per phone**, one measurement each; no repeat data. Band-to-band ripple of 2-3 dB is normal.
- **"Comparison" rows** are phones NotebookCheck shows next to the reviewed phone; the values are theirs, but taken
  from another article.
- **Volume:** NotebookCheck's measurement volume was not confirmed. If it is maximum volume, each phone's bass
  protection is part of the curve.
- **A second lab disagrees on the Galaxy S25 line.** The other lab's published summary puts the S25 and S25+ clearly
  below the S26 line in bass; NotebookCheck puts them level with it. A user with an S25+ reported weak bass. Until this
  is resolved, the S25 line is treated with the more cautious reading.
- The -10 dB point is unreliable where a phone has a deep dip in the mids (marked "unclear").

## Galaxy results (NotebookCheck, difference to the S26 Ultra)

Positive = more than the S26 Ultra. Groups: G1 within ±2 dB of the S26 Ultra's bass, G2 at least 2 dB less, G3 at
least 2 dB more.

| Model | NBC article | Bass 125-250 vs S26U | Low-mid 200-400 vs S26U | Treble 2.5-6.3k vs S26U | Est. -10 dB point | Group |
|---|---|---|---|---|---|---|
| Galaxy Z Fold6 | 877030 (review) | +5.0 | +6.0 | +3.4 | 162 Hz | G3 (more bass) |
| Galaxy Z Fold8 Ultra | 1390192 (review) | +4.5 | +6.3 | +1.1 | 161 Hz | G3 (more bass) |
| Galaxy S23 Ultra | 765989 (comparison) | +4.2 | +3.8 | +3.2 | 158 Hz | G3 (more bass) |
| Galaxy S24+ | 927082 (comparison) | +3.3 | +3.0 | +5.2 | 175 Hz | G3 (more bass) |
| Galaxy S24 | 899301 (comparison) | +3.2 | +4.6 | +4.8 | 168 Hz | G3 (more bass) |
| Galaxy A55 5G | 999161 (comparison) | +2.2 | +1.2 | +3.9 | 159 Hz | G3 (more bass) |
| Galaxy S25 Ultra | 1189651 (comparison) | +2.0 | +2.3 | +1.0 | 185 Hz | G3 (more bass) |
| Galaxy Z Fold7 | 1093384 (review) | +2.0 | +2.8 | +3.1 | 185 Hz | G3 (more bass) |
| Galaxy S24 FE | 1051238 (comparison) | +1.9 | +1.7 | +2.1 | 201 Hz | G1 (like S26U) |
| Galaxy S23+ | 811860 (comparison) | +1.9 | +2.8 | +1.5 | 193 Hz | G1 (like S26U) |
| Galaxy Z Fold5 | 877030 (comparison) | +1.9 | +1.7 | +1.6 | 171 Hz | G1 (like S26U) |
| Galaxy S23 | 775970 (comparison) | +1.5 | +3.2 | +2.9 | 197 Hz | G1 (like S26U) |
| Galaxy S24 Ultra | 924300 (comparison) | +1.2 | +1.6 | +3.7 | 201 Hz | G1 (like S26U) |
| Galaxy S23 FE | 915112 (comparison) | +1.0 | +1.7 | +1.0 | 199 Hz | G1 (like S26U) |
| Galaxy Z Fold8 | 1394389 (review) | +0.8 | +2.8 | +0.9 | 202 Hz | G1 (like S26U) |
| Galaxy A35 5G | 1013221 (comparison) | +0.5 | +0.1 | +3.3 | 214 Hz | G1 (like S26U) |
| Galaxy S26 Ultra | 1278349 (review) | +0.0 | +0.0 | +0.0 | 205 Hz | G1 (like S26U) |
| Galaxy S25+ | 978765 (review) | -0.1 | +1.7 | +0.1 | 210 Hz | G1 (like S26U) |
| Galaxy A16 5G | 948868 (review) | -0.3 | -0.7 | +5.2 | unclear (mid dip) | G1 (like S26U) |
| Galaxy S26 | 1284566 (review) | -0.4 | -0.6 | -0.9 | 224 Hz | G1 (like S26U) |
| Galaxy Z Flip8 | 1398173 (review) | -0.4 | +0.7 | -0.4 | unclear (mid dip) | G1 (like S26U) |
| Galaxy S25 FE | 1136160 (review) | -0.7 | -0.5 | -1.3 | 219 Hz | G1 (like S26U) |
| Galaxy A26 5G | 1015052 (review) | -0.7 | +0.1 | +5.3 | 225 Hz | G1 (like S26U) |
| Galaxy S25 | 1129342 (comparison) | -0.8 | -1.8 | +1.7 | 226 Hz | G1 (like S26U) |
| Galaxy A56 5G | 1039364 (comparison) | -0.9 | +1.4 | +4.4 | 207 Hz | G1 (like S26U) |
| Galaxy Z Flip5 5G | 742501 (review) | -1.1 | +3.2 | +2.5 | 202 Hz | G1 (like S26U) |
| Galaxy Z Flip7 | 1102761 (review) | -1.8 | -1.3 | -0.3 | 231 Hz | G1 (like S26U) |
| Galaxy Z Flip6 5G | 890376 (review) | -2.0 | -0.1 | +1.0 | 220 Hz | G2 (less bass) |
| Galaxy A36 5G | 1041306 (comparison) | -2.7 | +0.0 | +1.3 | 242 Hz | G2 (less bass) |
| Galaxy Z Flip | 458678 (review) | -2.8 | +4.0 | +4.0 | 204 Hz | G2 (less bass) |
| Galaxy S25 Edge | 1042425 (review) | -3.5 | -1.9 | -0.2 | 230 Hz | G2 (less bass) |
| Galaxy S21 FE 5G | 598090 (review) | -3.7 | +1.5 | +1.8 | 220 Hz | G2 (less bass) |
| Galaxy Z Flip3 5G | 563197 (review) | -3.8 | +2.0 | +2.7 | 219 Hz | G2 (less bass) |
| Galaxy A16 4G | 1002095 (review) | -5.5 | -1.9 | -1.6 | 240 Hz | G2 (less bass) |

**What the Galaxy data say**

- Almost every Galaxy phone with data sits within ±5 dB of the S26 Ultra in the 125-250 Hz band, and the estimated
  -10 dB point falls between about 160 and 240 Hz. The speaker family behaves similarly; the S26 Ultra profile's EQ
  shape (low-mid +3 dB at 220 Hz, treble -3 dB at 4.5 kHz) is a reasonable shape for Galaxy phones in general.
- More bass than the S26 Ultra (G3): Z Fold6, Z Fold8 Ultra, S23 Ultra, S24, S24+, and just over the line A55, S25 Ultra,
  Z Fold7.
- Less bass (G2): the budget A16 4G (-5.5 dB), Z Flip3, S21 FE, S25 Edge, Z Flip original, A36, and just over the line
  Z Flip6. Flips are thinner than Folds.
- Treble: the S24 line and most A models are 3-5 dB brighter than the S26 Ultra in 2.5-6.3 kHz.

## Other Android phones (NotebookCheck, same method; context)

| Model | Bass 125-250 vs S26U | Low-mid 200-400 | Treble 2.5-6.3k | Est. -10 dB point |
|---|---|---|---|---|
| Xiaomi 17 Pro Max | +10.6 | +11.5 | -1.8 | 129 Hz |
| Xiaomi 17 Pro | +9.8 | +8.6 | +0.8 | 136 Hz |
| Xiaomi Poco F8 Ultra | +9.5 | +7.5 | +0.7 | 132 Hz |
| Xiaomi 17 | +9.0 | +9.0 | +0.6 | 138 Hz |
| Google Pixel 10 Pro XL | +8.2 | +10.4 | +1.5 | 152 Hz |
| Motorola Edge 60 Pro | +6.3 | +8.5 | +2.7 | 159 Hz |
| Google Pixel 8 Pro | +5.6 | +2.7 | +2.8 | 150 Hz |
| Xiaomi 17 Ultra | +5.5 | +3.4 | -5.7 | 156 Hz |
| Honor Magic V6 | +5.0 | +4.6 | +3.7 | 155 Hz |
| OnePlus 15 | +4.5 | +5.9 | -4.7 | 179 Hz |
| Huawei Pura 80 Ultra | +4.4 | +4.1 | +2.4 | 153 Hz |
| Oppo Find X8 Pro | +4.0 | +6.9 | -2.2 | 177 Hz |
| Honor Magic V3 | +3.2 | +5.0 | +5.9 | 164 Hz |
| Honor 400 Pro | +2.9 | +2.7 | +4.4 | 169 Hz |
| Google Pixel 9 Pro XL | +2.9 | +2.4 | -1.0 | 155 Hz |
| Oppo Find X9 | +2.6 | +4.0 | -1.1 | 191 Hz |
| Google Pixel 9 Pro | +2.2 | +4.0 | +3.8 | 168 Hz |
| Oppo Find X9 Pro | +2.0 | +3.3 | -3.3 | 192 Hz |
| CMF Phone 2 Pro | +1.9 | +1.1 | +8.5 | 196 Hz |
| Realme GT 8 Pro | +1.6 | +3.7 | +0.6 | 189 Hz |
| Xiaomi 15 Ultra | +1.4 | +0.2 | +1.2 | 207 Hz |
| Sony Xperia 1 VI | +1.4 | +3.4 | -1.9 | 189 Hz |
| Asus ROG Phone 9 Pro | +1.3 | +0.0 | -1.8 | 224 Hz |
| Nothing Phone (3) | +1.3 | +2.0 | +3.1 | 203 Hz |
| Google Pixel Fold | +1.3 | +4.3 | -2.6 | 211 Hz |
| Xiaomi Mix Fold 4 | +1.2 | +4.5 | -7.9 | 196 Hz |
| Nothing Phone (3a) Pro | +1.1 | +3.0 | +2.4 | 209 Hz |
| Google Pixel 9 | +1.0 | +3.0 | +2.1 | 158 Hz |
| Google Pixel 9 Pro Fold | +0.7 | +1.7 | +0.3 | 204 Hz |
| Xiaomi 14 Pro | +0.4 | +0.9 | +1.6 | 208 Hz |
| Nothing Phone (3a) | +0.4 | +2.3 | +2.1 | 212 Hz |
| Vivo X300 | +0.3 | +0.5 | +1.9 | 205 Hz |
| Sony Xperia 1 VII | +0.3 | +2.6 | -2.6 | 199 Hz |
| Asus ROG Phone 8 Pro | +0.2 | +1.6 | +3.4 | 207 Hz |
| Google Pixel 9a | +0.2 | +1.4 | +1.8 | 204 Hz |
| Honor Magic8 Pro | +0.1 | +0.2 | +0.9 | 223 Hz |
| Vivo X300 Pro | +0.1 | +2.1 | +2.3 | 201 Hz |
| Xiaomi Poco F7 Ultra | -0.6 | +0.7 | +1.4 | 190 Hz |
| Google Pixel 10 Pro | -0.8 | +1.7 | -2.7 | 210 Hz |
| Asus Zenfone 12 Ultra | -0.9 | -3.7 | -0.9 | unclear |
| Motorola Razr 40 Ultra | -1.0 | +3.0 | -3.3 | 211 Hz |
| Motorola Moto G86 Power | -1.6 | +2.3 | -1.3 | 209 Hz |
| Xiaomi Mix Flip 2 | -2.1 | +0.5 | -5.5 | 219 Hz |
| OnePlus 9 Pro | -2.2 | +4.3 | -2.7 | 206 Hz |
| Google Pixel 7 | -2.3 | -0.4 | +3.4 | 227 Hz |
| Google Pixel 8 | -2.5 | -1.6 | -0.3 | 218 Hz |
| Xiaomi Redmi Note 13 Pro+ 5G | -2.5 | -0.2 | +2.3 | 240 Hz |
| Motorola Edge 60 | -2.8 | +1.7 | -1.7 | 215 Hz |
| Oppo Find N3 Flip | -3.4 | -2.2 | +5.2 | 257 Hz |
| Xiaomi Redmi Note 14 Pro+ 5G | -3.6 | -1.4 | -0.6 | 242 Hz |
| OnePlus 7T Pro | -3.9 | +2.7 | -3.6 | 213 Hz |
| Motorola Edge 60 Fusion | -4.0 | -0.1 | -2.5 | 225 Hz |
| Xiaomi 11T Pro | -4.1 | -1.6 | -0.3 | 246 Hz |
| Nothing Phone (2a) | -5.0 | +0.1 | -1.3 | 227 Hz |
| Xiaomi Redmi Note 15 Pro | -5.2 | -4.3 | +4.9 | unclear |
| Motorola Moto G86 | -5.5 | -1.9 | -5.5 | 248 Hz |
| Sony Xperia 10 VI | -5.8 | -0.9 | -4.8 | 230 Hz |
| Xiaomi Redmi Note 14 Pro 5G | -6.4 | -4.1 | -1.7 | 323 Hz |
| Fairphone 5 | -7.4 | -2.7 | -2.1 | 271 Hz |
| Xiaomi Redmi Note 15 Pro 5G | -8.4 | -2.0 | -12.0 | 251 Hz |
| Fairphone 6 | -9.0 | -5.9 | +4.3 | 309 Hz |
| Motorola Razr 70 Plus | -10.1 | -4.0 | -0.6 | 248 Hz |
| Xiaomi Redmi 14C | -11.1 | -5.8 | -2.2 | unclear |

Patterns: recent Xiaomi number series (17, 17 Pro, Poco F8 Ultra with its rear subwoofer) and the Pixel 10 Pro XL show
much more low bass than the S26 Ultra; older and budget models (Redmi 14C, Redmi Note 14 Pro, Fairphone 5/6, Moto G86,
Xperia 10 VI) show 5-11 dB less. The Poco F8 Ultra has a dedicated subwoofer and must not share a profile with other
Xiaomi or Poco phones.

## Why the bass limit sits where it does (parts E and F)

- Phone speaker modules (about 11x15 to 18x16 mm) resonate at about 800-1100 Hz in the standard 1 cc test box
  (manufacturer datasheets; TI SLAA936: "often in the 700- to 1000-Hz range"). Adsorbent beads in the back volume lower
  that by about 110-200 Hz; a teardown found such beads in the S26 Ultra's speaker.
- A plain box at that resonance would be 20-28 dB down at 200 Hz. The S26 Ultra measures about -9 dB there, so the
  phone's own processing and the room add 10-19 dB. The low-frequency limit is therefore set mostly by the maker's
  tuning, not by the part; datasheets give limits, not starting values.
- No phone maker or supplier publishes a per-model speaker response, f0 or frequency range.
- Size and class predict the bass limit only roughly (flagship about 190 Hz, mid-range about 300 Hz, budget about
  450 Hz, each ±0.5 octave). The NotebookCheck data put most mid-range Galaxy A models close to the flagships, so
  for Galaxy phones the measured data beat the class rule.

## Proposed starting values (for decision; not applied)

Virtual bass stays at +0 on every unmeasured phone (current policy). Only the EQ start changes. The bass boost is never
larger than the S26 Ultra's (+3 dB).

| Group | Models (examples) | `pvb_low_db` at 220 Hz | `pvb_hi_db` at 4.5 kHz | `speaker_floor_hz` | `pvb_hp_hz` |
|---|---|---|---|---|---|
| G1, like S26 Ultra | S26 (S26+ assumed the same: no NotebookCheck data), S24 Ultra, S24 FE, S23, S23+, S23 FE, S25 FE, Z Fold5, Z Fold8, Z Flip5/7/8, A16 5G, A26, A35, A56 | +3 | -3 (-4 if treble ≥ +3 dB) | 150 | 100 |
| G3, more bass | S23 Ultra, S24, S24+, S25 Ultra, Z Fold6, Z Fold7, Z Fold8 Ultra, A55 | +3 | -3 (-4 if treble ≥ +3 dB) | 150 | 100 |
| G2, less bass | S25 Edge, S21 FE, Z Flip (1st), Z Flip3, Z Flip6, A16 4G, A36; S25 and S25+ (until the disagreement is resolved) | +2 | -3 | 200 | 120 |
| No data | everything else, and all non-Galaxy phones for now | neutral profile (as now) | | | |

Derivation in one line each: G1/G3 take the S26 Ultra's blind-tested EQ shape because their low and mid bands differ
by 2 dB or less in the direction that matters (G3 has more, not less). G2 gets a smaller low-mid boost and a higher
high-pass because the speaker reaches the same level 20-40 Hz higher and has less in reserve. A treble cut of -4
follows the 3-5 dB brighter curve of the S24 line and most A models, capped at one dB beyond the S26 Ultra.

## Open questions

1. Ask Bandicoot Lab for permission (non-commercial, open-source use of a few derived values per phone). Their data
   also include per-model microphone responses, which would let the in-app measurement correct for the phone's mic.
2. Resolve the S25 disagreement: one measurement of an S25 or S25+ with the in-app measurement, or a shared settings
   code from an S25 user, would settle which reading to trust.
3. Confirm NotebookCheck's measurement volume.
4. Per-model tables live outside the repository; the research notes in `tools/pvb-harness/study/parts/` record the
   sources and how each number was obtained.
