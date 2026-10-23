# F: Speaker modules (component-level specs) for Android phones

Researcher F. Goal: for each phone, the built-in loudspeaker module (maker, type, size, f0, frequency range,
SPL, back volume, stereo layout), from manufacturer datasheets, teardowns and official launch pages,
starting from Chinese-language sources. Review-site curves (A-D) and DXOMARK/papers (E) are out of scope.

Status: IN PROGRESS (written incrementally; partial results are kept).

Confidence: A = manufacturer datasheet or official spec naming that model; B = teardown naming the part;
C = inference (labelled). Component datasheet values are measured in a test fixture (baffle/box), not in the
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

## Per-model table

(filled as sources are checked)

## Generic module datasheets (bracket by size)

(filled as sources are checked)

## Relation to bass limit

(filled at the end)

## Open gaps

(filled at the end)
