# E: papers, standards, DXOMARK and speaker-module data (structural prior)

Researcher E of 5. Collected 2026-10-23 with WebSearch/WebFetch only. GSMArena was not used.
Scope: sources that apply to many phones at once. These are microspeaker and receiver datasheets,
amplifier-vendor notes, papers, the Android CDD, Samsung and teardown statements, and DXOMARK's
protocol and per-model audio pages. Per-model review charts other than DXOMARK's belong to researchers A to D.

Convention: **[S]** marks what a source states. **[I]** marks my own inference or calculation.
"re 1 kHz" means dB relative to the level at 1 kHz.
The shared web-search budget ran out near the end of this work, so some leads in "Open gaps" were not followed up.

---

## 0. Short answer

* **[S] Bare driver in its test box.** Every phone-type microspeaker datasheet found gives a closed-box
  resonance f0 of **800 to 950 Hz in a 1 cc back volume**. That holds for 8 parts from 9x16 mm to 13x18 mm
  (table 1.1). The same drivers on an open-back baffle resonate at **425 to 650 Hz**.
  TI's smart-amp tuning guide says the resonance "is often in the 700- to 1000-Hz range".
  Maxim (now ADI) says about 1 kHz.
* **[S] Shape of the bare driver below f0.** The Knowles frequency-response tolerance windows (1 cc box, baffle)
  put **300 Hz about 20 dB below 1 kHz** at the window midpoints. The windows themselves are ±7 dB wide at 300 Hz.
* **[I] Footprint is not the predictor.** Driver footprint barely moves f0 in a fixed box. What moves it is back
  volume, including "virtual" volume from zeolite beads, and DSP.
  - Knowles states its adsorbent raises apparent back volume by up to 2x and shifts f0 by about 150 Hz.
  - Zeolite papers measure f0 drops of 111 to 200 Hz in 0.3 to 0.42 cc boxes.
  - A teardown report says the S26 Ultra speaker housing contains such beads.
* **[I] Bare physics fails on our anchor.** A closed-box model of a bare 1 cc driver (fc 800 to 900 Hz, Q about 1)
  puts the -10 dB re 1 kHz point at **450 to 500 Hz**. Our S26 Ultra measurement crosses -10 dB at **190 Hz**.
  So bare-driver physics misses the anchor by **about 1.25 octaves (range 1.1 to 1.5)**.
  The difference is acoustic (larger or virtual back volume) plus DSP bass EQ under smart-amp protection plus room.
  The sources do not allow the three to be separated.
  Maxim's marketing claim that its smart amp extends bass "to a quarter of the resonance frequency" (C confidence)
  would put that point at 200 to 250 Hz. That happens to be consistent with the anchor.
* **[I] Predictive rule.** A class rule with a ±0.5 octave band is given in section 3.4. Only the flagship value is
  anchored by a measurement. The mid-range and budget values are physics-based brackets that A to D's per-model
  data must confirm.
* **[S] DXOMARK.**
  - It publishes per-model playback scores (Timbre, Dynamics, Spatial, Volume, Artifacts), short bass comments and
    maximum SPL in dBA.
  - Each audio page has a 1/12-octave sine frequency-response chart measured in an anechoic box. The chart data
    could not be read through text fetching.
  - The newest audio tests listed are the Galaxy S24 series (March 2024). There are **no DXOMARK audio tests for the
    S25 or S26 lines**, and the S26 Ultra was tested only under the camera protocol.
* **[S] Android CDD.** It has **no low-frequency or bass requirement for the built-in speaker**.

---

## 1. Sources

Confidence: **A** means a primary document with stated conditions. **B** means a primary source whose
statement is general or whose device is a proxy. **C** means marketing, a blog, an indirect measurement or a
second-hand report. The same list is in `E_sources.csv`.

### 1.1 Microspeaker datasheets (phone-type drivers; IEC 268-5 / 60268-5 test conditions)

f0 is the closed-box resonance in the stated back volume. "Open" means open back on a baffle, which I use as a
proxy for free air.

