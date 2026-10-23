# F: Speaker modules (component-level specs) for Android phones

Researcher F. Goal: for each phone, the built-in loudspeaker module (maker, type, size, f0, frequency range,
SPL, back volume, stereo layout), from manufacturer datasheets, teardowns and official launch pages,
starting from Chinese-language sources. Review-site curves (A-D) and DXOMARK/papers (E) are out of scope.

Status: DONE for this pass (2026-10-23). Partial by nature: see Open gaps.

Confidence: A = manufacturer datasheet or official spec naming that model; 'A (relay)' = the OEM's or supplier's
own launch claim as reported by a press outlet; B = teardown (or service part) naming the part; C = inference,
leak or industry press (labelled). Component datasheet values are measured in a test fixture (baffle/box), not in the
phone; they are not the in-phone response.

## Source access log

- WebSearch is US-only; Chinese-language queries return few Chinese pages, and many hits are Sina mobile
  front pages (sina.cn/detail/...) whose fetched content is the portal home page, not the article. Not usable.
- pconline.com.cn: WebFetch refused (robots_disallowed). Not retried.
- goertek.com: home page fetched empty; product pages give categories only (no numbers).
- iFixit repair guides (Galaxy S24 Ultra, S25 Ultra): describe loudspeaker and earpiece removal but never name
  the speaker maker, part number or size. Chip ID guides list amplifiers (see below), not speakers.
- TechInsights teardown landing pages (S24 Ultra): component names behind paywall; speaker not named.
- The shell has no web access.
- Domain-restricted WebSearch (ithome.com, mydrivers.com, ifanr.com, zol.com.cn, qq.com, sohu.com, 163.com,
  sina.com.cn, 52audio.com) works much better for Chinese launch claims than open search; most rows below come
  from that route.
- k.sina.com.cn / cj.sina.com.cn articles: several returned 'article no longer exists' (deleted); not usable.
- mi.com spec page (xiaomi-15-ultra/specs) redirected to an error page; oneplus.com/cn and consumer.huawei.com/cn
  spec pages load but list only 'super-linear stereo dual speakers' / 'Histen, stereo' with no numbers.
- One ZOL review (Redmi K90) came back with corrupted character encoding; only the code '1115F' was readable.
- Samsung does not publish speaker specs; iFixit S25 Ultra Chip ID and S23 Ultra Chip ID name the amplifiers only.

## Sources

