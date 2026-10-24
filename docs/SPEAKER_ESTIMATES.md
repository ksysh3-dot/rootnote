# Speaker response estimates for unmeasured phones

Status: 2026-10-24. Applied: the conservative start for every unmeasured phone (neutral profile: high-pass 120 Hz,
low-mid +2 dB at 220 Hz, treble -2 dB at 4.5 kHz, speaker floor 200 Hz, virtual bass +0).

## Data policy

Per-model measurements taken from third-party reviews and labs are used for research only and are **not** kept in this
public repository: no copied tables, no per-model derived values. What is published here is the method and aggregate
results across many phones. The research copy stays with the maintainer.

## What this is

Rootnote has measured exactly one phone: the Galaxy S26 Ultra (UMIK-1, 30 cm, volume 60/150, Dolby Atmos off, one
room). Every other phone starts from the neutral profile. This document explains how that start was chosen.

Distortion and the phone's own protection behaviour are out of scope: they are assumed to behave like the S26 Ultra.

## Method: difference transfer

1. For a set of phones measured by one reviewer with one method (third-octave speaker response), take each phone's
   curve referenced to its mids (mean of 630-2000 Hz).
2. Take the difference "phone minus Galaxy S26 Ultra" inside that reviewer's data. The reviewer's own room, distance,
   weighting and volume are the same for both phones, so they cancel.
3. Add the difference to our own S26 Ultra curve. The result is the phone's estimated curve in our measurement frame.

Script: `tools/pvb-harness/study/nbc_transfer.py` (reads the input tables from a private folder, not from the repo).

Why only differences: one reviewer's S26 Ultra curve differed from ours by 7-9 dB at 125-160 Hz and 5-10 dB at
2.5-6.3 kHz. Differences between phones are far more trustworthy than any lab's absolute curve.

## Check of our own S26 Ultra measurement

Our curve was compared with an independent lab's measurement of the same phone (third-octave, 125 Hz-8 kHz; above
10 kHz the setups differ: phone on a desk here, free-standing there). Agreement: mean absolute difference about 1.8 dB;
among about 60 phones in that lab's data, our curve was closest to its S26 Ultra, followed by the S26+ and S25 Ultra.
Caveat: the band limit was chosen after seeing the data. Good enough to use as the reference, not a proof.

## Aggregate result (92 Android phones, one reviewer)

| Quantity | 10th percentile | Median | 90th percentile (weakest) |
|---|---|---|---|
| Frequency where the response is 10 dB below the mids | 156 Hz | 204 Hz | 242 Hz |
| Bass 125-250 Hz, re the S26 Ultra | -5.1 dB | +0.3 dB | +4.7 dB |
| Low-mid 200-400 Hz, re the S26 Ultra | -1.9 dB | +1.7 dB | +5.4 dB |

- Most phones, budget models included, reach about the same low-frequency limit as the S26 Ultra; 90 % are 10 dB down
  at or below about 240 Hz.
- Galaxy phones as a family sit close to the S26 Ultra (most within ±5 dB at 125-250 Hz), so the S26 Ultra profile's
  EQ shape suits Galaxy phones in general. Treble varies far more between phones (about -12 to +8 dB) than bass.
- Two labs disagreed about one Galaxy generation's bass; per-model starting values wait until that kind of
  disagreement can be checked with our own measurement.

## In the app: the EQ story (home/BassStory.kt)

The story draws per-band aggregates only (dataset as of 2026-10-24: 97 Android phone curves, 7 iPhones, same
reviewer): the 10th/50th/90th percentile of the Android phones and the median of the iPhones, plus our own S26 Ultra
curve. iPhones (median): 125-250 Hz about +7 dB re the S26 Ultra; 10 dB under the mids at about 155 Hz (Android
median about 205 Hz; about 1 Android phone in 10 reaches that low); still about -14 dB at 125 Hz. Seven phones: a
rough comparison. Cross-check with the independent lab (5 iPhones, 54 Android phones, 100 % volume, 50 cm):
iPhones 125-250 Hz about +5.5 dB over the Android median (about 1 in 10 Android phones as high), but only about
+1.4 dB over the S26 Ultra there (vs +7 dB in the reviewer's data); full-volume protection likely narrows it.

## Why the bass limit sits where it does (notes E and F)

- Phone speaker modules (about 11x15 to 18x16 mm) resonate at about 800-1100 Hz in the standard 1 cc test box
  (manufacturer datasheets; TI SLAA936: "often in the 700- to 1000-Hz range"). Adsorbent material in the back volume
  lowers that by about 110-200 Hz; teardowns show it in recent Galaxy Ultra speakers.
- A plain box at that resonance would be 20-28 dB down at 200 Hz. The S26 Ultra measures about -9 dB there, so the
  phone's own processing and the room add 10-19 dB. The low-frequency limit is set mostly by the maker's tuning, not by
  the part; datasheets give limits, not starting values.
- No phone maker or supplier publishes a per-model speaker response, resonance or frequency range.
- A physics-only class rule (flagship about 190 Hz, mid-range about 300 Hz, budget about 450 Hz) is more pessimistic
  than the measured phones; the measured distribution decides, the datasheets only bound it.

## The applied start (neutral profile)

| Setting | S26 Ultra (measured) | Unmeasured phones | Reason |
|---|---|---|---|
| `speaker_floor_hz` | 150 | 200 | Even the weakest 10 % of phones play little below this |
| `pvb_hp_hz` | 100 | 120 | Less energy where the speaker can't follow |
| `pvb_low_db` (220 Hz) | +3 | +2 | 200-400 Hz is at most about 2 dB below the S26 Ultra for 90 % of phones; kept under +3 to stay away from the buzz zone |
| `pvb_hi_db` (4.5 kHz) | -3 | -2 | Treble varies widely; a smaller cut is safer |
| Virtual bass | +4 | +0 | Unchanged policy for unmeasured phones |

## Open questions

1. Permission from reviewers/labs to publish per-model derived values (would allow per-model starting values).
2. One more phone measured our way (ideally a Galaxy S25 or S25+) to test the difference transfer directly.
3. User-shared measurements or settings codes, with consent, as a fully own data source.
