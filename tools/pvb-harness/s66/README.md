# s66 phone-aware allocation research (local only)

Base9d408fb. This directory contains startup-only/default-off host controls and
reproduction scripts. No room recording, original music, rendered song audio,
private report, dataset, model result, app build or release is committed here.
The three controls are C1 ratio allocation,C2 burst-history allocation and C3
band allocation. The pre-existing20ms-release T is a diagnostic comparator.
Native latency stays7140 samples. Live mode transitions are not a supported API.

Authoritative frozen protocol, correction chronology, fits and results live in
`~/r3a-dev/plan16/s66/`. Read REGISTRATION.md/json,MODEL_CORRECTION_v2*,
MODEL_DOMAIN_v21*,CORRECTIONS,NA_CORRECTION and PREFETCH_* before interpreting
anything. Original V1 and intermediate uncensored V2 results remain preserved.
The final model fails screening; no transferred efficacy/adoption is established.

Environment: Ubuntu-24.04 WSL,`~/venv-rootnote/bin/python`,CPU<=6 threads,
BLAS1. Scripts deliberately bind to the existing exposed DEV/frozen-helper
workspace and in-place listen paths. They never enumerate dataset validation/test.
No network install or playback is needed. Reproduction is an existing-workspace
workflow,not a standalone dataset distribution.

Fresh setup (before the local commit; do not overwrite an active experiment):
`python s66_setup.py` then `python s66_engine.py`.
Original fit: `python s66_phone.py`; preserve V1 before the exploratory correction
with `python s66_phone_v2.py`. The current v2 module applies the separately
registered v2.1 restriction: exclude the unidentifiable input component<150Hz.
It does not predict fundamental preservation or low-frequency phone response.
Run `python s66_validate_v2.py` to test the actual reconstructed waveform.

Verify native controls with `python s66_eval.py --proof` and
`python s66_eval.py --thread-proof`. Run at most these two worker commands:
`python s66_eval.py --rest --shards 2 --shard 0`
`python s66_eval.py --rest --shards 2 --shard 1`
Each worker has a main scoring thread and two native prefetch threads; each uses
three CPU affinity slots. The original serial implementation is preserved in the
work directory. All weak-mask absence is N/A,not zero or silent exclusion.
Then `python s66_summary.py`, `python s66_detail.py`, `python s66_qa.py`.
The QA rebuilds to build_final without overwriting the evaluated shared library,
and checks final host PCM identity and native syntax without the research macro.
This native syntax check is not an Android app build.

Prepare only: `python s66_kit.py`. This writes the synthetic247s WAV,map,Korean
measurement instructions and analyzer to Windows`rootnote-duo/listen/s66/`.
There is no playback call. Analyzer usage:
`python analyze_s66.py /path/to/recording.wav --out /path/to/s66_analysis`
The waveform contains independent silence,12 sync chirps,tone steps/bursts,
identical/+4 controls and5s identical recovery probes after loud/quiet conditions.
Run the analyzer on the synthetic WAV only as a digital fixture; actual15cm
acquisition is a future user mic session. Noise floor,SNR,clipping and affine
clock checks precede tone-level and phenomenological recovery interpretation.

`python s66_plot.py` creates diagnostics; `s66_report_write.py` writes the Korean
report/section outside git after LOCAL_COMMIT.json is recorded. No push,merge,
CORE edit,private-repository commit or app integration is part of these scripts.