| # | Title / site | Year | Type | What it gives |
|---|---|---|---|---|
| S1 | IT之家 (ithome.com) 0/472/565, Xiaomi 10 launch | 2020 | press relay of official claim | Xiaomi 10/10 Pro: identical 1216 'linear' speakers top and bottom, 'equivalent 1.2cc' cavity, near-zero gain difference. https://www.ithome.com/0/472/565.htm |
| S2 | Raltron RSP-950.000-1511-NS1 datasheet | n.d. | component datasheet | 15x11x3.5 mm: F0 650 Hz free air -> 950 Hz in 1cc box (both ±20%); SPL 90/92 dB @0.1 m. https://www.raltron.com/webproducts/specs/SPEAKERS/RSP-950.000-1511-NS1.pdf |
| S3 | Raltron RSP-1050.000-1511-NS2 datasheet | n.d. | component datasheet | 15x11x3.6 mm: F0 1050 Hz ±20% in 1cc; 93 dB @0.1 m 0.7 W. https://www.raltron.com/webproducts/specs/SPEAKERS/RSP-1050.000-1511-NS2.pdf |
| S4 | Ole Wolff OWS-111535TA-8A / -LA-8H (LCSC mirror) | 2024 upload | component datasheet | 15x11x3.5 mm: F0 1000 Hz in 1cc; 1.0/1.3 W. URLs in CSV |
| S5 | Knowles 2403-260-00001 (eicom mirror) | 2011 | component datasheet (smartphone microspeaker) | 11x15x3.5 mm: F0 800 Hz ±7.5% in 1 cm3 closed back; 450 Hz typ in baffle; tolerance window 300 Hz-20 kHz; THD limits 25% @300 Hz, 18% @500-750 Hz. https://cdn.eicom.ru/media/PDF/3468456.pdf |
| S6 | ifanr Redmi K80 至尊版 hands-on | 2025 | press relay of official claim | two AAC (瑞声) 1115 coaxial speakers, top and bottom, diagonal outlets. https://www.ifanr.com/1627750 |
| S7 | Notebookcheck news, Redmi K80 Extreme Edition | 2025 | leak relay | '1115 coaxial common magnetic circuit', '+16 dB average SPL' (leaker), first used in Huawei Mate 70 RS. Leak only. |
| S8 | IT之家 0/816/818, vivo Y300 | 2024 | press relay of teaser | speaker co-developed with AAC (瑞声), no numbers |
| S9 | Extrabux CN guide 4390636 | 2020 | secondary summary of launch claims | Xiaomi 10 (1216, 1.2cc), Black Shark 3 Pro (1217), iQOO Z1 (1.05cc), Huawei Mate 20 X (earpiece same size as bottom speaker), Meizu 17, OPPO Reno Ace (no numbers) |
| S10 | ASUS ROG Phone 5s official spec page | 2021 | official spec | '7-magnet stereo speaker with Cirrus Logic amplifier', symmetric dual front-facing, Dirac |
| S11 | AAC Technologies acoustic product page (aactechnologies.com/product/acousticProduct) | current | manufacturer product page | SLS tiers by Xmax: Entry 0.4-0.5 mm, Classic 0.55-0.8 mm, Master >=0.65 mm, Coaxial 'Ultimate Speaker' >=0.75 mm; back-to-back (private call) 0.3 mm; Tmax 110-120 C; low-frequency 'EQ SPL' +3-4 dB per tier. No F0, no sizes. |
| S12 | audioXpress, AAC at CES 2024 | 2024 | trade press | AAC 'Opera' coaxial speaker in OPPO Find N3 (mass production): 8-20 kHz extension, '+5 dB low-frequency boost'; AAC acoustic+haptic combo in Redmi Note 13 Pro+ |
| S13 | audioXpress, AAC at CES 2025 | 2025 | trade press | 'Ultimate Speaker' (full-range coaxial microspeaker), coaxial stereo speaker in 'leading flagship smartphones' (unnamed). No numbers |
| S14 | 集微网 (laoyaoba) n/937117, Goertek phone speaker families | 2023? | trade press of Goertek launch | DPS-F (foldable top), 大音-F (foldable bottom, 1.5 mm unit / 2.1 mm module thickness), DPS 2.0 (bar phone top, larger Vdmax), 大音Ultra (bar phone bottom, '灵霄' architecture, +30% radiating area, 'low-frequency loudness more than 2x'). No models named |
| S15 | iFixit Galaxy S23 Ultra Chip ID | 2023 | teardown | 2x Cirrus Logic CS35L42 audio amplifiers, CS40L26 haptic driver; speaker not identified (one user comment claims an AAC SLS partnership, unverified) |
| S16 | iFixit Samsung Galaxy S25 Ultra Chip ID | 2025 | teardown | 2x Texas Instruments audio amplifiers (no part number), CS40L26 haptics; speaker not identified |
| S17 | iFixit S25 Ultra earpiece / motherboard guides; S24 Ultra screen+battery guide | 2024-2026 | repair guide | loudspeaker sits in a combined wireless-charging + loudspeaker assembly (6 screws); earpiece is a separate part with its own connector. No maker or size |
| S18 | infogoodman Samsung supplier list 2026; SK Securities / Daishin broker notes on EM-Tech (이엠텍) 2020 | 2020/2026 | industry/broker | EM-Tech supplies smartphone speakers and receivers to Samsung; Daishin (Nov 2020) says it was chosen 'main vendor for speakers and receivers' in the customer's H2-2020 flagship (customer and model unnamed; Samsung inferred from SK note) |
| S19 | COMSOL Conference 2014 (Bangalore), Zhang Zhenhui, Chinese R&D centre presentation | 2014 | conference talk | 18x13 mm speaker: f0 960 Hz @0.8 cc, 850 Hz @1.0 cc, 770 Hz @1.2 cc back volume; phone case study with 0.6+0.2 cc cavities |
| S20 | Goertek patents US10609471B2 (2015), CN111147987B (2020), US9699548 (2013) | 2013-2020 | patent (typical values) | speaker-module F0 ~1000-1090 Hz unfilled -> ~860-970 Hz with adsorbent; zeolite lowers F0 by 150-170 Hz; passive-radiator design F0 ~700 Hz, Fb 350 Hz |
| S21 | JRD/TCL US10613594B2 (2017); Nokia US9386134B2 (2013) | 2013/2017 | patent (typical values) | back volumes 0.36-0.43 cc (TCL), 0.43-0.55 cc (Nokia) |
| S22 | TI SLAA936A (TAS2563 tuning), TI SLAA765 (TAS2563 quick start, 2020) | 2020-2021 | smart-amp app notes | microspeaker resonance 'often in the 700- to 1000-Hz range'; selection range 200-1400 Hz; 3-band excursion/thermal protection with per-band priorities; Xmax examples 0.2-0.3 mm |
| S23 | NXP (S. Scarlett), eeNews Europe 'Achieving loud, rich sound from micro speakers' | 2012 | vendor article | Xmax 'typically around 0.4 mm'; conventional designs high-pass at ~1000 Hz; smart amp gave ~+10 dB bass on one phone (vendor test) |
| S24 | Awinic AW88261 datasheet V1.5 and product page | 2022 | smart-PA datasheet | 10.25 V boost, 5.2 W @1% THD+N into 8 ohm; current sense; HW AGC; no f0 values |
| S25 | 我爱音频网 (52audio) vivo X70 Pro+ teardown | 2021 | teardown | top speaker measured ~12 x 10 x 3.44 mm with particle-filled rear chamber; bottom box cover marking '264 GTK-SBS ...' |
| S26 | 中关村在线 ZOL 7841089 (Xiaomi 12 Pro) and 7820782 (AAC 2021 seminar) | 2021 | press relay of OEM/supplier claims | Xiaomi 12 Pro: 2 AAC SLS woofer boxes (0.65 mm, 0.8 cc equivalent back cavity) + 2 tweeter boxes; AAC 'master-level' SLS: 0.65 mm max amplitude (+85% vs same-size), LF loudness '+100%' |
| S27 | 快科技 mydrivers 751808 (Xiaomi MIX FOLD), 1011393 (OnePlus 13) | 2021/2024 | press relay | MIX FOLD: dual 1216, 0.65 mm, 1.34 cc equivalent, 15 V smart PA; OnePlus 13: AAC master-level bottom speaker, 0.65 mm |
| S28 | 腾讯新闻 (雷科技 2025-01-12; 2024-12-14; 硬哲学 2025-03-18) | 2024-2025 | press summaries | Honor Magic7 Pro (Goertek 1216 x2, 0.8 mm, '8cc'), vivo Y300 (AAC 1326D, 1222 mm3 unit, 4 cc), Xiaomi 10S (1216, 1.2 cc), Redmi K50 Gaming (2x1115 + 2x0611), iQOO 13 (1115E x2), Huawei Mate X2 (240 mg powder, 1.2 cc equivalent). 2025-01-12 article: flagships 'at most 0812 or 1112' units |
| S29 | Huawei Central (2025-04-12) | 2025 | press relay | Honor Magic7: dual 1216 symmetric, 1.6 cc |
| S30 | ifanr 1613732 (Galaxy S25 Ultra design/teardown) | 2025 | teardown article | S25 Ultra bottom speaker and top earpiece-speaker both contain white adsorbent particles; symmetric dual layout |
| S31 | The Elec (thelec.net) idxno=1630, 'Samsung Mobile secures more speakers from Korean firm' | 2020 | industry press | EM-Tech chosen speaker supplier for Galaxy Note20 series and S20 FE; Goertek and AAC had supplied TPE speakers to Samsung; EM-Tech earlier PEEK speakers |
| S32 | 快科技 / IT之家 (Black Shark 5 Pro 824213; Redmi Note 15 Pro 876467; realme 10 874276; K80 Ultra 1054194; K90 Pro Max 1081340; OPPO Find X8 Ultra 1041656; OnePlus 11 884551; realme GT8 Pro 890571; Honor Magic8 Pro 889748; vivo X300 Ultra 1109054) | 2022-2026 | press relay of OEM/supplier claims | size codes, amplitudes, cc figures; URLs in CSV |
| S33 | 腾讯新闻 2025-10-18 (Redmi K90 Pro Max preview) | 2025 | press | defines the size-code convention (1216 = 16 mm long x 12 mm wide; 1326 = 26 x 13 mm) |
| S34 | Same Sky CMS-15118C-SP; Hunston OSR1609EB/1511EB/1816E; Raltron 1712-NS1 datasheets | n.d. | component datasheets | see generic table |
| S35 | Cirrus Logic CS35L42 product page | current | smart-amp product page | 11 V Class-H boost, 5.3 W @1% into 8 ohm, 'speaker protection algorithms' (no detail) |

