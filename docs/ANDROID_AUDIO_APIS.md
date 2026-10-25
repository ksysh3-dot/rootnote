# Android platform APIs for Rootnote

Status: 2026-10-25. Research note, nothing in the app changed. Target phone: Galaxy S26 Ultra (Android 16). App: target
SDK 34, compile SDK 35, min SDK 29 (`buildSrc/src/main/kotlin/AndroidConfig.kt`, `app/build.gradle.kts`).

Sources are primary only: the Android API diff reports and guides on developer.android.com, source.android.com, and AOSP
source on android.googlesource.com. Every API claim carries a source key in square brackets; the list is at the end.
"Unconfirmed" means no primary source was found or read for that claim. The full reference pages on developer.android.com
could not be read by the research tool, so API levels come from the official API diff reports and behaviour from the
AOSP javadoc.

## Summary

- Most of what the app needs is already in use. The biggest gaps are small: the app asks the phone what it **declares**
  about the microphone, but not which microphone a recording **actually** uses, whether the recording is silenced, or
  which effects run on it. These are public API 28/29 calls that `BuzzMicrophone.kt` already half uses.
- `getStreamVolumeDb()` only reports the attenuation of the framework volume curve [src-volcurve]. The app already
  found that the S26 Ultra reports about 0 dB at every index (`PvbController.kt`, `readVolume`). That points to a
  full-scale curve on the speaker, with the real volume applied later in the vendor audio path. If so, no public API
  can tell the dB of a volume step; only a measurement can. One `dumpsys media.audio_policy` on the phone settles it
  (the dump prints every volume curve point [src-volgroup]), and the app already holds `DUMP`.
- Any app may read `/vendor/etc` under the AOSP SELinux policy ("All domains get access to /vendor/etc" [src-sepol-domain]).
  Shizuku is not needed to read vendor audio XMLs, if the files are there at all: with the AIDL audio HAL the volume
  curves may come from the HAL instead of an XML file [sac-aidl].
- Playback callbacks keep each player's capture policy (reduced to "all" or "none") even in the anonymized copy an
  ordinary app receives [src-apc]. So the app can tell "something is playing that cannot be captured", which explains
  the most confusing failure, without root.
- Thermal headroom describes SoC and skin throttling [guide-thermal]. It is not a public view of speaker or amplifier
  protection. The thermal HAL does have a `SPEAKER` temperature type [src-thermal-type], but there is no public API for
  it; whether `dumpsys thermalservice` shows one on this phone is a test to run.

## Already used

Found by grep over `app/src` (Kotlin and Java) and `hidden-api-impl`, code as of 2026-10-25.

| API | Where | Notes |
|---|---|---|
| `AudioManager.getMicrophones()`, `MicrophoneInfo.getSensitivity/getFrequencyResponse/getAddress/getIndexInTheGroup/getType` | `devmode/DeclaredMic.kt`, `pvb/PvbAnalyzerView.kt` (MicFeed), `pvb/BassFit.kt` | Picks the mic whose address contains "bottom", else the lowest index. The same selection is written twice. |
| `AudioRecord.getActiveMicrophones()` | `home/SpatialBalanceActivity.kt` | Only the count (`micsReported`), for spatial balance. Not used by Bass fit, the probe or the analyzer. |
| `AudioRecord.setPreferredDevice`, `getRoutedDevice`, `getTimestamp`, `getActiveRecordingConfiguration` (`isClientSilenced`, `getAudioSource`), `Builder.setPrivacySensitive(false)` | `pvb/BuzzMicrophone.kt` | Only in the buzz diagnostics microphone. `BassFitActivity.FitMic.open`, `PvbMeasure` and `PvbAnalyzerView.MicFeed` use none of them. |
| `PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED`, sources `UNPROCESSED` / `VOICE_RECOGNITION` / `CAMCORDER` | BassFit, PvbMeasure, analyzer, SpatialBalanceActivity | |
| `AutomaticGainControl` / `NoiseSuppressor` / `AcousticEchoCanceler` disable requests | `pvb/BuzzMicrophone.kt` | Client effects only; vendor effects on the stream are not read. |
| `AudioManager.getStreamVolume/getStreamMaxVolume`, `getStreamVolumeDb(STREAM_MUSIC, i, TYPE_BUILTIN_SPEAKER)` | `pvb/PvbController.kt` `readVolume`, many cards | The dB table is used only when `VolumeCompensation.plausibleSystemTable` accepts it. Code comment: "Samsung reports about 0 dB for every index". |
| Hidden broadcast `android.media.VOLUME_CHANGED_ACTION` | `pvb/PvbController.kt` | Marked `@hide` in AOSP [src-am]; the app also polls, which is the safe fallback. |
| `AudioTrack.getRoutedDevice`, `addOnRoutingChangedListener`, `AudioDeviceCallback`, `getDevices(OUTPUTS)` | `pvb/PvbController.kt`, `pvb/PvbMeasure.kt`, `utils/RoutingObserver.kt` | When the track has no routed device yet, "any external output connected" counts as "not the speaker". |
| `getAudioDevicesForAttributes(USAGE_MEDIA)`, `getSupportedMixerAttributes`, `getPreferredMixerAttributes` | `utils/AudioSampleRateDetector.kt` | Only to choose the processing sample rate, not for routing. |
| `getProperty(PROPERTY_OUTPUT_SAMPLE_RATE / FRAMES_PER_BUFFER)` | `service/RootlessAudioProcessorService.kt` and others | |
| `registerAudioPlaybackCallback` | `RootlessAudioProcessorService.kt`, `RootAudioProcessorService.kt`, `session/shared/BaseSessionManager.kt` | Used as a wake-up signal only; the configurations are not read. |
| `AudioPlaybackCaptureConfiguration` (`USAGE_MEDIA/GAME/UNKNOWN`, `excludeUid`) | `RootlessAudioProcessorService.kt` `buildAudioRecord` | |
| Output `AudioTrack`: `USAGE_UNKNOWN`, `ALLOW_CAPTURE_BY_NONE`, stream mode, no performance mode; `getUnderrunCount`, `getTimestamp` | `RootlessAudioProcessorService.kt` | |
| `DynamicsProcessing` (input gain -200 dB) and the hidden Volume effect | `utils/MutedAudioEffectFactory.kt` | To mute other apps' sessions, not as a processor. |
| `DUMP` permission + binder `dumpAsync` of `audio`, `media.audio_policy`, `media.audio_flinger`, `package` | `session/dump/*` | `DUMP` is granted through Shizuku or ADB (`setup/RnSetupActivity.kt`). |
| Shizuku: `pm grant`, `appops set` (`PROJECT_MEDIA`, `SYSTEM_ALERT_WINDOW`, `GET_USAGE_STATS`) | `hidden-api-impl/.../ShizukuSystemServerApi.java` | `exec()` runs a shell command but discards its output. |
| Accelerometer posture, display rotation | `pvb/PvbController.kt` | |
| `BatteryManager` capacity, `PowerManager.isIgnoringBatteryOptimizations` | `pvb/LiveAbView.kt`, `pvb/FirstWeekStore.kt` | No thermal API is used. |