| # | Part (maker) | Size mm | f0 in 1 cc | f0 open | Other stated data | URL |
|---|---|---|---|---|---|---|
| D1 | 2403-260-00001 (Knowles) | 15x11x3.5 | 800 Hz ±7.5% | 450 Hz typ. | Xmax ±0.30 mm. FR window at 10 cm, 1 cc, 350 mW (table 2.1). 73 dB 1W/1m (2-5 kHz) | https://cdn.eicom.ru/media/PDF/3468456.pdf |
| D2 | Donau Slim Enhanced 2403-263-00301 (Knowles) | 11x15x3.0 | 800 Hz ±10% | 425 Hz typ. | Xmax 0.68 mm p-p. FR window at 600 mW, same offsets as D1 | https://cdn.eicom.ru/media/PDF/440124.pdf |
| D3 | Fox 2403-260-00086 (Knowles) | 9x16x3.0 | 850 Hz ±10% (500 mW) | not given | 0.6 mm p-p. FR window at 10 cm (table 2.1) | https://cdn.eicom.ru/media/PDF/3450095.pdf |
| D4 | 1318 "Sambo" 2403-260-00058 (Knowles), rev D 2011 | 18x13x4.5 | 900 Hz ±7.5% (700 mW) | 500 Hz ±18% | 0.75 mm p-p. FR window at 1 cm, 1 cc, 700 mW (table 2.1). "300 Hz-3.4 kHz telecom" | https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2312201805_Knowles-2403-260-00058_C19422743.pdf |
| D5 | RSP-950.000-1511-NS3 (Raltron) | 15x11x4 | 950 Hz ±20% | not given | 94 dB at 0.1 m, 0.8 W, 2 kHz | https://www.raltron.com/webproducts/specs/SPEAKERS/RSP-950.000-1511-NS3.pdf |
| D6 | SP-1511S-5 (Soberton) | 15x11x4.8 | 900 Hz ±20% | 650 Hz ±20% (free air) | Operating range 300 Hz-5 kHz | https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2404031552_Soberton-Inc--SP-1511S-5_C3311184.pdf |
| D7 | BMS1813F-11C (Bestar) | 18x13x4.5 | 850 Hz ±20% | not given | Range "F0~20 kHz". Curves image-only | https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2404181020_BESTAR-ELECTRONICS-BMS1813F-11C-08H4-5-BBS152_C6132203.pdf |
| D8 | BOX1-18082-10C speaker box (PUI/CUI, driver BR1511) | box | 900 Hz ±15% | not given | Sensitivity measured with 0.6 cc. FR curve image-only (3.16 cm, 2.05 Vrms) | https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/2990/BOX1-18082-10C.pdf |
| D9 | LF-K2040B15A speaker box (seller page; maker unnamed) | 20x40 (name) | 700 Hz ±20% (in own box) | not given | "Range f0 to 20 kHz", 91 dB at 10 cm | https://dau-components.co.uk/product-catalogue/components/sounders-and-buzzers/micro-speaker/lf-k2040b15a-speaker-box/ |

Receivers (earpieces). A receiver is the part that becomes the second "stereo" speaker in most current phones.

| # | Part | Size mm | f0 | FR data | URL |
|---|---|---|---|---|---|
| R1 | RA receiver 2403-260-00041 (Knowles, 2011) | 10x4.8x2 | 520 Hz ±15% (open back) | Window at 1 cm, 10 mW, open back. Midpoints: 300 Hz about 75 dB, 600-700 Hz about 90, 2-4.5 kHz about 85 | https://cdn.eicom.ru/media/PDF/440384.pdf |
| R2 | Franklin 2403-260-00087 (Knowles) | 6x15x2 | 400 Hz ±12% | Coupler window re 1 kHz: 200 Hz -20 to -11, 400 Hz -9 to -1, 1.6-1.7 kHz +5 to +14, 6 kHz -26 to -10 (ear-coupler, not free field) | https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2312210921_Knowles-2403-260-00087_C19500798.pdf |
| R3 | RC-1206S-1 (Soberton) | 12x6x5 | not given | 110 dB at 1 kHz in an IEC 318 coupler. Curve image-only | https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2404031557_Soberton-Inc--RC-1206S-1_C3311432.pdf |

### 1.2 Amplifier-vendor documents

* **TI, "TAS2563 Tuning Guide", SLAA936A (Sep 2020, rev Mar 2021)** (B). https://www.ti.com/lit/pdf/slaa936
  - [S] "the resonance frequency is often in the 700- to 1000-Hz range" (section on crossover and multi-band compression).
  - [S] The default DRC crossovers are 400 Hz and 4 kHz, and the measurement microphone sits about 10 cm from the port.
  - [S] Its pink-noise response family (Figure 2-8) shows an EQ-only region at low levels, then hard limiting from
    protection and DRC at high levels. The figure is described in text only; there are no axis values.