## Per-model table

Confidence: A = manufacturer datasheet/official spec page naming the model; 'A (relay)' = the OEM's or
supplier's own launch claim as reported by a press outlet (not read on the official page); B = teardown or
service-part evidence naming the part; C = inference. Size codes (1115, 1216, ...) are read as width x length in
mm: a 2025 Chinese press piece (腾讯新闻 2025-10-18) states 1216 = 16 mm long x 12 mm wide and 1326 = 26 x 13 mm.
'cc' figures are OEM 'equivalent' back volumes (often including adsorbent 'virtual' volume) unless stated.
No phone-level f0, SPL curve or frequency range was found for any named phone. Full rows and URLs in the CSV.

| Brand / model | Maker | Type / size | Back volume | Layout | Other numbers | Conf. |
|---|---|---|---|---|---|---|
| Samsung Galaxy S26 Ultra | not identified | bottom module service part GH96-20801A; no specs | - | bottom + earpiece (stereo) | - | B (part ID) |
| Samsung Galaxy S25 Ultra | not identified | bottom box and top earpiece-speaker both hold white adsorbent particles (ifanr) | - | symmetric bottom + earpiece | amps: 2x Texas Instruments (iFixit Chip ID, no PN) | B |
| Samsung Galaxy S23 Ultra | not identified | - | - | bottom + earpiece | amps: 2x Cirrus Logic CS35L42 (iFixit Chip ID); 'AAC SLS' only in a user comment | B (amp) |
| Xiaomi 10 / 10 Pro | n/s | dual 1216 'linear', identical top/bottom | 1.2 cc eq. | symmetric | - | A (relay) |
| Xiaomi 10S | n/s | dual 1216 | 1.2 cc | symmetric, Harman Kardon | - | A (relay) |
| Xiaomi CC9 Pro | n/s | - | 1 cc | - | 'loudness 2x prev gen' | A (relay) |
| Xiaomi MIX FOLD | n/s | 4 speakers incl. dual 1216 | 1.34 cc eq. | symmetric, screen side | 0.65 mm amplitude; 15 V smart PA '+40% loudness' | A (relay) |
| Xiaomi 12 Pro | AAC | 2x SLS woofer box (1115) + 2x tweeter box (0611), AME metal box | 0.8 cc eq. (woofer) | woofer+tweeter top and bottom | 0.65 mm; tweeters '>10 kHz' | A (relay) |
| Xiaomi 17 Pro Max | n/s | under-screen top earpiece-speaker, ring magnet (+20% magnet area) | 0.7 cc (top) | bottom + top earpiece | top '+4 dB vs prev gen' | A (relay) |
| Xiaomi 17 Ultra | n/s | - | - | bottom + under-screen top | - | A (relay) |
| Redmi K50 Gaming | n/s | 2x 1115 + 2x 0611 | - | two woofer+tweeter pairs | - | A (relay) |
| Redmi K80 Ultra (至尊版) | AAC | dual 1115 coaxial | - | symmetric top/bottom, diagonal outlets | leak: '+16 dB avg SPL' (not official) | A (relay) |
| Redmi K90 | n/s | '1115F' (page partly corrupted) | - | - | Bose tuning | A (relay), low |
| Redmi K90 Pro Max | n/s (Bose tuning) | 2x 1115 + '1620' bass unit by rear camera (2.1) | - | top/bottom + rear bass | - | A (relay) |
| OnePlus 11 | AAC | bottom SLS '1116E BOX' + top all-metal SLS box | - | bottom + top | 0.65 mm in small cavity | A (relay) |
| OnePlus 13 | AAC | bottom 'thin master-level' speaker | - | bottom + top | 0.65 mm | A (relay) |
| OPPO Find X8 Ultra / X8s / X8s+ | AAC | bottom SLS1115E | - | bottom + top | NLC algorithm 'LF clarity +100%' | A (relay) |
| OPPO Find N3 | AAC | 'Opera' coaxial speaker | - | - | 8-20 kHz extension, '+5 dB LF' | A (relay) |
| vivo X300 Ultra | vivo in-house | custom top '1697' upward-firing unit | 0.8 cc (top, 'near-pure air') | bottom + top | '300 Hz +4 dB vs prev gen'; smart-PA voltage +20% | A (relay) |
| vivo X70 Pro+ | bottom marked 'GTK-SBS' (Goertek? C) | top unit ~12 x 10 x 3.44 mm with particle-filled chamber | - | bottom + top | - | B |
| vivo Y300 (CN) | AAC | '1326D' unit (1222 mm3), rear-module position | 4 cc | 'three-way' | '600% volume' | A (relay) |
| iQOO 13 | n/s | dual '1115E' | - | symmetric | - | A (relay) |
| iQOO Z1 | n/s | dual 'super-linear' | 1.05 cc eq. | stereo | - | A (relay) |
| iQOO Neo 6 | n/s | - | - | bottom + earpiece-speaker | - | C |
| Honor Magic7 | n/s | dual 1216 | 1.6 cc | symmetric | - | A (relay) |
| Honor Magic7 Pro | Goertek | dual 1216, slanted | '8 cc' (conflicts; see note) | dual | 0.8 mm; 'LF +160%' | A (relay) |
| Honor Magic8 Pro | n/s | dual 1216 | '8 cc, industry's largest' | dual | - | A (relay) |
| realme GT8 Pro | n/s | 'full-cavity symmetric dual 1115E', N'Bass filler | - | symmetric | - | A (relay) |
| Huawei Mate X2 | n/s | dual, 240 mg 'Bass powder' | 1.2 cc eq. | dual | 'LF +180%' | A (relay) |
| Huawei Mate 20 X | n/s | earpiece = second speaker, same size as bottom | - | bottom + earpiece | - | A (relay) |
| Black Shark 3 Pro | n/s | dual 1217 'super-linear' | - | symmetric | - | A (relay) |
| ASUS ROG Phone 5s | n/s | '7-magnet stereo speaker' | - | symmetric front-facing | Cirrus Logic amp (CS35L45 per thelec 2021 for ROG 5) | A |
| Black Shark 5 Pro | n/s ('SLS' name suggests AAC, C) | dual 1216P 'SLS linear' | 1.5 cc eq. | symmetric | 0.8 mm; 2x 14 V smart PA | A (relay) |
| Redmi Note 15 Pro series | n/s | dual 1115 symmetric | - | symmetric | 'peak 82.5 dB' (no condition); '400% volume' | A (relay) |
| realme 10 series | AAC | 'classic SLS speaker BOX' | small cavity | - | 0.5 mm | A (relay) |
| Redmi K80 Ultra (leak) | AAC 'Ultimate Speaker' (coaxial, same as Huawei Mate 70 RS) | 1115 coaxial x2 | - | symmetric | '8-20 kHz +16 dB avg' | C (leak) |
| Samsung Galaxy Note20 / S20 FE | EM-Tech | - | - | - | Goertek/AAC had supplied TPE-diaphragm speakers to Samsung before (The Elec 2020) | C (industry press) |

