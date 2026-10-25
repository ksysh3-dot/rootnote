# Open-source projects for Rootnote (beyond the AOSP APIs)

Status: 2026-10-25. Research note, nothing in the app changed. Companion to `docs/ANDROID_AUDIO_APIS.md` (platform APIs),
which this page does not repeat. Target phone: Galaxy S26 Ultra (Android 16).

Method. Every project was read from its own repository: a shallow clone of the default branch on 2026-10-25 (the
"last commit" dates below are the HEAD commit of that clone), its README, LICENSE file and the source files named in
the text. Hosts that the research tools could not reach are marked; claims that need them are "unconfirmed". Each claim
carries a source key in square brackets; the list is at the end.

Licence rule used here. Rootnote is GPL-3.0 (`LICENSE`). Code under MIT, BSD (2-, 3-clause, Clear), ISC, zlib,
Apache-2.0, LGPL-2.1-or-later, LGPL-3.0, GPL-2.0-or-later and GPL-3.0 can be included; AGPL-3.0 can be combined
through GPL-3.0 section 13 (`LICENSE`), but the AGPL terms then apply to that part. GPL-2.0-only code cannot be
included. Code without a licence, or of unclear origin, is "learn from only" or "do not use". This is not a legal
review, and the FSF licence list could not be read from here.

## Summary

- **Without root, the speaker path is closed.** `/dev/snd/*` is `0660 system audio` [aosp-ueventd] and the adb shell
  user (which is what Shizuku runs as) is not in the `audio` group [aosp-adbd]. So `tinymix` cannot open the mixer, and
  no amplifier control, calibration value (Re, F0) or V/I-sense stream is reachable. What the shell can do is identify
  the amplifier and read configuration: it may read `/proc/asound` and list `sysfs` directories [aosp-shell-te], and any
  app may read `/vendor/etc` (`docs/ANDROID_AUDIO_APIS.md`). On a Qualcomm PAL phone that includes
  `<speaker_protection_enabled>` and `<cps_mode>` in `resourcemanager_*.xml` [pal-rm].
- **Calibration lives in files a shell cannot read.** Qualcomm's HALs write the speaker resistance and temperature
  (R0, T0) to `/data/vendor/audio/audio.cal` (legacy HAL [qc-legacy-sp]) or `/data/misc/audio/audio.cal` (PAL
  [pal-sp-h]). Smart-amp drivers expose calibration only as ALSA controls (TI: "Amp RE Data", "Amp R0 Data" [tas2781])
  or firmware controls (Cirrus `calR`, `calAmbient` [cs-amp-lib]). A root build could read some of these; the general
  build cannot. None of the drivers read gives F0 directly.
- **The only open speaker protection model is a thermal one.** speakersafetyd is a two-time-constant coil/magnet
  temperature model driven by V/I sense [ssd-types]. Its code after 2.0.2 is GPL-2.0-only [ssd-readme], so it is
  learn-from-only except the MIT release 2.0.2. Sound Open Firmware's smart-amp component is a pass-through plus a
  vendor binary [sof-smartamp]. No open excursion model was found.
- **The biggest new idea is from scrcpy, and it is a research spike, not a plan.** A shell-identity process can
  register a dynamic `AudioPolicy` loopback mix that takes the music away from the speaker instead of copying it
  (`ROUTE_FLAG_LOOP_BACK` versus `..._RENDER`) [scrcpy-apc]. Run in a Shizuku user service, this could replace both the
  MediaProjection capture and the per-session muting. It needs hidden APIs and a second process, and apps that opt out
  of capture stay out [scrcpy-doc].
- **For the measurement side, three things are worth doing soon:** a REW API bridge in `tools/` (REW serves an OpenAPI
  spec on port 4735; automated sweeps need REW Pro) [rew-api]; an exponential-sweep deconvolution for the probe so
  harmonic distortion is separated from the response (pyfar has a reference implementation [pyfar-dsp]); and
  perceptual metrics in the harness (ISO 532-1 and ECMA-418-2 loudness and roughness in MoSQITo [mosqito]).
- **DSP libraries add little to the engine now.** The virtual bass algorithm is frozen (`docs/LAB_PLAN.md`,
  2026-10-23), and the engine's own FFT, resampler and limiter are bit-exact tested (`docs/PERFORMANCE.md`). The
  libraries below are kept as references for the harness, not as engine replacements.
- **One licence finding.** The Bankstown model (MIT, [bankstown]) is ported in `libpvb/pvb_vb.cpp` (`VbBankstown`,
  header in `pvb_vb.h`), but neither `NOTICE.md` nor `app/src/general/assets/licenses/THIRD_PARTY.txt` carries its
  MIT notice. MIT asks for the notice in "all copies or substantial portions" [bankstown]. Not changed here.

## Already used

Found by reading the build files, `app/src/main/cpp`, `tools/` imports and the licence list, code as of 2026-10-25.

| Component | Where | Licence | Notes |
|---|---|---|---|
| libjamesdsp (JamesDSP engine) | submodule `app/src/main/cpp/libjamesdsp` at `1b9f89d` (2023-11-24) of ThePBone/JamesDSPManager | GPL-3.0 (`NOTICE.md`) | The submodule is at that fork's HEAD [jdsp-pbone]. The original james34602 repository has no engine commits after 2023-11-23 (later commits only add a funding file) [jdsp-upstream]. Nothing new to take. |
| WDL FFT (Cockos, based on DJBFFT) | inside libjamesdsp, `jdsp/Effects/eel2/fft.c` | Cockos WDL notice (text not checked; unconfirmed) | Used by JamesDSP, not by `libpvb`. |
| libsamplerate | inside libjamesdsp, `eel2/numericSys/libsamplerate/` | BSD-2-Clause (`THIRD_PARTY.txt`, [lsr]) | Used by JamesDSP only. |
| bs2b crossfeed | inside libjamesdsp, `jdsp/Effects/bs2b.c` | not stated in the file header read (unconfirmed) | Headphone crossfeed, not speaker crosstalk cancellation. |
| dr_wav / dr_flac / dr_mp3 | inside libjamesdsp | public domain or MIT-0 | |
| Bankstown model | `libpvb/pvb_vb.cpp` `VbBankstown` | MIT [bankstown] | Ported, notice missing (see Summary). Upstream is at 1.1.0, last commit 2026-09-30 ("Avoid panic if initialized with zero sample rate") [bankstown]. |
| fdlibm sin/cos kernels | `libpvb/pvb_fastmath.h` | fdlibm notice (`THIRD_PARTY.txt`) | |
| Own FFTs | `libpvb/pvb_vb.cpp` (radix-2, 64/192/2048 points), `pvb_analysis.cpp` (8192 points), Kotlin `pvb/PvbMeasureMath.kt` and `pvb/BassFit.kt` (4096 and 16384 points) | GPL-3.0 | No FFT library in `libpvb`. |
| Own resampler, limiter, loudness proxy, crosstalk canceller | `pvb_vb.h` (polyphase to 3 kHz), `pvb_dsp.h` (`TruePeakLimiter`, `LoudnessMatcher`), `pvb_xtc.h` (RACE design, `docs/XTC_PLAN.md`) | GPL-3.0 | `LoudnessMatcher` says itself that agreement with ISO 532-1 "has not been established". |
| ISO 226:2003 data | `pvb/BassFit.kt` (threshold), `pvb/VolumeCompensation.kt` (slope), `tools/pvb-harness/vb5/common5.py` | standard values | |
| Shizuku API 12.2.0 | `buildSrc/.../AndroidConfig.kt`, `hidden-api-impl/.../ShizukuSystemServerApi.java` | Apache-2.0 [shizuku-api] | Calls the private `Shizuku.newProcess` by reflection; output is discarded. |
| HiddenApiBypass 4.3, Refine | `app/build.gradle.kts` | Apache-2.0 | |
| AutoEQ client | `api/AutoEqClient.kt`, `AutoEqService.kt` | talks to ThePBone/AutoEqApi (GPL-3.0 [autoeqapi]) | Headphone profiles from AutoEq data (MIT [autoeq]). Not speaker data. |
| Python harness | `tools/` | numpy, scipy, soundfile, matplotlib, pyloudnorm (MIT [pyloudnorm]) | Not shipped in the APK. |