* **Maxim/ADI, "Unleash the Full Potential of Your Micro Speakers" (2019-09-24)** (C, marketing).
  https://www.analog.com/en/resources/technical-articles/unleash-the-full-potential-of-your-micro-speakers.html
  - [S] Resonance is "quite high (~1kHz)".
  - [S] The DSM smart amp extends bass response "to a quarter of the resonance frequency (Fc)" and adds "+6-8dB SPL".
  - The same text appeared in Electronic Design (Mow, Tuason, Rossetti, 2019-08-12).
* **Cirrus Logic CS35L45 press release (audioXpress, 2021-03-24)** (C). https://audioxpress.com/news/cirrus-logic-introduces-new-cs35l45-smart-boosted-amplifier-for-mobile-devices
  - [S] Claims "higher bass", "bass precision" and "up to 30 percent higher peak loudness".
  - [S] It gives no Hz or dB figures and names no phones.

### 1.3 Papers

* **Jiang, Park, Xu, Hwang, "Analysis and Prediction of Mid-High Peak Frequency for Microspeaker with Side-Firing Front Chamber", Applied Sciences 13(2):1018, 2023** (A for that design).
  https://www.mdpi.com/2076-3417/13/2/1018/htm
  - [S] Smartphone-type side-firing module, measured at 10 cm with a 3.1 Vrms sweep from 100 Hz to 20 kHz at 1/12 octave.
  - [S] First peak (f0) "around 1 kHz", front-cavity Helmholtz peak 3.0 to 3.15 kHz, tube resonance about 15 kHz.
  - [S] Cavity air 156 mm³.
* **Chang & Wang, "Bass Extension of Microspeaker System on Mobile Device", J. Mechanics 35(4):487-498, 2019** (B; the device is a tablet).
  https://www.cambridge.org/core/journals/journal-of-mechanics/article/abs/bass-extension-of-microspeaker-system-on-mobile-device/2F765A1986D3D93F3D8A365ACC4C8A7A
  - [S] A pipe-shaped front port extended a 10-inch tablet's response "from 630 to 300 Hz" (abstract only).
* **Guo et al., "Acoustic Enhancement Performance of Hierarchical ZSM-5 Zeolites with Different Si/Al Ratios", Nanomaterials 15(11):797, 2025** (A for the stated cell).
  https://www.mdpi.com/2079-4991/15/11/797/html
  - [S] "Microspeaker 1115" with a 0.3 cc back volume and 0.06 g of zeolite. Δf0 ranged from 121 to 200 Hz depending on the sample.
  - [S] The sealed back enclosure "typically occupies approximately 40%" of a phone microspeaker module's volume.
  - [S] Measured per IEC 60268-5 in an anechoic chamber with SoundCheck.
* **Guo et al., "Aging Characteristics of ZSM-5 Zeolite on Low-Frequency Acoustic Applications", Nanomaterials 15(9):639, 2025** (A).
  https://www.mdpi.com/2079-4991/15/9/639
  - [S] 0.42 cc back volume: empty 928.85 Hz, with zeolite 797.72 Hz (Δ133 Hz, -14%).
  - [S] After aging, Δf0 ranged from -2 to 151 Hz depending on the contaminant. Acetic acid vapour removed the effect.
* **Moliner, Rämö, Välimäki, "Virtual bass system with fuzzy separation of tones and transients", DAFx-20, 2020** (B for virtual-bass parameters, not phone data).
  https://acris.aalto.fi/ws/portalfiles/portal/51973173/Eloi2020_Virtual_bass_DAFx2020.pdf
  - [S] Gives a cutoff of "about 100 Hz and 200 Hz in small loudspeakers" (not phones). The listening test was high-passed at 150 Hz.
  - [S] Suggested harmonic gain is 8 to 12 dB. The paper reports a trade-off between the amount of enhancement and distortion.
* **Berdich, Groza, Mayrhofer, Levy, Shabtai, Elovici, "Sweep-to-Unlock: Fingerprinting Smartphones based on Loudspeaker Roll-off Characteristics", about 2021** (C as FR evidence).
  https://www.aut.upt.ro/~bgroza/Papers/sweep-to-unlock.pdf
  - [S] About 3000 sweeps from 28 devices (12 models), including Galaxy J5, S7 Edge, Note 8, A21s, Tab S7, Xiaomi Mi A3 and Redmi 7A.
  - [S] The recorder was a car head unit at 1 m in a 3 x 3.7 x 2.5 m room, at 50 to 100% volume.
  - [S] They state the response was "poor below 700Hz and above 11kHz". There are no dB values.