Note on Honor '8 cc': Honor markets a 'dual open sound cavity' (Magic7). An 8 cc figure is far larger than any
sealed phone speaker box (0.4-1.6 cc in every other source); it most likely counts phone-interior air used as an
open back volume (inference C), so it is not comparable with the other cc figures. Huawei Central gives 1.6 cc for
the Magic7.

Counts: 36 distinct phone models or model groups (43 model rows in the CSV; some models have one row per
source). By best evidence per model: 1 at A (ASUS official page), 29 at 'A (relay)', 4 at B (Galaxy S26 Ultra
service-part ID, Galaxy S25 Ultra teardown observation, Galaxy S23 Ultra amplifiers only, vivo X70 Pro+), 2 at C.
None of the Galaxy B rows is a speaker spec. Only one row (vivo X70 Pro+ top unit) has a physically measured size.

## Generic module datasheets (bracket by size)

Phone OEMs buy custom boxes from AAC/Goertek/EM-Tech etc. whose datasheets are not public. The public parts below
are catalogue microspeakers of the same footprints, measured in the industry-standard 1 cc test box at 10 cm.
They bracket what a bare unit of a given size does; the phone box is custom.

| Size (mm) | Part (maker) | f0 free air / baffle | f0 in 1 cc | Other | Source |
|---|---|---|---|---|---|
| 11x15x3.5 | 2403-260-00001 (Knowles, 2011, 'for smartphones') | 450 typ (baffle, no back cavity) | 800 ±7.5% | 73 dB 1 W/1 m; THD limit 25% @300 Hz, 18% @500-750 Hz | S5 |
| 15x11x3.5 | RSP-950.000-1511-NS1 (Raltron) | 650 ±20% | 950 ±20% | 92 dB @0.1 m 0.7 W | S2 |
| 15x11x3.6 | RSP-1050.000-1511-NS2 (Raltron) | - | 1050 ±20% | 93 dB @0.1 m 0.7 W | S3 |
| 15x11x3.5 | OWS-111535TA/LA (Ole Wolff) | - | 1000 | 1.0/1.3 W | S4 |
| 15x11x3 | CMS-15118C-SP (Same Sky) | 500 typ (400-600) | 850 typ (723-978) | response Fo-10 kHz within ±10 dB; 88 dB @0.8 W 0.1 m | CSV |
| 15x11x3.0 | OSR1511EB (Hunston) | - | 850 ±20% | 94 dB @1 W 10 cm; range F0-20 kHz | CSV |
| 16x9x3.0 | OSR1609EB (Hunston) | - | 800 ±20% | 87 dB @0.5 W | CSV |
| 17x12x3.3 | RSP-1000.000-1712-NS1 (Raltron) | - | 1000 ±20% | 98 dB @1 W 0.1 m; THD <=10% @1 kHz | CSV |
| 18x16x3.7 | OSR1816E (Hunston) | - | 1100 ±20% | 103 dB @1.5 W | CSV |
| 18x13 | COMSOL case (Chinese R&D centre, 2014) | - | 960 @0.8 cc, 850 @1.0 cc, 770 @1.2 cc | f0 roughly proportional to 1/sqrt(V): box stiffness dominates | S19 |
| module | Goertek US10609471B2 (2015) | - | 1002-1092 unfilled -> 863-973 with adsorbent | adsorbent lowers f0 ~120-140 Hz | S20 |
| module | Goertek CN111147987B (2020) | - | zeolite lowers f0 by 150-170 Hz | - | S20 |

