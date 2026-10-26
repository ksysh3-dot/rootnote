# P1+ research baseline — 2026-10-26

Provisionally adopted by the user as a research baseline, not an Android release.
Canonical identity: `p1plus-2026-10-26`, P1 profile 6 with research flags 6.
See [the decision and reproduction instructions](../../../docs/P1PLUS_BASELINE.md)
and [P1++ research](../../../docs/P1PP_RESEARCH.md).

The source used for the original measurements is based on
`4331423274665b6c16ca9d438389c289e39b92d4`. Publication was prepared against main
`b3c6fe47ee0c1720a43a6de2ae31efa6c80f0b24`; its added Bankstown attribution is
preserved. The DSP behavior was not tuned during naming/publication.

| Record | Meaning |
|---|---|
| `RESULTS_KO.md` | Original HQ v0.2 report, including adverse results |
| `summary.json` | Original summarized results; HQ/flags 6 now means P1+ |
| `hq-study.json` | Independent HPSS oracle, source-known mixtures, phase fixtures |
| `hq-engineering.json` | Explicit flags 6 and 14 checks at 44.1/48 kHz |
| `primary-envelopes.json` | Six input-defined main-harmonic envelope cases |
| `envelopes.json` | Earlier fixed-third-harmonic measurement, including failures |
| `am.json` | Preservation of legitimate amplitude modulation |
| `incremental-latency.json` | P1+ gains specifically over the phase-only control |
| `engine-regression.json`, `alpha2-regression.json` | Original host regressions |
| `legacy-controls-*.json` | Earlier synthetic controls and adverse changes |
| `music.json` | 29 files, 87 excerpts; output changes, not perceptual quality labels |
| `host-timing.json` | Host callback timing, not phone CPU/power |
| `baseline.json` | Canonical model, source and evidence hashes |
| `publication-checks.json` | Checks rerun on the publication source |
| `phase-only-control.patch` | Corresponding source for the historical flags-2 control |

Raw audio, processed copyrighted songs and workstation binaries are not stored
here. Source hashes and relative collection/file identifiers retain provenance;
absolute workstation paths were replaced with portable identifiers. Reports of
whole-song rendering and local WAVs describe local artifacts, not downloadable
files in this Git repository.

These cases informed development/selection; they are not an untouched final
perceptual validation set. Re-running them is a regression check. Android/UI,
physical speaker, listener preference, thermal and power validation are separate.
