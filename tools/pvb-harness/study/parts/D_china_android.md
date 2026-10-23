# D: Chinese-market and emerging-market Android brands (work in progress)

Scope: Xiaomi, Redmi, POCO, OnePlus, OPPO, realme, vivo, iQOO, Honor, Huawei, Tecno/Infinix and other
Chinese/emerging-market brands. Values are RAW as each source shows them (dB re 1 kHz), no method offset applied.

Status: in progress. Sections below are filled as sources are checked.

## Source log (as checked)

- NotebookCheck (notebookcheck.net/.com/-cn): reviews have a "Speakers" section with a pink-noise frequency
  chart, but WebFetch truncates every review page tried (Xiaomi 17 Ultra, Xiaomi 15 Ultra, Redmi Note 14 Pro 5G,
  Mi Note 10 Lite, Mi Note 10 Pro TR) inside the benchmark tables, before the speaker section. No speaker text,
  chart or table could be read. The shell has no web access (proxy 403).
- DXOMARK audio (Xiaomi 13 Ultra page): has a "Music playback frequency response" graph (1/12 octave, sine,
  anechoic), but the graph data and image are not in the fetched page content. Only sub-scores and max SPL
  (71.4 dBA hip-hop, 69.4 dBA classical) are text. Not usable for FR.