Derived (inference C): from the three parts with both a free-air/baffle and a 1 cc value, the equivalent
compliance volume is Vas ~1.1-2.2 cc (Vas = V((fc/fs)^2 - 1)). In a 0.8 cc sealed box these units would sit at
~870-1010 Hz; at 1.2-1.6 cc, ~690-910 Hz. Adsorbent fill ('Bass powder', zeolite, white particles) is worth about
120-170 Hz lower f0 (Goertek patents). Phone back volumes reported: 0.36-0.55 cc (older budget/Nokia patents),
0.7-1.6 cc (2019-2026 flagship claims, mostly 'equivalent' volumes including adsorbent).

Smart-amp vendor typical values (S22-S24): TI says microspeaker resonance is 'often in the 700- to 1000-Hz range'
and its selection guide allows 200-1400 Hz; Xmax examples 0.2-0.3 mm (TI) and 'typically around 0.4 mm' (NXP 2012);
AAC's current SLS tiers quote Xmax 0.4-0.5 (entry), 0.55-0.8 (classic), >=0.65 (master) and >=0.75 mm (coaxial
'Ultimate'); phone launch claims of 0.65-0.8 mm match the AAC classic/master tiers.

## Relation to bass limit

1. Bare-box model (textbook closed box, 2nd-order high-pass, 12 dB/oct below fc; computed here, inference C).
   The -10 dB point re the passband sits at 0.68 fc (Qtc 0.5), 0.58 fc (0.707), 0.53 fc (1.0). Measured re 1 kHz
   (which is close to fc for these boxes), the -10 dB point is:

   | box fc | Qtc 0.7 | Qtc 1.0 | level at 200 Hz re 1 kHz |
   |---|---|---|---|
   | 500 Hz | 284 Hz | 279 Hz | -16 dB |
   | 700 Hz | 380 Hz | 398 Hz | -21 to -23 dB |
   | 800 Hz | 420 Hz | 452 Hz | -22 to -25 dB |
   | 1000 Hz | 478 Hz | 531 Hz | -25 to -28 dB |

