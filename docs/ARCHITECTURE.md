# How Rootnote processes sound (current structure)

What runs where, who owns what, and in which order a sample is processed. Written from the code at the time of the
2026-10-23 code review and its fixes; when the code and this page disagree, the code is right and this page is
out of date. Symbols are named so they can be searched; line numbers are left out on purpose.

## 1. From a setting to the speaker

| Step | Where | What happens |
|---|---|---|
| Stored settings | `pvb_settings` (SharedPreferences), keys in `PvbSettings` | Written by the screens (home, advanced, developer mode, balance). |
| Settings as played | `PvbSettings.load` → `PvbBuild.finish` | Reads the stored values, applies the general build's caps (`SafeCaps.GENERAL`) and the first-run gate (nothing processes before the notice is confirmed). |
| What plays now | `PvbController.effective` | A blind comparison (s26u) wins: its condition is applied to the settings. Otherwise a temporary override (`PvbRuntime.devOverride`: developer mode, the spatial story, the balance screen) replaces them. Otherwise the settings as played. |
| Engine parameters | `PvbController.push` → `PvbEngineParams.encode` | `push` reads the Android state once into `PvbEngineParams.Inputs` (output device, volume, posture, rotation, comparison, measurement). `encode` (pure, no Android classes) builds the `FloatArray` of `PvbParam` values: processing on this route, matched bypass, the volume-linked virtual-bass level (`VolumeLevelLink`), the spatial mode from posture (landscape cancel, upright mono or split), the balance sign for the rotation, the comparison gate; its KDoc names the states kept apart (enabled, in the path, route allowed, processing, matched bypass). `push` then sends the array and publishes `PvbRuntime.status`. |
| Block route | `RootlessAudioProcessorService` audio loop, `JdspChain.route` | Per block: JamesDSP alone (PVB not in the path), PVB alone (no JamesDSP effect on, or a comparison, measurement, buzz diagnostics or speaker calibration runs), or JamesDSP effects then PVB. A test sound (`DevTestSound`) replaces the captured music before the route, so it takes the same path. |
| JamesDSP while PVB processes | `JdspChain.sealed`, `JamesDspBaseEngine` | Dynamic bass boost and analog modelling are sent as off and the JamesDSP output stage as neutral (0 dB, limiter out of the way); the stored JamesDSP settings are not touched and apply again when PVB stops. |
| Samples | `pvb_engine.cpp` `Engine::process` | Section 3. |

## 2. Modes and who owns them

| Mode | Started / ended by | What changes |
|---|---|---|
| Normal listening | the home switch (`pvb_enable`) | Stored settings as played. |
| Matched bypass ("끌 때 음량 맞춤") | `pvb_match_on_disable` | PVB off still plays the input at the matched loudness and the same latency. |
| Blind comparison (s26u only) | `LiveAbView` via `PvbRuntime.setAb` / `endAb` | Conditions replace the settings; output gate for mute and headroom; spatial only as the condition sets it (EQ v1.1: off; the spatial comparisons: the canceller or its matched M/S widener); JamesDSP out of the path. |
| Measurement (s26u research) | `PvbMeasure.run` sets `PvbRuntime.measuring` | Spatial off, loudness estimator held, JamesDSP out of the path. |
| Speaker calibration ("좌우 맞추기") | `SpatialBalanceActivity.previewBalance` / `clearOverride` | A temporary override (spatial on for the by-ear step, off and virtual bass off while measuring) and `PvbRuntime.calibrating` (JamesDSP out of the path). Nothing is stored before the by-ear "저장" or "값 지우기". |
| Developer mode preview | `DevModeActivity` | Temporary override while a control is held; engine meters on while visible. |

The full owner table (who writes, who clears, who reads, on which thread) is the header of `PvbRuntime`.

## 3. Inside the engine, per sample (current order)

| # | Signal | Operation |
|---|---|---|
| 1 | `xl/xr` | Input; non-finite samples become 0 (counted). |
| 2 | `alignedL/R` | Input delayed by the generator latency, so the dry path lines up with the layer. |
| 3 | `spatialL/R` | Spatial stage (`Xtc::tick`) on the delayed input: landscape cancel, or upright mono / two-way split, or (comparison only) the matched M/S widener, which adds 256 samples not reported as latency; not run at all when off. |
| 4 | `eqL/R` | Protective high-pass (two stages), low-mid bell, high bell, high shelf. |
| 5 | `layL/layR` | Virtual-bass layer: from the undelayed input (`xl/xr`) or, for models whose `VbModule::inputAfterEq()` is true (Bankstown), from `eqL/R`. Then the experimental trims. |
| 6 | `layL/layR` | Upright only, input-based models only: `Xtc::routeLayer` sends the layer where the music's low part goes (split: the low channel, +3 dB; mono: both). Models generating from `eqL/R` already follow the split. |
| 7 | `preLimitL/R` | `(EQ output + layer level × layer) × output gain`. |
| 8 | `limitedL/R` | Look-ahead limiter (its latency `lat`); the solo monitor has its own limiter. |
| 9 | `dryDelayedL/R` | Dry input delayed by `lat`; loudness matcher fed with dry and limited; matched bypass through its own limiter. |
| 10 | `yl/yr` | Wet/dry mix × fade × gate (comparison mute/headroom) × model switch fade; checked as float before writing (a non-finite or out-of-range block is silenced and the engine resets). |

Developer meters and diagnostic capture read along the way and never change the output.

## 4. Speaker calibration: what the measurement can and cannot say

`SpatialBalance` estimates "the left speaker is louder by" from the phone's two microphones (cross method). It
cancels the microphones' own sensitivity, not an asymmetric acoustic path: the leftover is
`10·log10((H_L0·H_L1)/(H_R0·H_R1))` dB for amplitude transfers H, which the recording cannot reveal. So
`Result.recordingConsistent` only says the recording was sound (enough bands, the two channels hear the speakers
differently, the repeated runs agree). The screen uses a consistent result only to place the by-ear slider; a
measured value is never stored without the listener's "저장".

## 5. Checks you can run

```bash
tools/pvb-harness/build_host.sh
python3 tools/pvb-harness/test_engine.py
python3 tools/pvb-harness/test_xtc.py            # spatial, balance, upright split and mono with virtual bass, low rates
tools/pvb-harness/jvm/run_jvm_test.sh            # needs KOTLINC and KOTLIN_STDLIB (see the script header)
```

CI (`.github/workflows`) runs the full list, then builds both APKs. Host checks do not cover the Android audio
path, a real phone's microphones or listening.

## 6. Known open points

- Speaker calibration: a mixed (beamformed) microphone pair or a per-channel level stage can pass as two
  microphones; the asymmetric-path error is undetectable (section 4). Both are why a measured value is never stored
  directly. No real phone has been checked.
- `PvbRuntime.devOverride` has no owner token: the last screen to set or clear it wins (safe while only one such
  screen is visible at a time).
- Not done from the 2026-10-23 refactor brief: tidying the service audio loop (R4).
