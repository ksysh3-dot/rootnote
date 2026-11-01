# Confirmed S30 FULL host preset

`pvb_set_s30_full_research(engine, 1)` enables the entire S30 FULL research combo before the first processing call. `0` restores P1 controls. Invalid arguments return 0 without changes. Uncalled/default state is OFF.

Caller: P1 algorithm6, flags0, layer level0dB, output -5dB, 48kHz, fixed EQ, spatial/dynamics OFF. Preset: LR4 80Hz/-6dB dry shelf, cap4 layer, A peak control mode1/release100ms, fast21_onset phase12, peak-aware dry mode1 (original P1 shadow). Existing total latency7140samples, no added delay. Configure only before processing; live toggling/other sample rates are not established.

This API is in the host harness only. Existing research parameters stay OFF by default. No JNI/UI wiring or app behavior change. This is a reproducible research snapshot, not an app adoption. Verification/results: ~/r3a-dev/plan16/s47. No audio or user song metadata belongs in git.