Not used anywhere today: any ALSA, `/proc/asound`, `/vendor/etc`, `sysfs`, thermal-zone or logcat reading (grep over
`app/src` and `hidden-api-impl` found none), Oboe, an FFT library in the engine, any measurement-file format other than
the app's own CSV (`pvb/BassFit.kt` `MicCal`).

## Projects by area

### 1. Vendor and kernel code for the speaker path

#### What a non-root app can reach on Android 14-16

| Access | Rule (AOSP main) | Consequence |
|---|---|---|
| ALSA mixer `/dev/snd/controlC*` | `/dev/snd/* 0660 system audio` [aosp-ueventd]; adbd drops the shell to groups `AID_ADB, AID_LOG, AID_INPUT, AID_INET, AID_NET_BT, AID_NET_BT_ADMIN, AID_SDCARD_R, AID_SDCARD_RW, AID_NET_BW_STATS, AID_READPROC, AID_UHID, AID_EXT_DATA_RW, AID_EXT_OBB_RW, AID_READTRACEFS`, no `AID_AUDIO` [aosp-adbd] | `tinymix` fails for the shell (and so for Shizuku in ADB mode) by file permission alone. Root only. |
| `/proc/asound` | shell may read `proc_asound` files [aosp-shell-te] | Card names and PCM list readable through Shizuku. |
| `sysfs` | shell: `sysfs:dir r_dir_perms` and a few specific file types only [aosp-shell-te] | Directories (for example the drivers bound on the I2C or SoundWire bus) can be listed, which names the amplifier. Reading generic `sysfs` files is not granted by `shell.te` (vendor policy may differ; unconfirmed). |
| `debugfs` | shell gets only tracing parts [aosp-shell-te] | The Cirrus `debugfs` node [cs-amp-lib] and ASoC `debugfs` are out of reach. |
| `/vendor/etc` | readable by all domains (`docs/ANDROID_AUDIO_APIS.md`) | Vendor audio XMLs (mixer paths, PAL resource manager, effect lists) readable by the app itself. |
| Calibration files under `/data/vendor`, `/data/misc/audio` | no rule for the shell in `shell.te` [aosp-shell-te] (unconfirmed for the vendor policy) | Not readable without root. |
| Logs | shell has `AID_LOG` [aosp-adbd] | HAL messages about speaker protection can be read through Shizuku (whether the vendor logs them is unconfirmed). |
| Shell permissions | `MODIFY_AUDIO_ROUTING`, `CAPTURE_AUDIO_OUTPUT`, `CAPTURE_MEDIA_OUTPUT`, `MODIFY_DEFAULT_AUDIO_EFFECTS`, `MANAGE_AUDIO_POLICY`, `DUMP` and others [aosp-shell-manifest] | Enables the loopback capture idea (idea 10). `MODIFY_DEFAULT_AUDIO_EFFECTS` only attaches effects that are already installed, so it does not help without root. |

#### Qualcomm audio HAL and PAL

| Project | Licence | Last commit | What it shows |
|---|---|---|---|
| Legacy Qualcomm HAL in AOSP, `hal/audio_extn/spkr_protection.c` [qc-legacy-sp] | Apache-2.0 (file header) | main branch, date not read | Calibration file `/data/vendor/audio/audio.cal` holding `r0` and `t0` per channel, written only after a successful calibration; properties `persist.speaker.prot.enable` and `persist.spkr.cal.duration`; temperature from `libthermalclient.so` (client name "spkr"), valid -30 to 80 °C, 40 °C assumed on failure; calibration only after 30 minutes of speaker idle. |
| AudioReach PAL, `device/Speaker/src/SpeakerProtection*.cpp`, `inc/SpeakerProtection.h` [pal-sp-h] | BSD-3-Clause-Clear [pal-lic] | 2026-10-23, tag v1.0.3 | Calibration file `/data/misc/audio/audio.cal`; idle before quick calibration `MIN_SPKR_IDLE_SEC (60 * 3)`; safe temperature 40 °C; minimum resistance 7 Ω (Q24); mixer controls "SpkrLeft WSA Temp", "SpkrRight WSA Temp", "... PA Disable"; separate files for WSA883x, WSA884x, WSA885x amplifiers. |
| PAL resource manager configs, `configs/qcom/.../resourcemanager_*.xml` [pal-rm] | same | same | Per output device: `<back_end_name>` (for example `CODEC_DMA-LPAIF_WSA-RX-0`), `<speaker_protection_enabled>`, `<cps_mode>`, `<vbat_enabled>`. PAL looks for configs under `/vendor/etc/audio/sku_...` and `/vendor/etc` (strings in `resource_manager`). |
| AudioReach engine [ar-engine] | BSD-3-Clause (file headers) | 2026-10-22, tag v1.0.2 | Open modules: bass boost, virtualizer, popless EQ, multi-stage IIR, FIR, gain control, volume, resamplers, simple accumulator limiter. Speaker protection and multiband DRC are not in the open set. |
| AudioReach graph services `acdb/` [ar-gsl] | BSD-3-Clause (README) | 2026-10-24 | The ACDB (tuning database) parser and delta-file manager are open. Decoding a phone's tuning would still need the closed module parameter layouts (unconfirmed which modules a given phone uses). |
| Mainline Linux AudioReach driver, `sound/soc/qcom/qdsp6/audioreach.h` [linux-ar] | GPL-2.0 (kernel) | 7.4-rc1 merge, 2026-10-24 | `MODULE_ID_SPEAKER_PROTECTION` and `_VI`; operation modes normal, calibration, factory test, validation; VI channel map "[Vsense of ch 1, Isense of ch 1, ...]"; `r0_t0_selection`. |
| Qualcomm audio kernel on CodeLinaro [clo-audiokernel] | not stated on the page read | project page only | Exists (created 2020-11-21); file tree not readable from here (unconfirmed what it exposes). |