One code finding while reading: `VolumeCompensation.FALLBACK_CURVE` says it is "Android's default speaker volume curve"
and uses (1 %, -56 dB), (20 %, -34 dB), (60 %, -11 dB). AOSP main's default speaker and media curves are (1, -58 dB),
(20, -40 dB), (60, -17 dB), (100, 0 dB) [src-voltables], and `AUDIO_STREAM_MUSIC` on `DEVICE_CATEGORY_SPEAKER` uses that
curve [src-volumes]. The app's values match an older default (unconfirmed). The gap is up to 6 dB in the middle of the
range. It only matters on phones where the platform table is rejected.

## Not used yet

### Microphone

| API | Level | Returns / does | Permission | Caveats |
|---|---|---|---|---|
| `AudioRecord.getActiveMicrophones()` | 28 [diff28-ar] | `MicrophoneInfo` list for the mics feeding this recording, with `getChannelMapping()` filled in. The channel mapping is "Empty list when the MicrophoneInfo is returned by AudioManager.getMicrophones()" [src-mic], so this is the call that says which mic is really used. | Holds a recording, so `RECORD_AUDIO` | The list depends on the HAL; empty is possible (unconfirmed how common). Used only for a count today. |
| `MicrophoneInfo.getPosition()` / `getOrientation()` | 28 [diff28-pkg] | Position in meters and a unit orientation vector; `POSITION_UNKNOWN` / `ORIENTATION_UNKNOWN` when not declared [src-mic]. | none (app relies on this) | The coordinate frame is not stated in the javadoc read (unconfirmed). Useful for distance from the bottom speaker. |
| `MicrophoneInfo.getDirectionality()` | 28 | `DIRECTIONALITY_OMNI`, `_BI_DIRECTIONAL`, `_CARDIOID`, `_HYPER_CARDIOID`, `_SUPER_CARDIOID`, `_UNKNOWN` [src-mic] | none | Phone mics are normally omni; a non-omni value would change the probe's meaning. |
| `MicrophoneInfo.getMaxSpl()` / `getMinSpl()` | 28 | "the maximum SPL supported by the device at 1000Hz" and "the minimum SPL that can be registered", dB; `SPL_UNKNOWN` when unknown [src-mic] | none | Lets the app tell when a probe near the speaker can clip the mic. Not yet read on the S26 Ultra. |
| `MicrophoneInfo.getSensitivity()` (already used) | 28 | "the level in dBFS produced by a 1000Hz tone at 94 dB SPL" [src-mic] | none | Declared for the device mic. Whether it holds for both `UNPROCESSED` and `VOICE_RECOGNITION` gain is unconfirmed; the UMIK-1 match can check it. |
| `MicrophoneInfo.getLocation()` / `getGroup()` / `getId()` | 28 | `LOCATION_MAINBODY`, `_MAINBODY_MOVABLE`, `_PERIPHERAL`; group 0 is "usually" the main body; `getId()` matches `AudioDeviceInfo.getId()` [src-mic] | none | `getId()` is the clean way to join a declared mic to the input `AudioDeviceInfo` passed to `setPreferredDevice`, instead of matching the word "bottom". |
| `AudioRecord.setPreferredMicrophoneDirection(int)` / `setPreferredMicrophoneFieldDimension(float)` | 29 [diff29-ar] | "Specifies the logical microphone (for processing)", meant to follow the camera; zoom -1 (wide) to 1; returns true "if sucessful" [src-micdir] | `RECORD_AUDIO` | It is a hint for processing, not a mic switch. With `UNPROCESSED` it may do nothing (unconfirmed). |
| `AudioRecord.setPreferredDevice(AudioDeviceInfo)` (Bass fit, probe, analyzer) | below min SDK | Chooses the input device. Which physical mic each source uses is decided by the vendor policy and HAL; only `getActiveMicrophones()` reports it (unconfirmed for this phone). | `RECORD_AUDIO` | Built-in inputs may appear as several `TYPE_BUILTIN_MIC` devices with different addresses; untested here. |
| `AudioRecord.getTimestamp(ts, TIMEBASE_MONOTONIC or BOOTTIME)` (Bass fit, probe) | 24 [diff24-ar] | Frame position at a clock time [src-ar] | `RECORD_AUDIO` | Already used in buzz diagnostics. |
| `AudioRecordingConfiguration.isClientSilenced()` / `getEffects()` / `getClientEffects()` / `getAudioSource()` | 29 [diff29-arc] | Silenced "due to the capture policy"; effects "enabled on the capture stream"; the source the capture path was configured with [src-arc] | own recording | `getEffects()` is the only public way to see vendor pre-processing on `VOICE_RECOGNITION`. |
| `AudioManager.registerAudioRecordingCallback` | 24 (unconfirmed level) | "The callback is executed only when the app is receiving audio and a change occurs" [guide-share] | none | |
| Privacy flag `AudioRecord.Builder.setPrivacySensitive` | 30 [diff30-arb] | True: "any concurrent capture is not permitted" [src-ar]. Default is false except for `VOICE_COMMUNICATION` and `CAMCORDER` [src-ar]. | `RECORD_AUDIO` | Setting true for a short probe would keep an assistant from sharing the mic during the measurement [guide-share]. |
| Concurrent capture rules | 29+ | Two ordinary apps never capture at once; the top UI wins, privacy-sensitive sources win; "The call always receives audio"; the loser gets silence [guide-share] | | A Bass fit run during a call or with another recorder in front records silence. Today nothing checks for that outside buzz diagnostics. |