2. Check against the Galaxy S26 Ultra anchor. Our room measurement (UMIK-1, 30 cm, volume 60, phone_model.py
   SPEAKER_DB) is -8.9 dB at 200 Hz and -14.0 dB at 160 Hz re 1 kHz, so -10 dB lies near 190 Hz, with a shelf of
   -3 to -6 dB from 250 to 630 Hz. A sealed box with the f0 that every datasheet and vendor source points to
   (700-1000 Hz; even 600-850 Hz after adsorbent) would put -10 dB at 340-530 Hz and be 20-28 dB down at 200 Hz.
   The measured phone is 10-19 dB louder at 200 Hz than that. Even fc = 500 Hz leaves a ~7 dB gap.
   Reading (inference C): the in-room response at volume 60 includes the OEM's own low-frequency EQ in the
   smart amp / DSP (small-signal bass boost below f0, the usual smart-amp practice: NXP 2012 reports ~+10 dB bass
   from this), plus desk/room gain at 30 cm. The shelf from 250-630 Hz followed by a steep fall below ~200 Hz looks
   like an EQ-boosted box with a protective high-pass near 150-200 Hz, not a bare box.

3. Consistency with the protection we measured. For a sealed box at constant voltage, cone excursion is roughly
   flat below fc and falls above it, so any bass boost below fc raises excursion there. TI's protection is
   3-band with most excursion in the low band (S22). Our long loud sweeps lose 4-7 dB in 250-800 Hz (phone_model.py notes): that is
   the band from about 0.3 to 1.0 x a 700-900 Hz f0, i.e. exactly where boosted, excursion-limited content is
   expected. This supports f0 ~700-900 Hz for the S26 Ultra box (inference C, not a measurement of f0).