Learn from only in practice: PAL and the HAL run in the vendor audio server. Their value for Rootnote is knowing where
the data is and what the configuration keys mean.

#### Smart-amplifier drivers

| Driver | Source | Licence | What it exposes |
|---|---|---|---|
| Cirrus CS35L41 / CS35L45 (mainline) | `sound/soc/codecs/cs35l41.c`, `cs35l45.c` [linux-codecs] | GPL-2.0 | ALSA "Digital PCM Volume", "Analog PCM Volume", noise gate and amplifier mode controls; over-temperature warnings and errors only as kernel log lines; DSP firmware type `WM_ADSP_FW_SPK_PROT` (CS35L41). |
| Cirrus calibration library | `sound/soc/codecs/cs-amp-lib.c`, `include/sound/cs-amp-lib.h` [cs-amp-lib] | GPL-2.0-only | `struct cirrus_amp_cal_data { calTarget, calTime, calAmbient, calStatus, calR }`, written to firmware controls; stored in UEFI variables (PC platforms); a `cirrus_logic` `debugfs` directory. |
| Cirrus Android branches | CirrusLogic/linux-drivers, branches `v6.12-cs35l43`, `v6.12-cs35l45` (last commit 2026-04-15), `v6.18-cs40l26` and older [cirrus-ld] | GPL-2.0 | CS35L43 adds "DC Watchdog", "Amp Gain", "Delta Select", "Ultrasonic Mode" controls (`cs35l43.c`, branch `v6.12-cs35l43`). CS40L26 is a haptics driver. |
| TI TAS2563 / TAS2781 family (mainline) | `sound/soc/codecs/tas2781-i2c.c`, `include/sound/tas2781.h` [tas2781] | GPL-2.0 | Byte controls "Amp TF Data", "Amp RE Data", "Amp R0 Data", "Amp XMA1 Data", "Amp XMA2 Data", "Calibration Start", "Calibration Stop"; "RE" reads a runtime-Re register (`TAS2781_RUNTIME_RE_REG`). What TF and XMA mean is not documented in the file (unconfirmed). |
| TI TAS2764 / TAS2770 (mainline) | `tas2764.c`, `tas2770.c` [linux-codecs] | GPL-2.0 | "VSENSE" and "ISENSE" switches: the amplifier sends voltage and current as a capture stream. This is what speakersafetyd consumes. |
| NXP (now Goodix) TFA989x (mainline) | `tfa989x.c` [linux-codecs] | GPL-2.0-only | Bypasses the built-in "CoolFlux DSP" because no public information exists about it (comment in the file). No calibration. The vendor `tfa98xx` Android driver: no official repository found (unconfirmed). |
| Qualcomm WSA883x / WSA884x (mainline) | `wsa883x.c`, `wsa884x.c` [linux-codecs] | GPL-2.0-only | A `hwmon` temperature sensor "related to speaker protection" (comment). It is measured only while the power amplifier is off; while it plays, the last cached value is reported (`wsa883x_get_temp`). Android vendor kernels use their own copies (unconfirmed which). |
| Samsung kernel and platform sources | opensource.samsung.com | per package | The portal disallows automated reading (fetch refused, robots). Which amplifier and driver the S26 Ultra uses is unconfirmed; the phone checks below find out. |

#### Root and Magisk audio modules

| Project | Licence | Last commit | Notes |
|---|---|---|---|
| Audio Modification Library [aml] | MIT | 2023-07-24 (v5.1) | Merges several audio mods' copies of `audio_effects*.conf/xml`, `audio_*policy*`, `mixer_paths*.xml`, `mixer_gains*.xml`, `audio_device*.xml`, `sapa_feature*.xml`, `audio_platform_info*.xml`, `audio_configs*.xml` (file list in `post-fs-data.sh`); coordinates with a module named `acdb`. Useful as the convention the root build's module (stage 2 of `docs/ROOT_BUILD_PLAN.md`) should respect. The `acdb` module's source was not found (unconfirmed). |
| ViPER4Android app [v4a] | app not open source (README: "currently not open source") | 2023-03-11 | Skip. |
| ViPERFX_RE [v4a-re] | `module/LICENSE` is GPL-2.0 for the module scripts; the C++ sources carry no licence header; README: "a reverse-engineering project" | 2023-12-09 | Do not use or copy (origin is a reverse-engineered closed binary). |

#### Open speaker protection code

| Project | Licence | Last commit | What it gives |
|---|---|---|---|
| speakersafetyd [ssd-readme] | MIT up to 2.0.2, GPL-2.0-only after (README; `SPDX` lines in `src/*.rs`) | 2026-10-03, tag 3.0.0 | A daemon that reads V/I sense, runs a coil and magnet temperature model and lowers the gain near the limit (`src/types.rs`: `tau_coil`, `tau_magnet`, `tr_coil`, `tr_magnet`, `t_limit`, `t_headroom`; cooling while idle in `skip_model`). Per-speaker values in `conf/apple/*.conf` (for example coil time constant about 2-3 s, magnet about 60-190 s, limit 140 °C) [ssd-conf]. Learn from only (current code); the 2.0.2 release could be used under MIT. |
| asahi-audio [asahi-audio] | MIT up to 4.2, then GPL-2.0-or-later (README; `SPDX` in `conf/`) | 2026-10-07, v5.0 | A complete laptop speaker chain: Bankstown, then LSP loudness compensation, then per-speaker FIR convolution (`firs/*/graph.json`). Shows how Bankstown is tuned elsewhere (for example `amt 1.45`, `sat_second 1.35`, `sat_third 2.25`, `blend 0.67`, `ceil 200`, `final_hp 200`). |
| Sound Open Firmware smart amp [sof-smartamp] | BSD-3-Clause | 2026-10-23, v2.15.1 | Component frame only: pass-through or a vendor's prebuilt library (`MAXIM_DSM`); no open algorithm. |

What this means for Rootnote: the phone's amplifier firmware protects the speaker, using calibration Rootnote cannot
read without root. A feed-forward thermal estimate from Rootnote's own output (no V/I sense) would need coil
parameters nobody publishes for this phone; at most it is a logging experiment (idea 8).

### 2. DSP libraries

Context: virtual bass work is frozen until a better candidate wins blind comparisons (`docs/LAB_PLAN.md`). The engine
already has its own FFT, resampler, limiter and pitch tracking (phase-vocoder peaks and track assignment,
`pvb_vb.h`, `pvb_track_assignment.h`). So the useful role of these libraries is reference and test material.