### Volume

| API | Level | Returns / does | Permission | Caveats |
|---|---|---|---|---|
| `AudioManager.getStreamVolumeDb(stream, index, deviceType)` (already used) | 28 [diff28-am] | "the volume in dB" of the stream at that index on that device type; mute is negative infinity; `IllegalArgumentException` for a bad stream, index or device [src-am] | none | The value comes from the framework volume curve: linear interpolation between curve points, last point past the end [src-volcurve]. It cannot see volume applied in the HAL or DSP. That fits the S26 Ultra's 0 dB table. |
| Volume curve files | n/a | `<point>index,millibel</point>` lists per stream and device category; index 0-100 [sac-policy] [src-voltables] | read: any app (SELinux) [src-sepol-domain] | Search order `/odm/etc`, `/vendor/etc/audio/sku_<ro.boot.product.vendor.sku>`, `/vendor/etc`, `/system/etc` [src-audioconfig]. With the AIDL HAL the curves come from `IConfig.getEngineConfig`, and the XML may be absent [sac-aidl]. |
| `dumpsys media.audio_policy` (volume groups) | n/a | Each volume group prints its curves "for device category (index, attenuation in millibel)" and the current index per device [src-volcurve] [src-volgroup] [src-enginebase] | `DUMP` (the app has it) | Shows the curves in effect, whatever their origin. If the music group's speaker curve is full scale (0 dB), the platform has handed volume to the vendor path. |
| `AudioManager.getVolumeGroupIdForAttributes`, `isVolumeGroupMuted`, `adjustVolumeGroupVolume` | 34 [diff34-am] | Volume group id for attributes, mute state [src-am] | none | Minor. |
| `AudioManager.isVolumeFixed()` | 21 (unconfirmed level) | True when the device "implements a fixed volume policy"; volume calls then have no effect [src-am] | none | Cheap check before a measurement that steps the volume. |
| `cmd audio set-device-volume STREAM INDEX NATIVE_DEVICE` and friends | n/a | Shell commands: `set-volume`, `set-device-volume`, `adj-volume`, `set-group-volume`, sound dose get/set [src-audioshell] | shell (Shizuku) | Could set the speaker index while headphones are connected. Not needed today. |

### Routing and playback state

