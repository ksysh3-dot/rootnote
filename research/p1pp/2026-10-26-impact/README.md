# P1++ impact investigation, round 1

The fixed research baseline remains P1+ (8bec71f, flags 6). This round implements
two optional host counterfactuals: mode 1 requires current fit throughout; mode 2
requires it until a new track first earns permission. Both use the existing fit
threshold and preserve valid modulation fits. Neither is an Android option.

**Mode 2 is experimental, not adopted as P1+.** The strongest six fresh pitched
impacts improve 3.75..16.41 dB in the defined late stationary residual, with
-0.15..+0.32 dB attack-energy change and no added delay. A broadband case worsens
46.32 dB from -150.7 to -104.3 dBFS; pre-impact residual mostly remains and some
short-note envelope cases regress. Do not turn this into a universal noise score.

Read [RESULTS_KO.md](RESULTS_KO.md), [the protocol](../../../docs/P1PP_IMPACT_PROTOCOL.md)
and [the research direction](../../../docs/P1PP_RESEARCH.md).

## Reproduction

Build the host library using the existing builder. Python requires numpy, scipy
and soundfile. The default library is tools/pvb-harness/build/libpvbcapi.so on
Linux or pvbcapi.dll on Windows. --library can select another path.

```sh
python3 tools/pvb-harness/research_p1pp_impacts.py --out recheck/base --flags 6 --fresh
python3 tools/pvb-harness/research_p1pp_impacts.py --out recheck/new --flags 6 --impact-mode 2 --fresh
python3 tools/pvb-harness/check_p1pp_impact_controls.py --out recheck/controls
python3 tools/pvb-harness/render_p1hq.py --input /path/music.flac --output /path/experiment.wav --impact-mode 2 --peak-target -1
```

Omit --fresh for the development sweep, whose default flags are 0/2/6. Reproduce
the separate current-fit diagnostic with --impact-mode 1. To check independent
mode-0 bit equality, build the P1+ commit separately and supply its library via
check_p1pp_impact_controls.py --baseline /path/to/frozen/P1plus/library.
Without that argument the independent comparison is explicitly null, not passed.
The frozen-envelope regression still runs separately in CI.

For the eight input-selected music events, use research_p1pp_impact_music.py
--test-folder /path/TestSound --album-folder /path/RayarkCollection --out recheck/music.
Music output differences are not labeled noise reduction. Exact media is required
to repeat those renders; no recordings, processed music, DLLs or NPZ waveforms
are committed. Absolute workstation paths are not part of the public records.

## Records

- development-initial: original 60 P1/phase-only/P1+ settings, seed 2026102607.
- current-guard and new-guard-initial: 20 development settings for each option.
- development-baseline/new-guard: phase-projection clarification of the same cases.
- fresh-baseline/new-guard: seed 2026102608, 8 shapes at 4 levels, not 32 independent shapes.
- controls: 44.1/48 kHz engineering, six prior note fixtures, normal AM.
- music: eight events from four predeclared supplied files, plus limiter stress.
- engine-regression and p1plus-frozen-regression: 71/71 and frozen default behavior.
- summary and source-manifest: derived effects and source/library provenance.

Repeating a fixture after the metric clarification is not a new independent
sample. The clarification was recorded before inspecting fresh-case results.
No DSP constants changed after fresh evaluation. Window residual is a limited
synthetic objective; physical phone listening, thermal and OEM protection remain
separate evidence. The default impact mode is 0 and preserves P1+ output.