| Area | Project | Licence (GPL-3.0) | Last commit / release | What it would give | Verdict |
|---|---|---|---|---|---|
| Pitch | aubio [aubio] | GPL-3.0 (compatible) | 2026-04-10; last tag 0.4.9 | C pitch methods `yin`, `yinfast`, `yinfft`, `mcomb`, `fcomb`, `schmitt`, `specacf` (`src/pitch/`), onset detection | Harness reference only |
| Pitch | librosa `yin`, `pyin` [librosa] | ISC | 2026-10-22 | Python pYIN for offline checks of tracked bass notes | Harness reference only |
| Pitch | Essentia [essentia] | AGPL-3.0 (combinable via section 13) | 2026-10-22; v2.1_beta5 | Large C++ MIR library | Reject (licence weight, size) |
| Pitch | CREPE [crepe] | MIT | 2024-08-19; v0.0.16 | Neural monophonic f0 | Reject on device |
| Pitch | PESTO [pesto] | LGPL-3.0 | 2025-10-15 | Small neural f0, streaming, ONNX export ("~0.7 ms inference"); "800x" fewer parameters than CREPE (README); trained for monophonic material | Reject on device; not built for bass in a full mix |
| Pitch | basic-pitch [basic-pitch] | Apache-2.0 | 2025-11-13; v0.4.0 | Polyphonic note transcription | Harness only, if ever |
| Loudness | libebur128 [ebur128] | MIT | 2021-02-14; v1.2.6 | BS.1770 / R128 in C with true peak | Optional dev-mode meter; harness already has pyloudnorm |
| Loudness | MoSQITo [mosqito] | Apache-2.0 | 2024-04-22; v1.2.1 | ISO 532-1 stationary and time-varying (`loudness_zwst`, `loudness_zwtv`), ECMA-418-2 loudness and roughness, DIN 45692 sharpness, tonality | Keep (harness, idea 5) |
| Loudness | deeuu/loudness [loudness-gm] | GPL-3.0 | 2019-08-08 | C++ Glasberg-Moore 2002 dynamic loudness, Chen 2011/2012, ANSI S3.4-2007 (`src/models/`) | Keep as a second model in the harness |
| Loudness compensation | LSP loud-comp [lsp-loud] | LGPL-3.0-or-later (file headers) | 2026-08-20; 1.0.35 | ISO 226:2003 and ISO 226:2023 contour tables (`include/generated/iso226/`) | Optional: compare 2003 and 2023 for `VolumeCompensation` |
| Resampling | libsamplerate [lsr], speexdsp [speexdsp], soxr [soxr], r8brain [r8brain] | BSD-2, BSD-3, LGPL ("LGPLv2" on the project page; file not read), MIT | 2026-08, 2025-07, 2019-11, 2026-09 | General resamplers | Reject (the engine's polyphase is exact for its two rates) |
| FFT | pffft [pffft], KissFFT [kissfft], PocketFFT [pocketfft], FFTW [fftw] | FFTPACK-style BSD, BSD-3, BSD-3, GPL-2.0-or-later | all active in 2026 | Faster FFTs | Reject for the engine (bit-exact own code); pffft is the candidate if the Kotlin 16384-point FFT ever matters |
| Limiter, DRC | LSP limiter [lsp-lim], x42 dpl [x42-dpl], SOF DRC and multiband DRC [sof] | LGPL-3.0, GPL-3.0, BSD-3 | 2026 | Look-ahead limiters with oversampling; WebKit-derived DRC (SOF, from Google) | Learn from only; own limiter is tested |
| Virtual bass | Bankstown [bankstown] | MIT | 2026-09-30 | Already ported | Already used |
| Virtual bass | Calf bass enhancer [calf] | LGPL-2.1-or-later | 2026-10-13 | `src/modules_dist.cpp` `bassenhancer_audio_module` | Learn from only (frozen) |
| Virtual bass | AudioReach bass boost [ar-engine] | BSD-3 | 2026-10-22 | `modules/processing/bassboost/lib/src/bassboost.c`, a vendor reference | Learn from only (algorithm not read) |
| Crosstalk | LCC [lcc] | MIT | 2024-06-12; 1.0 | RACE-style recursive canceller made "with guidance from Ralph Glasgal": fixed 32 µs delay, -2.5 dB feedback, -3 dB input, a centre mix, no band filters (`lcc_rtaudio.cpp`) | Keep as a harness comparison (idea 13) |
| Spatial | Spatial Audio Framework [saf], libmysofa [mysofa] | ISC core (some optional modules GPL-2.0), BSD-3 | 2026-01-03, 2026-09-08 | HRIR, SOFA reading, binaural renderers | Later only, for HRTF-based XTC design work |

### 3. Android audio app infrastructure

| Project | Licence | Last commit / release | What it gives Rootnote | Verdict |
|---|---|---|---|---|
| scrcpy [scrcpy-apc] [scrcpy-doc] | Apache-2.0 | 2026-10-08; v5.0.1 | `server/.../audio/AudioPlaybackCapture.java`: a shell-identity process builds `AudioMixingRule` (role players, usage rules), `AudioMix` with `ROUTE_FLAG_LOOP_BACK` (audio leaves the device output) or `ROUTE_FLAG_LOOP_BACK_RENDER` (keeps playing), registers it with `AudioManager.registerAudioPolicyStatic` and opens `createAudioRecordSink`. Android 13+; "Android apps can opt-out". | Research spike (idea 10) |
| Shizuku API [shizuku-api] | MIT (API repository) | 2025-05-29; changelog to 13.1.5 | `UserService` (bound service in a shell-identity process) and `ShizukuBinderWrapper`. 13.1.1 notes "Prepare to remove `Shizuku#newProcess`"; 13.1.5 fixes a crash "on Android 14 (for apps targeting Android 14)". Rootnote is on 12.2.0 and calls `newProcess` by reflection. | Keep (idea 2) |
| Shizuku app [shizuku] | Apache-2.0 (code; launcher icons restricted, README) | 2025-06-18; v13.6.0 | | |
| Oboe and OboeTester [oboe] | Apache-2.0 | 2026-10-05; tag 1.11.0 | OboeTester (`apps/OboeTester/docs/Usage.md`): Device Report (features, properties, paths, microphones), Data Paths (dead channels, broken input presets; through speaker and mic), round-trip latency through the speaker, glitch test. The latency analyzer (`LatencyAnalyzer.h`) is C++. The docs mention "latency caused by speaker protection". | Use the app as a phone check; Oboe for output stays rejected (`docs/ANDROID_AUDIO_APIS.md`) |
| RootlessJamesDSP upstream [rjdsp] | GPL-3.0 | 2026-07-25 (`60d25ae`) | HEAD equals the fork base in `NOTICE.md` | Nothing new |
| JDSP4Linux [jdsp4linux] | GPL-3.0 | 2026-10-01; 2.7.0 | Same engine on Linux | Nothing new |
| NoiseCapture [noisecapture] | GPL-3.0-or-later (file headers) | 2026-09-04; v1.3.2 | Phone SPL meter with calibration screens, among them calibration against a reference phone (`CalibrationActivityHost/Guest.java`) and a linearity test that plays white noise at stepped levels and compares third-octave levels (`CalibrationLinearityActivity.java`) | Learn from, code includable (idea 7) |
| phyphox [phyphox] | GPL-3.0 | 2026-09-04; v1.2.1 | Sensor and audio experiments app | Low |
| Audio spectrum analyzer [aa4a] | Apache-2.0 | 2018-03-06 | RTA app; A-weighting "not suitable for serious application" (README) | Low, unmaintained |
| Loopback latency app [loopback] | Apache-2.0 (`LoopbackApp/MODULE_LICENSE_APACHE2`) | 2018-12-12 snapshot | Audio loopback latency tool | Superseded by OboeTester |
| tinyalsa [tinyalsa] | BSD-3 | 2026-10-23; v2.0.0 | `tinymix` source; needs `/dev/snd` access (root) | Root checks only |
| AutoEq [autoeq] | MIT | 2025-07-20; 4.1.2 | Headphone data; its CLI fits parametric EQ to a target from any frequency-response CSV | Optional in `tools/` (fit speaker EQ from REW data) |
| Wavelet | no source repository found | | Closed app | Skip |

### 4. PC-side measurement tooling

| Project | Licence | Last commit / release | What it gives `tools/` |
|---|---|---|---|
| REW API [rew-api] | REW's own terms (closed program) | docs read 2026-10-25 | Start with `-api` (or from preferences), port 4735 (`-port`), localhost only by default, `-nogui` possible. OpenAPI at `localhost:4735/doc.json`. Endpoints for measurements, measure, generator, import (frequency and impulse response data), EQ, RTA, SPL meter, input levels. Arrays are Base64 of big-endian 32-bit floats. All GET methods work; "controlling REW to make automated sweep measurements requires a Pro upgrade license". |
| REW calibration files [rew-cal] | n/a (format) | | Text, "Only lines which begin with a number are loaded"; frequency, dB, optional phase; "Sens Factor =...dB" used for named USB mics (UMIK-1 among them); "Sensitivity -12.34 dBFS" for analogue mics. |
| pyfar [pyfar-dsp] | MIT | 2026-10-23; v0.8.1 | `pyfar/signals/deterministic.py` (`exponential_sweep_time`, `linear_sweep_time`, `magnitude_spectrum_weighted_sweep`), `pyfar/dsp/dsp.py` (`deconvolve`, `regularized_spectrum_inversion`, `minimum_phase`, `time_window`, `find_impulse_response_start`), `pyfar/dsp/filter/` (fractional octave bands, frequency weighting). |
| pyrato, sofar [pyrato] [sofar] | MIT | 2026-08 | Room acoustics parameters; SOFA files. |
| python-acoustics [pyacoustics] | BSD-3 | 2023-08-20; v0.2.6 | Octave bands, weighting; slow maintenance. |
| pyroomacoustics [pyroom] | MIT | 2026-07-17; v0.10.1 | Room simulation, beamforming. Low relevance. |
| MoSQITo, deeuu/loudness | see area 2 | | Perceptual loudness and roughness. |
| ViSQOL [visqol] | Apache-2.0 | 2025-05-17; v3.3.3 | Perceptual similarity built for codecs. Low relevance (unclear meaning for speaker processing). |

## Combinations and ideas (ranked)

"Companion" means an idea number in `docs/ANDROID_AUDIO_APIS.md`.

| Rank | Idea | Parts | Value | Effort | Risk | Verdict |
|---|---|---|---|---|---|---|
| 1 | Speaker-path report (identify amplifier and protection config) | Shizuku shell: `/proc/asound`, bus driver listings, `/vendor/etc` XMLs, `getprop`, logcat [aosp-shell-te] [pal-rm] + companion 2 | High | Low | Low | Keep |
| 2 | Shizuku user service for shell commands | Shizuku API `UserService` [shizuku-api] replacing reflective `newProcess` | High (enabler) | Low-medium | Low | Keep |
| 3 | Sweep deconvolution in the probe | exponential sweep + deconvolution (pyfar as reference [pyfar-dsp]), existing probe and mic chain | Medium-high | Medium | Low | Keep (developer mode) |
| 4 | REW API bridge in `tools/` | REW API [rew-api] + the app's validation sounds (`DevTestSound`) + adb | Medium-high | Low-medium | Low | Keep |
| 5 | Perceptual metrics in the harness | MoSQITo [mosqito], deeuu/loudness [loudness-gm] on recordings and engine output | Medium | Low | Low | Keep (tools only) |
| 6 | Root build: read amp temperature and calibration controls | `tinymix` as root, PAL control names [pal-sp-h], TI controls [tas2781] | Medium (root users) | Medium | Low (read only) | Later (root stage 3) |
| 7 | Volume step map by stepped noise | NoiseCapture linearity pattern [noisecapture] + companion 6 | Medium | Medium | Low | Keep if companion 2 shows a full-scale curve |
| 8 | Thermal logging with a feed-forward model | speakersafetyd model structure [ssd-types] + companion 7 + UMIK-1 level log | Low-medium | Low | Medium (parameters guessed) | Test only |
| 9 | Root module follows AML conventions | AML file patterns [aml], `docs/ROOT_BUILD_PLAN.md` stage 2 | Medium (root) | Low | Low | Keep |
| 10 | Capture by loopback policy from a shell process | scrcpy pattern [scrcpy-apc], shell permissions [aosp-shell-manifest], Shizuku user service | Potentially high | High | High | Research spike only |
| 11 | Licence notice for Bankstown | `THIRD_PARTY.txt`, `NOTICE.md` [bankstown] | Required | Very low | None | Do |
| 12 | ISO 226:2023 cross-check | LSP tables [lsp-loud] vs `BassFit.kt`, `VolumeCompensation.kt` | Low | Low | Low | Later |
| 13 | LCC in the XTC harness | LCC [lcc] as another modelled condition in `tools/pvb-harness/test_xtc.py` / `tools/xtc/race_design.py` | Low-medium | Low | Low | Keep (harness only) |
| 14 | Library pitch tracker as reference | aubio [aubio], librosa pYIN [librosa] | Low (frozen) | Low | Low | Harness only, if the freeze is lifted |
| 15 | Replace own FFT, resampler, limiter | pffft, soxr, LSP | None | Medium | Breaks bit-exact tests | Reject |
| 16 | Decode the phone's ACDB tuning | AudioReach graph services [ar-gsl] | Unclear | High | Medium | Reject for now |
| 17 | Raise speaker gain by mixer patches (Magisk) | AML-style `mixer_paths` edits | Negative | Low | Speaker damage, bypasses protection | Reject |
| 18 | Neural pitch or AGPL libraries on device | CREPE, PESTO, Essentia | Low | High | Size, licence | Reject |
| 19 | Use ViPERFX_RE code | [v4a-re] | | | Origin | Reject |

### 1. Speaker-path report

- What: one developer-mode screen (and a shareable text) that says which amplifier drives the speaker, whether the
  vendor config enables speaker protection, and where the volume curve lives. It joins the companion's idea 2 (volume
  curves from `dumpsys media.audio_policy` and vendor XMLs).