| API | Level | Returns / does | Permission | Caveats |
|---|---|---|---|---|
| `AudioManager.getAudioDevicesForAttributes(attrs)` for routing | 33 [diff33-am] | Devices the given attributes would route to now (javadoc not read; unconfirmed wording) | none in practice (already called by `AudioSampleRateDetector.kt`) | Answers "would media play on the speaker" before the app's own track has a routed device. The app's output track uses `USAGE_UNKNOWN`; ask with `USAGE_MEDIA`, the usage of the music being captured. |
| `AudioManager.getActivePlaybackConfigurations()`, `AudioPlaybackConfiguration.getAudioAttributes()` | 26 [diff26-am] | Ordinary apps get an anonymized copy: uid, pid, session, player type and devices are cleared, but usage, content type, flags and the capture policy are kept, the policy reduced to `ALLOW_CAPTURE_BY_ALL` or `ALLOW_CAPTURE_BY_NONE` [src-apc] | none | `getAudioDeviceInfo()` is deprecated: "this information was never populated". `getPlayerState`, `getClientUid`, `isActive`, `getSessionId` are `@SystemApi` [src-apc]. Package names need the dump (already parsed in `AudioServiceDumpProvider.kt`). |
| Capture rules for the player (`AudioAttributes.Builder.setAllowedCapturePolicy`, 29 [diff29-aab]) | 29+ | The player must use `USAGE_MEDIA`, `USAGE_GAME` or `USAGE_UNKNOWN`; "The most restrictive capture policy is always applied"; apps targeting 28 or lower are not capturable unless they opt in; a runtime policy change applies only to players opened after it [guide-capture] | | This is the full list of "why is this app not processed" reasons. |
| `AudioManager.addOnModeChangedListener` | 31 [diff31-am] | Call / communication mode changes | none | A call takes the mic [guide-share]; useful to pause Bass fit cleanly. |

### Output path

| API | Level | Returns / does | Caveats |
|---|---|---|---|
| `AudioTrack` `PERFORMANCE_MODE_LOW_LATENCY / POWER_SAVING / NONE` | 26 [diff26-at] | AAudio's description: power saving "uses larger internal buffers and a data path that trades off latency for lower power" [guide-aaudio] | The processor track uses the default. Power saving may move it to a deep-buffer output (unconfirmed for this phone) and add latency that matters for video. |
| `AudioTrack.Builder.setOffloadedPlayback`, `AudioTrack.isOffloadedPlayback`, `AudioManager.getDirectPlaybackSupport` / `getDirectProfilesForAttributes` | 29 [diff29-atb] [diff29-at], 33 [diff33-am] | Offload and direct paths for a format | `getPlaybackOffloadSupport` (31) is deprecated in favour of `getDirectPlaybackSupport` [src-am]. Offload bypasses the mixer; float PCM offload on the speaker is unlikely (unconfirmed). Not useful for a stream the app mixes itself. |
| `AudioMixerAttributes`, `setPreferredMixerAttributes` | 34 [diff34-am] | Mixer format and behaviour `DEFAULT` or `BIT_PERFECT` ("there will not be mixing happen") [src-mixer] | Which devices support it was not found in the source read (unconfirmed). Not relevant to the speaker. |
| `PROPERTY_OUTPUT_SAMPLE_RATE / FRAMES_PER_BUFFER` (already used) | 17 | Typical buffers 96-512 frames; "There is currently no API to determine audio latency over any path on an Android device at runtime" [guide-latency] | Latency must come from timestamps or a loopback, as the app already does. |
| `dumpsys media.audio_flinger` | n/a | Output threads and tracks; an "F" marks a fast track [guide-latency] | Shows which output thread the app's track is on and what effect chains are attached (root build). |
| AAudio / Oboe | 26 | Low-latency callback streams, exclusive or shared [guide-aaudio] | AAudio has no MediaProjection playback capture in the guide read, so the capture side would stay `AudioRecord`. No gain for this app. |

### Effects

| API | Level | What a non-system app can do | Caveats |
|---|---|---|---|
| `DynamicsProcessing` | 28 | Attach to an audio session; pre-EQ, multi-band compressor, post-EQ, limiter per channel; session 0 logs "attaching a DynamicsProcessing to global output mix is" deprecated [src-dp] | The native engine already does more. Keep it only as the mute tool. |
| `Spatializer` (`AudioManager.getSpatializer`) | 32 [diff32-am] | Public: `isAvailable`, `isEnabled`, `canBeSpatialized(attrs, format)`, `getImmersiveAudioLevel`, state listeners. Speaker-specific queries (`isAvailableForDevice`) are `@SystemApi` [src-spatializer] | Useful only as a diagnostic: is the platform spatializer on while Rootnote runs its own crosstalk cancellation. Whether the phone's own speaker 3D mode goes through this class is unconfirmed. |
| `HapticGenerator` | 31 [diff31-fx] | Makes haptic data from the audio of a session; "the effect will only be created on device supporting audio-coupled-haptic playback"; enabling needs `VIBRATE` [src-haptic] | Attach to the app's own output track session. Availability on the S26 Ultra is unknown. |
| `VibrationEffect.BasicEnvelopeBuilder` / `WaveformEnvelopeBuilder`, `Vibrator.areEnvelopeEffectsSupported()` | Android 16 [a16-features] [guide-haptics] | Amplitude and frequency curves; out-of-range frequencies do not play [guide-haptics] | Needs compile SDK 36. Not audio-synchronous by itself. |
| `Visualizer` | 9 | `RECORD_AUDIO` always; session 0 (output mix) also needs `MODIFY_AUDIO_SETTINGS`; `MEASUREMENT_MODE_PEAK_RMS`; `SCALING_MODE_AS_PLAYED` follows playback volume [src-visualizer] | The app holds both permissions. Gives an independent post-mix meter; it sees framework volume only. |
| `LoudnessEnhancer` | 19 | Target gain in mB; out-of-range samples "are compressed"; session 0 deprecated (log warning) [src-loudness] | No use: the app has its own limiter. |
| `LoudnessCodecController` | 35 | CTA-2075 loudness for AAC with metadata, applied on `MediaCodec` [a15-features] | Only for an app's own decoder. Not applicable. |

