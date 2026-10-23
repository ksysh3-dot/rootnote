# Anchor: published S2x Ultra speaker data vs our S26 Ultra measurement

Status: PRELIMINARY (written 2026-10-23 by researcher A, will be revised as more sources are checked).
Read the "Verdict summary" first.

## Our anchor (reference for every offset below)

Galaxy S26 Ultra (SM-S948N), UMIK-1 at 30 cm, volume 60/150, Dolby Atmos off, in a room, sine sweep,
third-octave, dB re 1 kHz (speaker + room):

| Hz | 125 | 160 | 200 | 250 | 315 | 400 | 500 | 630 | 800 | 1k | 1.25k | 1.6k | 2k | 2.5k | 3.15k | 4k | 5k | 6.3k | 8k | 10k |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dB | -20.2 | -14.0 | -8.9 | -4.9 | -6.0 | -5.6 | -4.7 | -2.8 | 1.0 | 0.3 | 3.0 | 2.3 | 5.3 | 10.7 | 11.1 | 10.9 | 15.7 | 13.3 | 7.9 | -1.6 |

Derived from the anchor (my arithmetic, plain dB averages of the bands listed):
- mids 500-2000 Hz average = +0.6 dB re 1 kHz; highs 2-10 kHz average = +9.1 dB; highs minus mids = 8.5 dB.
- "drop from mids" to 125-160 Hz = 17.7 dB; to 125 Hz alone = 20.8 dB; to 125-250 Hz = 12.6 dB.
- 10 dB below 1 kHz: about 190 Hz (between 160 Hz -14.0 and 200 Hz -8.9, linear-in-dB interpolation).

## Verdict summary

| Site | What it publishes for S2x Ultra | Verdict | Confidence |
|---|---|---|---|
| Bandicoot Lab (bandicootlab.com) | Scalars only: loudness dBA, "dB drop from the mids to the bass band", "treble X dB above the mids" (some models), THD %. Charts are JS-loaded and not readable here; numeric API needs a partner key. | **rough** (scalars only; usable for model-to-model DIFFERENCES within Bandicoot, not for third-octave shapes) | B for differences between Galaxy models, C for mapping to our bands |
| NotebookCheck | Pink-noise "frequency diagram" (JS chart with third-octave-like bands) in every S-series review. Not reachable: WebFetch truncates every NotebookCheck review at about 82-94 k characters, before the Speakers section (it stops in the Display or Performance section). A reader-proxy fetch was declined by the permission system and was not worked around. | **not possible yet** (pending screenshots or the chart table from a browser) | n/a |
| DXOMARK | "Music playback frequency response", 1/12 octave, pure-sine, anechoic (S24 Ultra audio test). The graph is script-rendered; no image URL, no data file in the fetched page. DXOMARK does not appear to have audio-tested S25/S26 Ultra. | **not possible** (data not reachable) | n/a |
| Mobilissimo.ro | Loudness dBA only (S26 Ultra 85.8 top / 87.5 bottom / 96.1 multimedia), no frequency response, no conditions. | **not possible** (no FR) | n/a |
| GSMArena | Not used for anchoring (low trust, per instructions; their speaker test is loudness only anyway). | not used | n/a |

Bottom line for the other researchers: **no site gives a third-octave curve we can read for the S26/S25/S24 Ultra,
so there is no per-band method offset yet.** The only cross-site check possible is Bandicoot's two scalars,
which agree with our anchor within about 1-2 dB under plausible band definitions (see below), but whose
band definitions are not published.

## Bandicoot Lab