* **Audiokinetic blog, "Loudness and frequency response on popular smart phones" (author Jie Yang, about 2016-2019)** (C, not peer reviewed).
  https://www.audiokinetic.com/en/blog/loudness-and-frequency-response-on-popular-smart-phones
  - [S] Four phones (iPhone 7 Plus, Huawei Mate 7, Vivo Y51A, Oppo R9 Plus) measured with white noise at maximum volume at 30 cm. The room is not stated.
  - [S] Android games "start rising at about 220 Hz"; the iPhone 7 Plus at about 400 Hz.
  - Charts not available as text.
* **R. H. Small, "Closed-Box Loudspeaker Systems, Part 1: Analysis", JAES 20:363-372, 1972** (standard theory; not fetched, cited via https://en.wikipedia.org/wiki/Acoustic_suspension).
  - I use the textbook relations fc = fs·sqrt(1 + Vas/Vb) and a 12 dB/octave second-order roll-off below fc.

### 1.4 Virtual back volume (adsorbent beads)

* **Knowles "N'Bass Virtual Back Volume", eeNews Europe 2012-02-19 and Elektor 2013-12-10** (C, press).
  https://www.eenewseurope.com/en/wp-json/wp/v2/posts/358262 and https://elektormagazine.com/news/miracle-material-doubles-speaker-volume-for-better-bass-response
  - [S] Raises the apparent back volume "by up to 100%".
  - [S] f0 changes by "about 150 Hz", with "approximately 3 dB" more SPL below resonance.
  - [S] Already in tier-1 smartphones in 2012.

### 1.5 Standards

* **Android CDD, section 7.8 Audio** (A). https://android.googlesource.com/platform/compatibility/cdd/+/refs/heads/main/7_hardware-compatibility/7_8_audio.md
  - [S] The only speaker frequency-response clause is conditional on near-ultrasound support: 7.8.3 [C-2-1], mean response in 18.5-20 kHz no lower than 40 dB below the response at 2 kHz.
  - [S] 7.8.4 has signal-integrity criteria with a 2 kHz sine. A mirror of the CDD lists the speaker THD < 3% and SNR >= 50 dB as SHOULD; I did not confirm the values in the official text.
  - **[S] There is no clause on low-frequency response or bass.**
* **Android CDD, section 5.5 Audio Playback** (A). https://android.googlesource.com/platform/compatibility/cdd/+/refs/heads/main/5_multimedia/5_5_audio-playback.md
  - [S] 5.5.2 [C-1-1] requires `EFFECT_TYPE_EQUALIZER` and `EFFECT_TYPE_LOUDNESS_ENHANCER` implementations.
  - [S] 5.5.3 recommends per-stream volume. It has no output-level or frequency-response requirement.
  - Latest CDD index: https://source.android.com/docs/compatibility/cdd (Android 17 is current).
* **IEC 268-5 / IEC 60268-5** is named by every datasheet above as its SPL method. I did not fetch the standard itself; it is paywalled.

### 1.6 Samsung build statements and teardowns

* **Samsung Newsroom ZA, "Bringing Stereo Speakers to Life", 2018-04-11 (Galaxy S9)** (C, manufacturer PR).
  https://news.samsung.com/za/bringing-stereo-speakers-to-life
  - [S] Added a second dynamic speaker at the top. The existing speaker was "enlarged by 1.5 times".
  - [S] The two speakers differ in size, so their levels were tuned to balance.
  - [S] It is "1.4 times (3-4dB) louder" than the S8. AKG tuning "expanded the bass range"; no Hz are given.
  - [S] Dolby Atmos is described as virtual surround.
* **Samsung Mobile Press, "Tech Lab Notes Part 2: Stereo Speakers", 2018-04-06** (C).
  https://samsungmobilepress.com/articles/tech-lab-notes-part-2-stereo-speakers
  - [S] Mentions AKG tuning and Dolby Atmos. There are no numbers.
* **Samsung Japan support FAQ on Dolby Atmos for Galaxy** (B for behaviour).
  https://www.samsung.com/jp/support/mobile-devices/how-to-set-up-dolby-atmos-for-galaxy
  - [S] Atmos "boosts quiet sounds" for a 3D effect. It may make background hiss audible in quiet places.
  - [S] It is greyed out on some mono-speaker devices unless earphones are connected.
  - [S] No frequency-response information.
* **Android Authority report of JerryRigEverything's Galaxy S26 Ultra teardown (2026-03)** (C, second-hand).
  https://www.androidauthority.com/samsung-galaxy-s26-ultra-teardown-3648568/
  - [S] Samsung "includes tiny internal balls inside the speaker housing designed to reduce the tinny sound".
  - [I] These are almost certainly adsorbent (zeolite-type) virtual-back-volume beads.
* **iFixit, Galaxy S26 Ultra teardown news (E. Chamberlain, 2026-03-24)** (checked).
  https://ru.ifixit.com/News/116328/samsungs-galaxy-s26-ultra-pairs-a-brilliant-display-with-a-brutal-repair
  - No speaker details. **No source found gives speaker-module dimensions or back volume for any Galaxy S24, S25 or S26.**

### 1.7 DXOMARK (protocol pages and per-model audio pages)

See section 4. Protocol pages:

* https://www.dxomark.com/what-we-test-audio/
* https://www.dxomark.com/a-closer-look-at-the-dxomark-audio-protocol/
* https://www.dxomark.com/how-we-test-smartphone-speaker-playback (2019-10-10)
* https://www.dxomark.com/audio-testing-insights-dxomarks-audio-clips (2020-07-15)

Per-model pages are listed in the table in section 4.3.

---

## 2. Findings: what the sources state

### 2.1 Bare driver frequency-response windows, re 1 kHz

These are window midpoints. The windows are tolerance limits, not measured curves. Each midpoint has an
uncertainty of ±(half the window width), which is ±4 to ±9 dB at 300 to 400 Hz.

| Part, condition | Low end | about f0 | 2-5 kHz | 9-11 kHz |
|---|---|---|---|---|
| D1/D2 11x15, 1 cc, 10 cm (1 kHz about 93.8 dB interpolated) | 300 Hz: **-19.8** (window -27 to -13) | 770-890 Hz: +0.7 | **-4.1** | 9 k: +1.7, 11 k: +5.7 |
| D3 9x16, 1 cc, 10 cm (1 kHz window 90-94.5) | 400 Hz: **-20.2** (window -29 to -11) | — | 2 k: -4.8 | 6 k: -3.8 |
| D4 13x18, 1 cc, 1 cm (850-1100 Hz window 116-123) | 300 Hz: **-25.5** (window -29.5 to -21.5) | 0 | 2-4 k: -4.5 | 7 k: -0.5 |
| R1 receiver 10x4.8, open back, 1 cm (re its 600-700 Hz peak) | 300 Hz: -15 | 0 | -5 | — |

[I] Every bare unit peaks near its f0 of about 0.8 to 1 kHz. They fall about 20 dB from 1 kHz to 300 to 400 Hz,
which matches a second-order closed box with fc 800 to 900 Hz and Q about 1 (table 3.2).
They sit 4 to 5 dB lower at 2 to 5 kHz than at 1 kHz.

### 2.2 How enclosure and adsorbent change f0

* [S] In D1 to D9, putting the driver in 1 cc instead of an open back roughly doubles f0: 425-650 Hz becomes 800-950 Hz.
* [S] Zeolite in 0.3 to 0.42 cc lowers f0 by 111 to 200 Hz, for example 929 to 798 Hz.
  Knowles claims up to 2x apparent volume and about 150 Hz.
* [S] On a tablet, a front pipe port moved the usable low end from 630 to 300 Hz (Chang & Wang).

### 2.3 Typical in-phone resonance (vendor statements)

* [S] TI: 700 to 1000 Hz. Maxim: about 1 kHz.
  Jiang 2023: first peak about 1 kHz, with a front-cavity Helmholtz peak at about 3 kHz in a side-firing module.

### 2.4 How much bass phones actually reproduce (cross-model statements)

* [S] Sweep-to-Unlock, 12 mostly budget and mid-range models, 2016-2020 era, recorded indirectly:
  "poor below 700 Hz and above 11 kHz".
* [S] Audiokinetic, 4 phones from about 2016: output "starts rising at about 220 Hz" (Android) and about 400 Hz (iPhone 7 Plus).
* [S] I found **no peer-reviewed paper with a set of measured smartphone loudspeaker frequency responses**
  (several phones, numeric low-frequency limits). The acoustic-fingerprinting papers I checked (Das et al. 2014;
  Han et al. 2021) give no low-frequency response data.
* [S] Volume dependence: TI's tuning guide and our own S26 Ultra notes (`phone_model.py`: 250-800 Hz 4 to 7 dB lower
  with long loud sweeps) agree. At high volume, protection removes bass first.
  Responses measured at maximum volume, as many reviews do, will show less bass than at moderate volume.