### Thermal and power

| API | Level | Returns | Caveats |
|---|---|---|---|
| `PowerManager.getCurrentThermalStatus()`, `addThermalStatusListener` | 29 [diff29-pm] | `THERMAL_STATUS_NONE` ... `SHUTDOWN` | "Some devices might not fully support this technology yet and return THERMAL_STATUS_NONE regardless" [guide-thermal] |
| `PowerManager.getThermalHeadroom(forecastSeconds)` | 30 [diff30-pm] | 0.0 (no throttling) to 1.0 (`SEVERE`), above 1.0 possible; NaN if called more than once every 10 s or unsupported [guide-thermal] | Describes device throttling, not the speaker. |
| `PowerManager.getThermalHeadroomThresholds()` | 35 [diff35-pm] | Headroom value per status [a15-features] | |
| `PerformanceHintManager` sessions | 31 [diff31-os] | Work-duration hints; Android 15 adds `setPreferPowerEfficiency` [a15-features] | Built for games. The audio thread uses about 5 % of a core (`docs/PERFORMANCE.md`); little to gain. |
| `SystemHealthManager.getCpuHeadroom` / `getGpuHeadroom` | Android 16 [a16-features] | CPU and GPU headroom estimates | Needs compile SDK 36. |
| Thermal HAL `TemperatureType.SPEAKER` (17), `POWER_AMPLIFIER` (5) | HAL | Enum values exist [src-thermal-type] | `@hide`; no public API. `dumpsys thermalservice` may list it if the vendor reports it (unconfirmed; the service source could not be read). `POWER_AMPLIFIER` most likely means the radio amplifier (unconfirmed). |

### Sensors

| Sensor | Level | Notes |
|---|---|---|
| Proximity (`TYPE_PROXIMITY`) | 3 (unconfirmed level) | cm, or only near/far; "Some proximity sensors return binary values"; under-screen sensors may show a dot when the screen is on [guide-pos]. Could detect a covered phone (pocket, face down). |
| Hinge angle (`TYPE_HINGE_ANGLE`) | 30 [diff30-sensor] | Foldables only. Not the target phone; would matter for profiles on foldables. |
| Accelerometer, display rotation | already used | |

### What Shizuku or ADB adds on Android 14-16

- **Shell identity.** Shizuku started by ADB runs commands as the shell user. The app's `ShizukuSystemServerApi.exec()`
  writes the command and discards the output; reading output needs a small new helper.
- **`DUMP`.** Already granted through Shizuku or ADB and used through binder `dumpAsync` (`DumpUtils.kt`). With it the app
  can read, without running a shell: `media.audio_policy` (volume curves [src-volgroup], sessions, spatializer state,
  `AudioPolicyService::dump` [src-aps]), `media.audio_flinger` (threads, tracks, fast flag [guide-latency]), `audio`
  (stream indices, playback configurations with uid and usage, parsed in `AudioServiceDumpProvider.kt`), and probably
  `thermalservice` (unconfirmed what it prints).
- **Vendor XMLs.** Readable by any app under the AOSP policy [src-sepol-domain], so Shizuku is not needed. The vendor can
  label files differently (unconfirmed for this phone).
- **Speaker protection or smart-amp calibration.** The AOSP shell policy grants no access to vendor data partitions or
  persist storage; only `sysfs` directories and a few `sysfs` files are readable [src-sepol-shell]. Calibration data is
  therefore probably not readable without root (unconfirmed; vendor policy can add rules).
- **`cmd audio`.** Volume and sound dose commands [src-audioshell]. `cmd media.audio_policy` exists (the service handles
  `SHELL_COMMAND_TRANSACTION` [src-aps]), but its command list could not be read (unconfirmed).
- **`logcat`.** The shell can read the logs of the vendor audio HAL; speaker protection messages may show up there
  (unconfirmed, vendor-specific).

## Combinations and ideas

### Ranked

| Rank | Idea | API chain | Value | Effort | Verdict |
|---|---|---|---|---|---|
| 1 | Mic truth for every measurement | `getActiveMicrophones` + `getActiveRecordingConfiguration` (`isClientSilenced`, `getEffects`, `getAudioSource`) + join by `MicrophoneInfo.getId` | High | Low | Keep |
| 2 | Find out where the volume lives | `dumpsys media.audio_policy` curves + read `/vendor/etc` XMLs + `getStreamVolumeDb` | High | Low | Keep |
| 3 | Reliable "speaker or not" before the track plays | `getAudioDevicesForAttributes(USAGE_MEDIA)` + existing routing listener | Medium | Low | Keep |
| 4 | Explain "this app cannot be processed" | playback callback attributes (`getAllowedCapturePolicy`, usage) + `audio` dump for the package | Medium | Low-medium | Keep |
| 5 | At-mic SPL and a mic clipping guard | declared sensitivity + `getMaxSpl` + UMIK-1 match | Medium | Low | Keep (developer mode) |
| 6 | Volume step map from a measurement | existing probe volume steps (`PvbMeasure`) stored per index, replacing the fallback curve | Medium | Medium | Keep if idea 2 shows a full-scale curve |
| 7 | Thermal logging next to bass level | `getThermalHeadroom` (10 s) + status listener + `dumpsys thermalservice` | Low-medium | Low | Keep as logging only |
| 8 | Spatializer state in diagnostics | `Spatializer.isAvailable/isEnabled/getImmersiveAudioLevel` | Low | Low | Keep, small |
| 9 | Power-saving output track | `PERFORMANCE_MODE_POWER_SAVING` + `dumpsys media.audio_flinger` | Medium | Medium | Test only |
| 10 | Absolute SPL at the listener | `getStreamVolumeDb` + speaker response + declared mic sensitivity | Low | Medium | Reject |
| 11 | Thermal headroom as speaker protection | `getThermalHeadroom` -> lower virtual bass | Low | Low | Reject |
| 12 | Bass feel through haptics | `HapticGenerator` on the output session, or Android 16 envelopes | Low | Medium | Reject (check `isAvailable` once) |
| 13 | Pocket / covered detection | proximity sensor | Low | Low | Later |
| 14 | Mic direction hints, AAudio/Oboe output, `LoudnessEnhancer`, `DynamicsProcessing` as processor | | Low | | Reject |