- Method (from https://bandicootlab.com/explainer/how-we-test-speakers-microphones): miniDSP UMIK-1 with its
  calibration file, REW, phone at **100 % volume**, "a consistent, quiet room" (not stated to be anechoic),
  20 Hz-20 kHz **sine sweep at 50 cm** for frequency response and THD; pink noise at 40 cm for loudness (dBA).
  Bass score = "where the bass sits relative to the midrange" + evenness; clarity = treble vs mids + smoothness.
  The **bands behind "drop from the mids to the bass band" and "above the mids" are not published**, nor the smoothing.
- Calibration used: none possible (no chart). Numbers are quoted from text.
- S26 Ultra (https://bandicootlab.com/phone/samsung-galaxy-s26-ultra): bass "18.4 dB of decay from the mids";
  high end "8 dB above the mids"; 75.3 dBA; THD 3.3 %.
- Comparison with our anchor (inference, not a Bandicoot statement):
  - Treble: Bandicoot +8 dB vs our highs-minus-mids 8.5 dB (2-10 kHz vs 500-2000 Hz) or 8.2-10.9 dB for other
    plausible band choices. Agreement within about 1-2 dB.
  - Bass: our anchor gives 17.7 dB for a 125-160 Hz bass band and 20.8 dB at 125 Hz alone; a band reaching down to
    60 Hz cannot be checked (our anchor starts at 125 Hz). So 18.4 dB is consistent with our curve, but it does not
    pin down which frequency the number refers to.
  - Volume: Bandicoot measures at 100 % volume. Our phone_model.py notes that long loud sweeps on the S26 Ultra
    showed 250-800 Hz 4-7 dB lower than small signals (bass protection), so Bandicoot's bass drop for any Galaxy can
    be larger than at our volume 60. This affects all Galaxy models similarly only if they share the same
    protection tuning (not known).
- Offsets per third-octave band: **not computable** (scalar data). What IS usable: the difference between two
  Galaxy models in Bandicoot's own metric (same lab, same mic, same distance, same 100 % volume), applied as a
  coarse bass-band shift relative to our S26 Ultra curve. See A_galaxy_s.md for the per-model numbers.
- Verdict: **rough**. Confidence B for the relative ranking/differences, C for any per-band translation.

## NotebookCheck

- Every Galaxy S review has a "Speakers" section with a pink-noise frequency diagram (an interactive chart,
  not an image) and an "audio analysis" box. Method details (distance, volume) could not be read for the same reason.
- Fetch attempts (all truncated before the Speakers section):
  - https://www.notebookcheck.net/Blocks-prying-eyes-Samsung-Galaxy-S26-Ultra-review.1278349.0.html (ends at the CrossMark table, ~94 k chars)
  - https://www.notebookcheck.com/Sperrt-neugierige-Blick-aus-Test-Samsung-Galaxy-S26-Ultra.1251262.0.html (ends in the Display section, ~82 k chars)
  - https://www.notebookcheck.net/Samsung-Galaxy-S25-Ultra-review-The-AI-phone-relies-fully-on-artificial-intelligence-and-small-hardware-upgrades.968346.0.html (ends in the Display/PWM section, ~94 k chars)
- The S26 Ultra review text says only that the loudspeaker "sounds a little tinny" (call-quality section).
  NotebookCheck's "Best smartphone for audio enthusiasts in our 2026 reviews" gives S26 Ultra an audio score of
  83.8 % (pink-noise based), no curve.
- Verdict: **not possible yet**. The chart is the most promising anchor candidate: listed under "images to
  digitize" in A_galaxy_s.md (it needs a browser screenshot or the chart's data table copied by hand).

## DXOMARK

- https://www.dxomark.com/samsung-galaxy-s24-ultra-audio-test/ : "Music playback frequency response", 1/12-octave,
  pure sine, anechoic (distance not stated on that page). Graph not present as an image or data in the fetched page.
  Qualitative: "all-in with bass power", warm; low-mid/upper-bass resonance ("muddy"); low-end extension
  "quite good but could have gone further"; harsh at maximum volume.
- Verdict: **not possible** (no data reachable). Even if obtained, an anechoic sine response at an unstated volume
  would need its own offset (no room gain below ~300 Hz compared with our in-room curve).

## Revision log
- 2026-10-23 v0.1: first version (Bandicoot, NotebookCheck, DXOMARK, Mobilissimo checked).