- Chain: through the Shizuku user service (idea 2): `cat /proc/asound/cards`, `ls` of `/sys/bus/i2c/drivers`,
  `/sys/bus/soundwire/drivers` and `/sys/bus/platform/drivers` filtered for amplifier names (cs35, cs40, tas, tfa,
  wsa, aw, max98, fs); from the app itself, read `/vendor/etc/resourcemanager*.xml` (PAL keys
  `speaker_protection_enabled`, `cps_mode`, `vbat_enabled`, `back_end_name` [pal-rm]), `mixer_paths*.xml`,
  `audio_platform_info*.xml`; `getprop` for `persist.speaker.prot.enable` [qc-legacy-sp]; logcat lines from a loud
  bass passage.
- Benefit: replaces assumptions in `docs/SPEAKER_ESTIMATES.md` ("protection behaviour ... assumed to behave like the
  S26 Ultra") with a fact for each phone that shares a report; tells whether the phone's protection is software in the
  DSP (PAL) or in the amplifier.
- Cost and risk: low; read only. File names differ by vendor; Samsung may not use PAL (unconfirmed).
- Verify: run the phone checks below by adb first; the report must print the same.

### 2. Shizuku user service

- What: a small AIDL service started with `Shizuku.bindUserService`, with one method that runs a fixed, whitelisted
  command and returns stdout, and the "destroy" transaction the README asks for [shizuku-api].
- Benefit: needed by ideas 1, 6 and 10; removes the reflective call to a method upstream plans to remove; moving to API
  13.1.5 also picks up the Android 14 crash fix for apps targeting 14 (Rootnote targets 34).
- Cost and risk: low to medium; the service runs as shell, so the whitelist matters.
- Verify: unit test of the whitelist; on the phone, compare output with `adb shell`.

### 3. Sweep deconvolution in the probe

- Today the probe plays a 40-500 Hz log sweep and reads band levels (`DevTestSound.kt`, `PvbMeasureMath.kt`). With an
  exponential sweep and its inverse filter, the recording splits into the linear response and separate impulse
  responses for the 2nd, 3rd ... harmonics (the method behind pyfar's `exponential_sweep_time` and `deconvolve`
  [pyfar-dsp]; harmonic separation itself has to be written).
- Benefit: an objective distortion-versus-frequency curve at the speaker's low end, from the phone's own microphone. It
  can cross-check bass fit step 1 (floor) and step 3 (break-up) in `docs/BASS_FIT_PLAN.md`, where today only the
  listener answers.
- Cost and risk: medium; the phone microphone's own distortion near a loud speaker is unknown (the companion's
  `getMaxSpl` check helps). Keep in developer mode.