### 2.5 Galaxy-specific build

* [S] Since the S9, Galaxy flagships have a bottom main speaker plus a top unit. On the S9 Samsung called the top
  unit a second dynamic speaker of a different size, level-matched by tuning.
* [S] The S26 Ultra main speaker housing contains adsorbent "balls" (teardown report).
* [S] Samsung's own statements on AKG and Dolby give no frequency figures.
* [S] Dolby Atmos is described as "boosting quiet sounds". Our anchor was measured with Atmos off.
* [I] I found no source on the top unit's own response in the phone. A receiver-sized diaphragm (6x15 or 10x4.8 mm)
  in a small back cavity will contribute less bass than the bottom speaker.
  [I] On area alone, a receiver diaphragm moving the same distance as the main speaker would give roughly 6 to 10 dB
  less output at low frequency. So the bottom speaker sets the low-frequency limit.

---

## 3. Structural prior (all [I] unless marked)

### 3.1 Closed-box f0 versus back volume

Inputs:
* [S] Datasheet open-back f0 and 1 cc f0, and the textbook relation fc = fs·sqrt(1 + Vas/Vb).
* From these I back out Vas: about 2.2 to 2.5 cc for D1, D2 and D4, and about 0.9 cc for D6.

Predicted fc in Hz:

| Driver model | Vb 0.3 cc | 0.5 | 0.8 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|
| 11x15 type (fs 450, Vas 2.2) | 1289 | 1038 | 866 | 800 | 703 | 649 | 590 |
| 13x18 type (fs 500, Vas 2.2) | 1455 | 1170 | 975 | 900 | 790 | 728 | 661 |
| stiff 11x15 (fs 650, Vas 0.9) | 1311 | 1095 | 953 | 901 | 826 | 785 | 743 |