4. What this means for the -10 dB point of unmeasured phones: datasheet f0 and size do NOT predict it directly,
   because the OEM tuning EQ moves it by one octave or more. Size and back volume only rank phones loosely:
   1216/1217 with 1.2-1.6 cc and adsorbent > 1115 with 0.8-1.0 cc > 0811/0812 units in sub-0.6 cc
   (budget). A separate 1620 bass unit (Redmi K90 Pro Max) or a 1326 rear unit (vivo Y300) is a different class.

Candid view for the app: datasheet values can supply priors, not starting values. Useful priors:
(a) the excursion-sensitive band is about 250 Hz to f0 (f0 ~700-1000 Hz), so harmonics placed there at high level
will trigger smart-amp limiting (matches our S26 Ultra data); (b) real in-phone -10 dB points after OEM EQ cluster
far lower than bare f0 suggests (S26 Ultra ~190 Hz), so the auto-calibration should search a cutoff range of
roughly 120-350 Hz rather than derive it from f0; (c) larger 1216/1217 boxes with high cc claims justify a lower
initial cutoff guess than 1115 phones. The actual cutoff must come from the app's own measurement.

## Open gaps

- No f0, SPL curve, THD or frequency range was found for any named phone's speaker, from any source. OEMs and
  their suppliers (AAC, Goertek, EM-Tech) publish only size codes, amplitudes and 'equivalent cc' claims;
  custom-box datasheets are not public.
- Galaxy S26 Ultra: no supplier, size, back volume or amplifier identity found (only service part GH96-20801A).
  The S25 Ultra used two TI amplifiers (part number not given), the S23 Ultra two Cirrus CS35L42. The S26 Ultra
  amplifier could be identified on the device itself (amp firmware/driver names under /vendor, or the audio HAL
  dump) - not done here (no device access, and outside part F's remit).
- Samsung supplier history is only from 2020 industry press (EM-Tech for Note20/S20 FE; Goertek/AAC earlier).
  Nothing current for S24-S26 or the A/M/Z lines.
- Pixel, Motorola, Sony, Nothing: no module specs found (Sony pages are qualitative only). Researcher C's brands.
- Huawei Mate 70 / Pura 80: official spec pages say only 'Histen, stereo'; the Mate 70 RS coaxial unit is known
  only via leaks.
- 'cc' figures are not comparable across brands: 'equivalent' volumes include adsorbent, and Honor's 8 cc likely
  includes an open back volume. Size codes are footprints only (no height).
- Teardown outlets with BOM tables (eWiseTech, TechInsights, 52audio phone teardowns) are mostly paywalled or
  cover few phones; only the vivo X70 Pro+ teardown gave a measured size. pconline.com.cn was blocked by robots.
- Patents and catalogue datasheets give typical values only; they bracket bare-box f0 (700-1100 Hz in 1 cc), not
  the in-phone response after OEM EQ and protection.