- Verify: the same sweep measured by the UMIK-1 in REW (which also reports harmonic distortion); Python reference
  in `tools/` with pyfar.

### 4. REW API bridge

- What: `tools/rew_bridge.py` that starts each validation condition on the phone by adb, reads REW's RTA levels or
  captured data per condition, and imports the phone-mic results into REW as frequency-response data for overlay
  [rew-api].
- Benefit: repeatable UMIK-1 references for the S26 Ultra profile and for the mic match, without hand work.
- Cost and risk: low to medium. Automated sweeps need REW Pro [rew-api]; whether RTA control by POST is free is
  unconfirmed. Write the format from the OpenAPI file of the installed REW, not from memory.
- Verify: one condition by hand and by the bridge must agree within 0.5 dB per third octave.

### 5. Perceptual metrics in the harness

- What: compute ISO 532-1 time-varying loudness and ECMA-418-2 roughness (MoSQITo) and Glasberg-Moore loudness
  (deeuu/loudness) for engine outputs through the measured phone model, and for UMIK-1 recordings.
- Benefit: tests the `LoudnessMatcher` proxy against two published models (its header says agreement "has not been
  established"); a roughness number as a second opinion on break-up.
- Cost and risk: low; offline only. MoSQITo is slow-moving (last commit 2024-04).
- Verify: compare the matcher's gain with the gain that equalises ISO 532-1 loudness on the same 40 s set used in
  `docs/PERFORMANCE.md`.

### 6 and 8. Amplifier data and thermal model

- Root build (idea 6): read-only `tinymix` dump filtered for temperature, resistance and protection controls. On a
  PAL phone the names would be like "SpkrLeft WSA Temp" [pal-sp-h]; on a TI amplifier with a mainline-style driver,
  "Amp RE Data" [tas2781]. A rising Re during loud bass is the coil heating. Benefit: a real "the speaker is hot" signal
  for root users. Which controls the S26 Ultra has is unconfirmed.
- Rootless (idea 8): a two-time-constant thermal estimate from the processed output's low-band power, structured like
  speakersafetyd's `run_model` [ssd-types]; log it next to the companion's thermal headroom and a 15-minute UMIK-1
  level log. Do not tie bass to it unless the level drift follows it. Re-implement from the published model structure,
  or use the MIT 2.0.2 code.

### 10. Loopback capture from a shell process (research spike)

- What scrcpy shows [scrcpy-apc]: a shell process can register a dynamic policy whose mix takes players with the
  listed usages; with `ROUTE_FLAG_LOOP_BACK` they no longer play on the device, and the process reads them from an
  `AudioRecord` sink. Shell holds `MODIFY_AUDIO_ROUTING` and `CAPTURE_AUDIO_OUTPUT` [aosp-shell-manifest].
- Possible benefit: no MediaProjection, no per-session muting with `DynamicsProcessing` (`MutedAudioEffectFactory.kt`),
  possibly more usages captured.
- Costs and risks: hidden APIs called by reflection; the `AudioRecord` lives in the shell process, so either audio
  crosses processes (latency, buffering) or the engine runs in the user service; Rootnote's own output track must be
  excluded from the mix (an exclude-UID rule; unconfirmed that it works from shell); "apps can opt-out" still holds
  [scrcpy-doc]; Samsung's audio policy may differ (unconfirmed).
- Verify first, without code: on the S26 Ultra, `scrcpy --no-video --audio-source=playback` while music plays. If the
  speaker goes silent and the PC hears the music, the mechanism works on this phone. Then the same with Rootnote on, to
  see whether its track is captured too.

### Rejected, briefly

- Library FFT, resampler or limiter (15): the engine's versions are bit-exact checked across builds
  (`docs/PERFORMANCE.md`); a swap gains little speed and loses that guarantee.
- ACDB decoding (16): the parser is open [ar-gsl], but parameter layouts of the modules that matter (protection,
  multiband DRC) are not in the open engine [ar-engine]; the phone may not use AudioReach ACDB at all.
- Mixer gain patches (17): they act after the vendor tuning and around the protection; a speaker app must not do this.
- ViPERFX_RE (19): reverse-engineered from a closed binary, no source licence.

## Checks to run on the phone

USB debugging on, Rootnote and other effects off unless stated. "Expected" is what the AOSP rules above predict; the
vendor can change it. Save each output; none of it changes the phone.

1. Sound cards (shell can read `/proc/asound` [aosp-shell-te]):
   `adb shell cat /proc/asound/cards /proc/asound/pcm`
2. Mixer access (expected: `tinymix` missing or "Permission denied", because `/dev/snd/*` is `0660 system audio`
   [aosp-ueventd] and the shell has no `audio` group [aosp-adbd]):
   `adb shell ls -l /dev/snd`; `adb shell which tinymix tinycap tinyplay`; `adb shell tinymix`; `adb shell id`
3. Which amplifier:
   `adb shell 'ls /sys/bus/i2c/drivers /sys/bus/soundwire/drivers /sys/bus/soundwire/devices /sys/bus/spi/drivers /sys/bus/platform/drivers 2>&1' | grep -i -E 'cs35|cs40|tas|tfa|wsa|aw8|max98|fs1'`;
   `adb shell ls /sys/class | grep -i -E 'cirrus|tas|tfa|spk|amp'`
4. Temperatures:
   `adb shell 'for z in /sys/class/thermal/thermal_zone*; do echo $z $(cat $z/type) $(cat $z/temp); done'`;
   `adb shell 'cat /sys/class/hwmon/hwmon*/name'`; `adb shell dumpsys thermalservice` (look for a speaker or amplifier
   entry; companion check 9).
5. Vendor audio configuration (readable by any app):
   `adb shell ls /vendor/etc /vendor/etc/audio /odm/etc | grep -i -E 'resourcemanager|mixer_paths|audio_platform_info|card-defs|usecaseKv|sapa|audio_effects|acdb'`;
   `adb shell ls /vendor/etc/acdbdata`;
   `adb shell "grep -h -i -E 'speaker_protection_enabled|cps_mode|vbat_enabled|back_end_name' /vendor/etc/resourcemanager*.xml"`;
   `adb shell "grep -h -i -E 'spkr|wsa|cs35|tas|tfa|prot' /vendor/etc/mixer_paths*.xml | head -50"`
6. Calibration storage (expected: not readable as shell):
   `adb shell ls -l /data/vendor/audio /data/misc/audio /mnt/vendor/persist/audio`
7. Properties: `adb shell getprop | grep -i -E 'spkr|speaker|prot|vendor.audio|ro.vendor.audio|persist.audio'`
8. Protection traces: start `adb logcat -b all -c`, play a loud bass passage for 2 minutes, then
   `adb logcat -b all -d | grep -i -E 'spkr|speaker.?prot|SpeakerProtection|cs35l|tas25|tas27|tfa98|wsa88|thermal'`
9. Effects on the speaker path: `adb shell dumpsys media.audio_flinger | grep -i -E -A3 'effect|chain'`
10. Shell permissions on this build:
    `adb shell dumpsys package com.android.shell | grep -E 'MODIFY_AUDIO_ROUTING|CAPTURE_AUDIO_OUTPUT|MODIFY_DEFAULT_AUDIO_EFFECTS'`
11. Loopback capture (idea 10), scrcpy 5.x on the PC: `scrcpy --no-video --audio-source=playback` (does the phone
    speaker go silent?), then `scrcpy --no-video --audio-dup`; repeat with Rootnote on.
12. OboeTester (install from the Oboe releases): Device Report, Data Paths with the speaker and microphones, round-trip
    latency through the speaker. Compare the microphone list with `AudioManager.getMicrophones()` (companion check 5).
13. Root only (a rooted phone, for the root build): `su -c tinymix | grep -i -E 'temp|cal|r0|re data|tf data|sense|prot'`;
    `su -c 'ls -l /data/vendor/audio /data/misc/audio; xxd /data/vendor/audio/audio.cal | head'`.

## Sources

Repositories (default branch, read 2026-10-25; dates are the HEAD commit):

- [aml] https://github.com/Zackptg5/Audio-Modification-Library (`post-fs-data.sh`, `module.prop`, `LICENSE`)
- [aa4a] https://github.com/bewantbe/audio-analyzer-for-android (`README.md`, `LICENSE`)
- [ar-engine] https://github.com/AudioReach/audioreach-engine (`LICENSE`, `modules/processing/`, `modules/cmn/simple_accumulator_limiter/`)
- [ar-gsl] https://github.com/AudioReach/audioreach-graphservices (`README.md`, `acdb/src/`)
- [pal-lic] https://github.com/AudioReach/audioreach-pal/blob/main/LICENSE
- [pal-sp-h] https://github.com/AudioReach/audioreach-pal (`device/Speaker/inc/SpeakerProtection.h`, `device/Speaker/src/SpeakerProtection*.cpp`)
- [pal-rm] https://github.com/AudioReach/audioreach-pal (`configs/qcom/IoT/Kaanapali/resourcemanager_Kaanapali_MTP.xml`, `resource_manager/`)
- [asahi-audio] https://github.com/AsahiLinux/asahi-audio (`README.md`, `conf/`, `firs/*/graph.json`)
- [aubio] https://github.com/aubio/aubio (`COPYING`, `src/pitch/`)
- [autoeq] https://github.com/jaakkopasanen/AutoEq (`README.md`, `LICENSE`)
- [autoeqapi] https://github.com/ThePBone/AutoEqApi (`LICENSE`)
- [bankstown] https://github.com/chadmed/bankstown (`LICENSE`, `README.md`)
- [basic-pitch] https://github.com/spotify/basic-pitch (`LICENSE`, `NOTICE`)
- [calf] https://github.com/calf-studio-gear/calf (`COPYING`, `src/modules_dist.cpp`)
- [cirrus-ld] https://github.com/CirrusLogic/linux-drivers (branch list; `sound/soc/codecs/cs35l43.c` on `v6.12-cs35l43`)
- [crepe] https://github.com/marl/crepe (`LICENSE`)
- [ebur128] https://github.com/jiixyj/libebur128 (`COPYING`, `README.md`)
- [essentia] https://github.com/MTG/essentia (`COPYING.txt`)
- [fftw] https://github.com/FFTW/fftw3 (`COPYING`, `COPYRIGHT`)
- [jdsp-pbone] https://github.com/ThePBone/JamesDSPManager (HEAD `1b9f89d`)
- [jdsp-upstream] https://github.com/james34602/JamesDSPManager (commit history since 2023-11)
- [jdsp4linux] https://github.com/Audio4Linux/JDSP4Linux (`LICENSE`)
- [kissfft] https://github.com/mborgerding/kissfft (`COPYING`)
- [lcc] https://github.com/MeteorStudioASU/lcc (`README.md`, `LICENSE`, `lcc_rtaudio.cpp`)
- [librosa] https://github.com/librosa/librosa (`LICENSE.md`, `librosa/core/pitch.py`)
- [linux-ar] https://github.com/torvalds/linux/blob/master/sound/soc/qcom/qdsp6/audioreach.h
- [linux-codecs] https://github.com/torvalds/linux/tree/master/sound/soc/codecs (`cs35l41.c`, `cs35l45.c`, `tas2764.c`, `tas2770.c`, `tfa989x.c`, `wsa883x.c`, `wsa884x.c`)
- [cs-amp-lib] https://github.com/torvalds/linux (`sound/soc/codecs/cs-amp-lib.c`, `include/sound/cs-amp-lib.h`)
- [tas2781] https://github.com/torvalds/linux (`sound/soc/codecs/tas2781-i2c.c`, `include/sound/tas2781.h`)
- [loopback] https://github.com/gkasten/drrickorang (`LoopbackApp/`)
- [loudness-gm] https://github.com/deeuu/loudness (`LICENSE`, `src/models/`)
- [lsp-loud] https://github.com/lsp-plugins/lsp-plugins-loud-comp (`src/main/plug/loud_comp.cpp`, `include/generated/iso226/`)
- [lsp-lim] https://github.com/lsp-plugins/lsp-plugins-limiter (`include/private/meta/limiter.h`)
- [lsr] https://github.com/libsndfile/libsamplerate (`COPYING`)
- [mosqito] https://github.com/Eomys/MoSQITo (`LICENSE`, `mosqito/sq_metrics/`)
- [mysofa] https://github.com/hoene/libmysofa (`LICENSE`)
- [noisecapture] https://github.com/Universite-Gustave-Eiffel/NoiseCapture (`LICENSE`, `app/src/main/java/org/noise_planet/noisecapture/Calibration*.java`)
- [oboe] https://github.com/google/oboe (`LICENSE`, `apps/OboeTester/docs/Usage.md`)
- [pesto] https://github.com/SonyCSLParis/pesto (`LICENSE.md`, `README.md`)
- [pffft] https://github.com/marton78/pffft (`LICENSE.txt`)
- [phyphox] https://github.com/phyphox/phyphox-android (`LICENSE`)
- [pocketfft] https://github.com/mreineck/pocketfft (`LICENSE.md`)
- [pyacoustics] https://github.com/python-acoustics/python-acoustics (`README.md`, `LICENSE`)
- [pyfar-dsp] https://github.com/pyfar/pyfar (`LICENSE`, `pyfar/dsp/dsp.py`, `pyfar/signals/deterministic.py`, `pyfar/dsp/filter/`)
- [pyloudnorm] https://github.com/csteinmetz1/pyloudnorm (`LICENSE`)
- [pyrato] https://github.com/pyfar/pyrato (`LICENSE`)
- [pyroom] https://github.com/LCAV/pyroomacoustics (`LICENSE`)
- [r8brain] https://github.com/avaneev/r8brain-free-src (`LICENSE`)
- [rjdsp] https://github.com/ThePBone/RootlessJamesDSP (HEAD `60d25ae`)
- [saf] https://github.com/leomccormack/Spatial_Audio_Framework (`LICENSE.md`, `framework/include/saf.h`)
- [scrcpy-apc] https://github.com/Genymobile/scrcpy/blob/master/server/src/main/java/com/genymobile/scrcpy/audio/AudioPlaybackCapture.java
- [scrcpy-doc] https://github.com/Genymobile/scrcpy/blob/master/doc/audio.md
- [shizuku] https://github.com/RikkaApps/Shizuku (`LICENSE`, `README.md`)
- [shizuku-api] https://github.com/RikkaApps/Shizuku-API (`LICENSE`, `README.md`, `api/src/main/java/rikka/shizuku/Shizuku.java`)
- [sofar] https://github.com/pyfar/sofar (`LICENSE`)
- [sof] https://github.com/thesofproject/sof (`LICENCE`, `src/audio/drc/`, `src/audio/multiband_drc/`)
- [sof-smartamp] https://github.com/thesofproject/sof/tree/main/src/audio/smart_amp (`README.md`)
- [speexdsp] https://github.com/xiph/speexdsp (`COPYING`)
- [ssd-readme] https://github.com/AsahiLinux/speakersafetyd (`README.md`, `Cargo.toml`, `LICENSE`, `LICENCE.MIT`)
- [ssd-types] https://github.com/AsahiLinux/speakersafetyd/blob/main/src/types.rs
- [ssd-conf] https://github.com/AsahiLinux/speakersafetyd/tree/main/conf/apple
- [tinyalsa] https://github.com/tinyalsa/tinyalsa (`LICENSE`, `Android.bp`)
- [v4a] https://github.com/AndroidAudioMods/ViPER4Android (`README.md`)
- [v4a-re] https://github.com/AndroidAudioMods/ViPERFX_RE (`README.md`, `module/LICENSE`, `src/viper/`)
- [visqol] https://github.com/google/visqol (`LICENSE`)
- [x42-dpl] https://github.com/x42/dpl.lv2 (`COPYING`)

Other primary sources:

- [aosp-ueventd] https://android.googlesource.com/platform/system/core/+/refs/heads/main/rootdir/ueventd.rc
- [aosp-adbd] https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/daemon/main.cpp (`drop_privileges`)
- [aosp-shell-te] https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/private/shell.te
- [aosp-shell-manifest] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/packages/Shell/AndroidManifest.xml (first 100,000 characters read)
- [qc-legacy-sp] https://android.googlesource.com/platform/hardware/qcom/audio/+/refs/heads/main/hal/audio_extn/spkr_protection.c
- [clo-audiokernel] https://git.codelinaro.org/clo/la/platform/vendor/opensource/audio-kernel (project page only)
- [rew-api] https://www.roomeqwizard.com/help/help_en-GB/html/api.html
- [rew-cal] https://www.roomeqwizard.com/help/help_en-GB/html/calfiles.html
- [soxr] https://sourceforge.net/projects/soxr/ (project page; repository not reachable)

Not read (blocked or not reachable from here): opensource.samsung.com (fetch refused), git.rwth-aachen.de (an ITA
crosstalk-cancellation library was found by search but not read), the CodeLinaro file trees, the soxr repository, the
FSF licence list, the GitHub API (release dates). Claims that would need them are marked unconfirmed.