### 1. Mic truth for every measurement

Today the declared sensitivity and response are taken from the mic whose address contains "bottom". The recording itself
never confirms that this is the mic in use, and only buzz diagnostics checks for silencing.

- Chain: after `startRecording()` in `FitMic.open`, `PvbMeasure` and `MicFeed`, call `getActiveMicrophones()`; take the
  mic with a `CHANNEL_MAPPING_DIRECT` entry for channel 0 [src-mic]; use its `getSensitivity()` and
  `getFrequencyResponse()`; fall back to the current heuristic when the list is empty. Read
  `getActiveRecordingConfiguration()`: stop or flag the run when `isClientSilenced()` [src-arc] [guide-share]; log
  `getAudioSource()` (the source the path was really set up with) and `getEffects()` (vendor processing on the stream).
- Benefit: the correction, room check and UMIK-1 match use the data of the mic that recorded; a run during a call or
  with another recorder in front no longer produces a silent "result"; vendor noise suppression on `VOICE_RECOGNITION`
  becomes visible.
- Cost and risk: a few lines in three places, plus moving the duplicated selection into `DeclaredMic`. No new permission.
- Verify: log all fields with `UNPROCESSED` and `VOICE_RECOGNITION`; record with a second app in front and check
  `isClientSilenced`.

### 2. Find out where the volume lives

The app already knows that `getStreamVolumeDb` returns about 0 dB on the S26 Ultra, and that a bass-weighted limiter sits
after the volume control (`VolumeLevelLink.kt`). `getStreamVolumeDb` reports the framework curve
[src-volcurve], so 0 dB means the framework applies no attenuation on the speaker.

- Chain: one `DumpUtils.dumpAll(context, "media.audio_policy")`; find the music volume group and its
  `DEVICE_CATEGORY_SPEAKER` points [src-volgroup]. Also list `/odm/etc`, `/vendor/etc/audio/sku_*`, `/vendor/etc` for
  `audio_policy_*.xml` and any vendor volume tables [src-audioconfig] [src-sepol-domain].
- Benefit: either the curve is real (then `getStreamVolumeDb` is wrong for another reason, and the curve can feed
  `VolumeCompensation` directly), or it is full scale and volume steps can only be known by measurement (idea 6). Both
  answers remove a guess. Also correct the fallback curve to AOSP's current default [src-voltables], or label it.
- Cost and risk: low; the dump code exists. Vendor XML formats are not documented.
- Verify: the adb checks below; compare with the probe's measured level per index.

### 3. Reliable "speaker or not"

`PvbController.updateRoute` falls back to "any external output connected means not the speaker" when the app's track has
no routed device. A connected Bluetooth device with media switched to the phone counts as "not the speaker" there.

- Chain: in that fallback, use `getAudioDevicesForAttributes(AudioAttributes(USAGE_MEDIA))` [diff33-am] and check for
  `TYPE_BUILTIN_SPEAKER` / `_SAFE`. Keep the routed device as the first source. Re-check on `AudioDeviceCallback`.
- Benefit: correct EQ state while idle and at the first sound after a route change. Same check before a probe.
- Cost and risk: low. The javadoc of this call was not read (unconfirmed); the app already calls it without trouble.
- Verify: connect Bluetooth, switch media output to the phone, compare both answers.

### 4. Explain "this app cannot be processed"

- Chain: in the existing playback callback, read each configuration's `getAudioAttributes().getAllowedCapturePolicy()`
  and usage [src-apc]. A player with `USAGE_MEDIA` or `USAGE_GAME` and policy "none" means music that capture cannot
  get [guide-capture]. Skip the app's own players: the processor track is `USAGE_UNKNOWN` with policy "none", the probe
  `USAGE_MEDIA` with "none", so the probe must be excluded while it runs. With `DUMP`, take the package from the `audio`
  dump (already parsed). Usages outside media, game and unknown (for example a call) are not capturable either.
- Benefit: a plain status line ("this app does not allow its sound to be processed") instead of silence.
- Cost and risk: low. Ordinary apps get no uid, so without `DUMP` the message cannot name the app.
- Verify: play from a player that opts out of capture, read the callback, compare with the `audio` dump.

### 5. At-mic SPL and a mic clipping guard