* Doubling the effective volume from 1 to 2 cc with adsorbent lowers fc by about 150 Hz.
  This matches Knowles' "about 150 Hz" independently.
* Bigger drivers do not get a lower fc in the same box, because Vas grows with the diaphragm. Across D1 to D8 the
  1 cc f0 is 800 to 950 Hz whatever the footprint.
  **Speaker dimensions alone are a poor predictor of the low-frequency limit. Back volume, adsorbent and DSP matter more.**
  Footprint mainly sets the excursion-limited maximum SPL in the bass. Those stated Xmax values are 0.3 to 0.38 mm peak.

### 3.2 Bare closed-box response re 1 kHz

Second-order high-pass with fc and Q:

| fc, Q | f(-6 dB) | f(-10 dB) | f(-15 dB) | 300 Hz | 200 Hz | 150 Hz |
|---|---|---|---|---|---|---|
| 650, 1.0 | 459 | 369 | 282 | -13.8 | -21.3 | -26.5 |
| 700, 1.0 | 496 | 398 | 304 | -15.3 | -22.7 | -27.8 |
| 800, 0.7 | 545 | 420 | 310 | -15.6 | -22.5 | -27.5 |
| 800, 1.0 | 563 | 452 | 346 | -17.6 | -25.0 | -30.1 |
| 900, 1.0 | 618 | 497 | 380 | -19.4 | -26.6 | -31.7 |
| 1000, 1.0 | 660 | 531 | 406 | -20.5 | -27.8 | -32.9 |

The 800 to 900 Hz, Q 1 rows reproduce the datasheet windows at 300 Hz (-17.6 to -19.4 against a stated midpoint of
-19.8) within their tolerance.

### 3.3 Check against the S26 Ultra anchor

* Anchor (`phone_model.py` SPEAKER_DB, in room at 30 cm, volume 60/150, Atmos off): crosses **-10 dB re 1 kHz at
  190.6 Hz**, -6 dB at 235 Hz and -15 dB at 154 Hz (log-frequency interpolation).
  It has a plateau of about -4.8 dB from 250 to 630 Hz.
* Fitting a second-order high-pass to the anchor's 125 to 315 Hz points, relative to that plateau, gives fc about
  **290 Hz, Q about 1.0**, rms error 1.35 dB.
* A bare 1 cc driver (fc 800 to 900, Q 1) would put -10 dB at 450 to 500 Hz.
  **Driver physics alone misses the anchor by 1.25 octaves (1.1 to 1.5 depending on the assumed fc and Q).**
  At 300 Hz the anchor sits about -6 dB re 1 kHz, against about -18 to -20 dB for a bare driver.
  That is **12 to 14 dB more relative bass**.
* Possible contributors. The sources do not allow a split:
  1. A larger and adsorbent-loaded back volume. The beads are confirmed in the S26U. On its own this could account
     for about 0.2 to 0.4 octave (fc 800 to 650 Hz).
  2. Smart-amp DSP bass EQ under excursion protection at moderate volume. Maxim claims Fc/4.
  3. Room gain and modes at 30 cm.
  4. 1 kHz may sit in a local dip of the phone's response. The anchor rises +11 to +16 dB toward 2.5 to 5 kHz,
     while bare drivers fall 4 to 5 dB there.
