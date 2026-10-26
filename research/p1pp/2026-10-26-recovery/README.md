# P1++ recovery investigation v0.2

Read [the measured results and adverse changes](RESULTS_KO.md) and the
[prospective protocol](../../../docs/P1PP_RECOVERY_PROTOCOL.md).
P1+ remains the adopted research baseline. Mode 4 repairs the identified late
fade-recovery regression of mode 2. Early 0..80 ms and legitimate short-note
regressions remain; this is not an overall-quality approval or an Android change.

Build the host library with tools/pvb-harness/build_host.sh (Linux) or
build_host_windows.py (Windows with Zig 0.16). Install numpy, scipy and soundfile.
From repository root:

```sh
python tools/pvb-harness/research_p1pp_recovery.py --set inspected --out recheck/inspected
python tools/pvb-harness/research_p1pp_recovery.py --set new --out recheck/selection
python tools/pvb-harness/research_p1pp_recovery.py --set confirm --modes 0 2 4 --out recheck/confirmation
python tools/pvb-harness/check_p1pp_impact_controls.py --out recheck/controls
python tools/pvb-harness/render_p1hq.py --input /path/music.flac --output /path/experimental.wav --impact-mode 4 --peak-target -1
```

The optional --baseline for controls accepts a separate host library compiled
from frozen P1+ commit 8bec71f47bc1e85dcfddfcf362411347490c5119. Do not point it to
the same candidate and describe that as a historical comparison.
Music: research_p1pp_impact_music.py --modes 0 2 3 4 --test-folder ...
--album-folder ... --out recheck/music. Input-only selection, three-second preroll;
music differences have no noise ground truth.

Modes: 0 P1+, 1 all-current-fit diagnostic, 2 unconfirmed-track guard,
3 first-fit recovery, 4 recovery only after current and effective fits pass.
Mode 4 was selected using the 12-waveform selection cohort. A separate 8-waveform
confirmation followed without DSP changes. Levels are repeats, not independent
waveforms. The 8 inspected waveforms are development data. Full pre/early/late,
attack, note and AM outcomes remain in the JSON files.

input-features-recomputed.json corrects descriptive input FFT truncation in the
inspected raw results only. Rendered audio and residual metrics did not change.
The original music.json metadata's 'per pair' wording refers to one common gain
per event across all four variants. No listening verdict is asserted.

The separate Windows code/measurement and short-excerpt bundles were delivered
locally in the research chat. DLLs, NPZ traces and music are not committed here.
The default host mode remains 0; no JNI/UI binding was added for these modes.