- Chain: level in dBFS + 94 - declared sensitivity = dB SPL at the mic, at 1 kHz [src-mic]; apply the declared response
  for other frequencies; compare the peak with `getMaxSpl()`.
- Benefit: the room-noise check and the probe can show dB SPL instead of dBFS, and the probe can warn when the mic near
  the bottom speaker is close to clipping. The UMIK-1 match measures the real offset, which says how far the declared
  value can be trusted.
- Cost and risk: low. It is SPL at the mic in the near field of the speaker, not at the listener. Keep it in developer
  mode.

### 6. Volume step map from a measurement

If idea 2 shows a full-scale curve, the dB per index can only come from measurement. `PvbMeasure` already steps the volume
with a 200 Hz - 8 kHz noise. Storing the measured level per index (S26 Ultra, 15 steps) replaces both the fallback curve
and the plausibility test for this phone. Risk: the limiter after the volume makes the step size depend on level and
frequency; measure at a low level.

### 7. Thermal logging

`getThermalHeadroom` is SoC and skin throttling [guide-thermal]. Speaker coil temperature is handled by the amplifier and
its firmware, with no public API (unconfirmed; none found). Logging headroom (at most once every 10 s) and the status
listener into `PvbRuntime` status costs little and would show, in a long loud session, whether level drift (measured by
the UMIK-1) follows device heat. Do not tie bass to it unless that test shows a link.

### 10. Absolute SPL at the listener (rejected)

On this phone `getStreamVolumeDb` reports about 0 dB at every index, so it adds nothing. The listener distance and room
are unknown, and the vendor limiter after the volume changes the level with the signal. The honest form of this idea is
idea 5 (at the mic) plus idea 6 (measured steps).

### 11. Thermal headroom as speaker protection (rejected)

The headroom scale is defined against the device's throttling statuses [guide-thermal], not the speaker. Backing off
virtual bass on SoC heat would cut bass when the processor is hot, not when the speaker is. If `dumpsys thermalservice`
shows a `SPEAKER` sensor [src-thermal-type], reconsider for the Shizuku or root build only.

### 12. Haptics for bass feel (rejected)

`HapticGenerator` needs audio-coupled haptic playback in the HAL and the `VIBRATE` permission [src-haptic]. The Android
16 envelope API needs compile SDK 36 and is not synchronized with audio [guide-haptics]. A vibration motor at bass
frequencies also adds buzz to the phone body, which works against a speaker app. One `HapticGenerator.isAvailable()`
call in the dev log is enough to close the question.

## Open questions to test on the phone

Run with the phone on USB debugging; the app checks need a dev-mode log line.

1. Volume curves in effect:
   `adb shell dumpsys media.audio_policy > policy.txt`; search for "Volume Groups dump" and the music group's
   `DEVICE_CATEGORY_SPEAKER` points. Full scale (all 0) or a real curve?
2. Vendor configuration files:
   `adb shell getprop ro.boot.product.vendor.sku`;
   `adb shell ls -l /odm/etc /vendor/etc /vendor/etc/audio` and look for `audio_policy*`, `*volume*`, `mixer_paths*`,
   `microphone_characteristics.xml`. Then try reading one from the app without Shizuku.
3. `getStreamVolumeDb` across devices: log every index for `TYPE_BUILTIN_SPEAKER`, `TYPE_WIRED_HEADSET`,
   `TYPE_BLUETOOTH_A2DP`. Is it 0 dB everywhere, or only on the speaker? Also log `isVolumeFixed()`.
4. Active microphones: during `UNPROCESSED` and `VOICE_RECOGNITION` recordings, log `getActiveMicrophones()` (address,
   id, position, channel mapping) and `getActiveRecordingConfiguration()` (`getAudioSource`, `getEffects`,
   `isClientSilenced`). Then `setPreferredDevice` to each `TYPE_BUILTIN_MIC` input and see whether the active mic changes.
5. All declared mic fields: `getMaxSpl`, `getMinSpl`, `getDirectionality`, `getPosition`, `getOrientation` for every
   entry of `getMicrophones()`.
6. Routing: Bluetooth connected, media output switched to the phone; log `getAudioDevicesForAttributes(USAGE_MEDIA)`,
   the same for `USAGE_UNKNOWN`, the track's routed device, and the current `updateRoute` answer.
7. Output thread: while Rootnote plays, `adb shell dumpsys media.audio_flinger`; which output thread has the app's track,
   is it fast, what is the HAL frame count, which effect chains exist. Repeat with `PERFORMANCE_MODE_POWER_SAVING` on a
   test build.
8. Capture policy in callbacks: play from a player that opts out of capture; log the configurations the callback gets
   (usage, capture policy) and compare with `adb shell dumpsys audio`.
9. Thermal: `adb shell dumpsys thermalservice`; is there a `SPEAKER` (type 17) temperature? Log
   `getThermalHeadroom(0)` every 10 s and the status during 15 minutes of loud bass, next to a UMIK-1 level log.
10. Platform spatializer: `getSpatializer().isAvailable()`, `isEnabled()`, `getImmersiveAudioLevel()` with the phone's
    3D audio setting on and off.
11. Haptics: `HapticGenerator.isAvailable()`.
12. Speaker protection traces: `adb logcat -b all` during a loud bass passage, looking for amplifier or protection
    messages from the vendor HAL.