* Maxim's "to a quarter of Fc" (C) gives 200 to 250 Hz for Fc 800 to 1000 Hz. That is within about 0.4 octave of
  the anchor. It is a plausibility check, not an independent validation.

### 3.4 Proposed class rule (low-frequency limit as measured like our anchor)

f_x(phone) ≈ f_x(bare driver in its back volume) × 2^(−E). Here E is the extension in octaves from virtual or extra
back volume, DSP and room.

| Class (assumed hardware) | Bare fc | E (octaves) | f(-10 dB re 1 kHz) | f(-15 dB re 1 kHz) | Basis |
|---|---|---|---|---|---|
| Flagship: large bottom module, beads, smart amp (S2x Ultra type) | 650-900 Hz | 1.25 (1.1-1.5) | **190 Hz** (135-270) | **155 Hz** (110-220) | Anchored on the S26 Ultra measurement |
| Mid-range: stereo, about 1 cc, smart amp likely (A5x type) | 800-900 Hz | about 0.6 (0.25-1.0) | **300 Hz** (210-420) | **230 Hz** (160-330) | Interpolated. Not measured |
| Budget or older: about 1 cc or less, no beads, basic amp | 850-1100 Hz | about 0 to 0.25 | **450 Hz** (320-640) | **350 Hz** (250-500) | Bare-driver physics. Sweep-to-Unlock "poor below 700 Hz" is consistent |

* **Error band.** About ±0.5 octave (a factor of 1.4) on each value. On a 12 dB/octave slope that is about ±6 dB at
  a given frequency.
* Only the flagship row is calibrated by a measurement. The other two are physics brackets, and the class
  assignment itself is a guess per model.
* Expect E to shrink at higher volume as protection engages. The values above are for moderate volume
  (60/150 on the S26U).
* A to D's per-model data are the test. If several mid-range phones measured at moderate volume land outside
  210 to 420 Hz, the mid-range E is wrong.
* **For settings (suggestion).** On the S26U, `speaker_floor_hz` = 150 equals the -15 dB point (154 Hz).
  The same rule would give about 230 Hz for an unmeasured mid-range phone and about 350 Hz for a budget phone.
  The flagship value of 150 to 155 matches the current neutral profile.
  The DXOMARK comments (section 4.3) rank the bass the same way: S2x Ultra "deep and powerful" against A33/A53/A54
  "limited", "lacks depth". They do not quantify it.

### 3.5 Tilt from 1 to 10 kHz (weak prior)

* [S] Bare drivers are 4 to 5 dB lower at 2 to 5 kHz than at 1 kHz and rise again at 9 to 11 kHz.
* [S] Side-firing modules add a front-cavity Helmholtz peak at about 3 kHz (Jiang 2023).
* [I] So structure predicts a presence peak somewhere around 2.5 to 5 kHz and a roll-off above about 8 to 10 kHz in
  the phone. The anchor has that shape (+10.7 to +15.7 dB at 2.5 to 6.3 kHz, -1.6 at 10 kHz, -12 at 12.5 kHz).
* [I] The size of the 1 to 4 kHz rise (+11 dB) cannot be predicted from structure. It depends on the cavity, port
  and tuning. **For unmeasured phones I would not move the treble EQ away from flat on structural grounds alone.**

---

## 4. DXOMARK: what it does and doesn't publish

### 4.1 Protocol, as DXOMARK states it

* Introduced October 2019. Audio = Playback (70%) + Recording (30%).
* **Playback attributes:**
  - Timbre: bass, midrange, treble, tonal balance, "extensions for low- and high-end frequencies", resonances.
  - Dynamics: attack, bass precision, punch.
  - Spatial.
  - Volume: maximum, minimum and consistency.
  - Artifacts.
* **How scores are produced.** Scores combine perceptual evaluation against up to five other devices and studio
  monitors in a treated room with objective tests in an anechoic box. DXOMARK says about 20 of 30 test hours are
  perceptual.
  The scoring algorithms are internal, the scale is open-ended, and the weighting of perceptual against objective
  results is not disclosed.
* **Objective tests:**
  - Frequency response and THD+N at "soft, nominal and maximum" levels. The levels are not given in dB.
  - SPL per volume step with pink noise.
* **Conditions stated on device pages:**
  - Frequency response: "1/12 octave frequency response ... pure-sine wave in an anechoic environment". No distance
    or level is given.
  - Volume consistency: correlated pink noise, anechoic box, on-axis at 0.20 m.
  - THD at maximum volume: 0 dBFS sweep, anechoic box, 40 cm.
  - Comparison recordings: 60 LAeq, anechoic, A-B microphone pair at 30 cm.