## Sources

API levels (official API diff reports):

- [diff24-ar] https://developer.android.com/sdk/api_diff/24/changes/android.media.AudioRecord
- [diff26-am] https://developer.android.com/sdk/api_diff/26/changes/android.media.AudioManager
- [diff26-at] https://developer.android.com/sdk/api_diff/26/changes/android.media.AudioTrack
- [diff28-am] https://developer.android.com/sdk/api_diff/28/changes/android.media.AudioManager
- [diff28-ar] https://developer.android.com/sdk/api_diff/28/changes/android.media.AudioRecord
- [diff28-pkg] https://developer.android.com/sdk/api_diff/28/changes/pkg_android.media
- [diff29-ar] https://developer.android.com/sdk/api_diff/29/changes/android.media.AudioRecord
- [diff29-arc] https://developer.android.com/sdk/api_diff/29/changes/android.media.AudioRecordingConfiguration
- [diff29-atb] https://developer.android.com/sdk/api_diff/29/changes/android.media.AudioTrack.Builder
- [diff29-at] https://developer.android.com/sdk/api_diff/29/changes/android.media.AudioTrack
- [diff29-aab] https://developer.android.com/sdk/api_diff/29/changes/android.media.AudioAttributes.Builder
- [diff29-pm] https://developer.android.com/sdk/api_diff/29/changes/android.os.PowerManager
- [diff30-pm] https://developer.android.com/sdk/api_diff/30/changes/android.os.PowerManager
- [diff30-arb] https://developer.android.com/sdk/api_diff/30/changes/android.media.AudioRecord.Builder
- [diff30-sensor] https://developer.android.com/sdk/api_diff/30/changes/android.hardware.Sensor
- [diff31-am] https://developer.android.com/sdk/api_diff/31/changes/android.media.AudioManager
- [diff31-fx] https://developer.android.com/sdk/api_diff/31/changes/pkg_android.media.audiofx
- [diff31-os] https://developer.android.com/sdk/api_diff/31/changes/pkg_android.os
- [diff32-am] https://developer.android.com/sdk/api_diff/32/changes/android.media.AudioManager
- [diff33-am] https://developer.android.com/sdk/api_diff/33/changes/android.media.AudioManager
- [diff34-am] https://developer.android.com/sdk/api_diff/34/changes/android.media.AudioManager
- [diff35-pm] https://developer.android.com/sdk/api_diff/35/changes/android.os.PowerManager

Guides and release notes (developer.android.com):

- [guide-thermal] https://developer.android.com/games/optimize/adpf/thermal
- [guide-share] https://developer.android.com/media/platform/sharing-audio-input
- [guide-capture] https://developer.android.com/media/platform/av-capture
- [guide-latency] https://developer.android.com/ndk/guides/audio/audio-latency
- [guide-aaudio] https://developer.android.com/ndk/guides/audio/aaudio/aaudio
- [guide-haptics] https://developer.android.com/develop/ui/views/haptics/haptics-apis
- [guide-pos] https://developer.android.com/develop/sensors-and-location/sensors/sensors_position
- [a15-features] https://developer.android.com/about/versions/15/features
- [a16-features] https://developer.android.com/about/versions/16/features

source.android.com:

- [sac-policy] https://source.android.com/docs/core/audio/implement-policy
- [sac-aidl] https://source.android.com/docs/core/audio/aidl-hidl-comp

AOSP source (android.googlesource.com, `refs/heads/main`):

- [src-mic] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/MicrophoneInfo.java
- [src-micdir] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/MicrophoneDirection.java
- [src-ar] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/AudioRecord.java
- [src-arc] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/AudioRecordingConfiguration.java
- [src-am] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/AudioManager.java
- [src-apc] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/AudioPlaybackConfiguration.java
- [src-mixer] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/AudioMixerAttributes.java
- [src-spatializer] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/Spatializer.java
- [src-haptic] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/audiofx/HapticGenerator.java
- [src-visualizer] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/audiofx/Visualizer.java
- [src-loudness] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/audiofx/LoudnessEnhancer.java
- [src-dp] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/audiofx/DynamicsProcessing.java
- [src-audioshell] https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/services/core/java/com/android/server/audio/AudioManagerShellCommand.java
- [src-voltables] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/config/default_volume_tables.xml
- [src-volumes] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/config/audio_policy_volumes.xml
- [src-volcurve] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/engine/common/src/VolumeCurve.cpp
- [src-volgroup] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/engine/common/src/VolumeGroup.cpp
- [src-enginebase] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/engine/common/src/EngineBase.cpp
- [src-aps] https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/services/audiopolicy/service/AudioPolicyService.cpp
- [src-audioconfig] https://android.googlesource.com/platform/system/media/+/refs/heads/main/audio/include/system/audio_config.h
- [src-sepol-domain] https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/private/domain.te
- [src-sepol-shell] https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/private/shell.te
- [src-thermal-type] https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/main/thermal/aidl/android/hardware/thermal/TemperatureType.aidl

Not read (fetch failed or truncated): the developer.android.com class reference pages, `ThermalManagerService.java`,
the Android 16 CDD audio sections, the `cmd media.audio_policy` command list, and the later parts of `AudioManager.java`
and `AudioRecord.java`. Claims that would need them are marked unconfirmed.