* **Not defined anywhere I found:** numeric bass, mid and treble band edges.

### 4.2 What this means for us

* **Timbre score.** A perceptual composite on an open scale without published conditions, and C confidence as a
  frequency-response proxy. It spans only 117 to 135 across the phones below and does not track bass extension.
  The A33 and A53 (128) score the same as the S23 FE (127), while the comments differ.
* **Bass comments.** Qualitative and useful for ranking only.
* **Max SPL in dBA.** Two music tracks at maximum volume. All phones checked fall within 72.3 to 75.1 dBA (hip-hop,
  including the iPhone references), so it says nothing about bass.
* **Frequency-response chart.** This is the one quantitative item. Each audio page has a 1/12-octave sine response in
  an anechoic box, apparently with comparison devices.
  Through text fetching the chart had no image URL and no embedded numbers, so it is probably rendered by script or
  lazy-loaded. **I could not read it.** It needs a browser capture (section 5). Its axis calibration and level are
  unknown until then.
* **Coverage ends at the S24 series (published 2024-03-15).**
  - The audio-review index (12 pages) lists the S24 (Exynos), S24+ and S24 Ultra as newest.
  - No S25, S26, Z Fold6/7, Z Flip6/7 or A55-and-later audio tests appear.
  - DXOMARK's own S26 Ultra article (2026-04-09) covers the camera protocol only.
  - [I] DXOMARK appears to have stopped publishing smartphone audio tests after about March 2024.
    I found no DXOMARK statement confirming this; the search budget ran out.
* **Carry-over caution.** The S24 Ultra and S23 Ultra pages show identical playback sub-scores (135/131/147/137/96),
  identical bass wording and identical maximum SPL (74.8/71.8 dBA). DXOMARK calls the S24U "very little changed".
  Treat the two as one data point.
  The A33 and A53 also share maximum SPL values (74.3/69.3).

### 4.3 Per-model DXOMARK data

Kept out of this public repository (third-party per-model data, research use only).

## 6. Open gaps

* **No multi-phone measured data set.** I found no published set of measured loudspeaker frequency responses for
  many smartphones with stated conditions and numeric low-frequency limits. The class rule therefore has one
  calibration point. A to D's per-model data must test the mid-range and budget rows.
* **Module data for actual phones.** No public source gives speaker-module size, back volume or f0 for any Galaxy
  S24, S25 or S26 (or other current phone). Teardowns (iFixit, JerryRigEverything via Android Authority) only note
  the beads. The amount of DSP bass boost Samsung applies by volume step is unknown.
* **Top unit (earpiece used as a speaker).** No in-phone response data. Its contribution to the stereo sum below
  1 kHz is unknown.
* **DXOMARK.** The frequency-response charts are unreadable as text. No DXOMARK statement was found on ending audio
  tests. There are no audio tests after the S24 series.
* **Room versus anechoic.** The anchor is speaker plus room at 30 cm. DXOMARK and the datasheets are anechoic or on a
  baffle. Below about 300 Hz the room can shift levels by several dB, and I did not quantify that here.
* **Not followed up after the search budget ran out:**
  - AES and JASA papers on mobile-phone microspeaker perception (Backman/Nokia era work, Klippel microspeaker notes)
  - Samsung or Apple patents giving back-volume numbers
  - whether DXOMARK still runs audio tests for some Chinese brands in 2025
* **CDD values.** The 7.8.4 speaker THD and SNR numbers came from a mirror and were not confirmed in the official text.

## 7. Checked, nothing usable for low-frequency response

* Das, Borisov, Caesar 2014, acoustic fingerprinting (https://ar5iv.labs.arxiv.org/abs/1403.3366): no frequency response.
* Han et al. 2021, IEEE TMC (https://par.nsf.gov/servlets/purl/10339849): 18 to 20 kHz only.
* PhoneMicBench dataset on IEEE DataPort: microphones only, paywalled.
* Akesbi 2022 thesis (arXiv 2212.11277): microphones and home speakers, not phone speakers.
* Zeman et al. 2010, IOA: iPhone microphones only.
* connect-testlab acoustics page: earpiece receive tests on an artificial head only.
* Sinelnikov et al. 2019, COMSOL: no numbers.
* DXOMARK "Audio matters" article: microphones and a reader survey.
* AES e-library pages: redirected to an unrelated paper, so not usable.
* NCBI PMC and Chalmers repository: not retrievable (reCAPTCHA / client error); I did not work around them.
