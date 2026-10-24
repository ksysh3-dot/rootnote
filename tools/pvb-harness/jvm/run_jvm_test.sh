#!/usr/bin/env bash
# Compiles the app's pure-Kotlin PVB classes plus JniSmokeTest.kt and runs them on the host JVM against
# build/libpvbengine.so, then compares the JNI output with the C API output (bit exact).
# Needs a Kotlin compiler: set KOTLINC to a kotlinc-compatible command and KOTLIN_STDLIB to the stdlib jar.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb"
OUT="$HERE/../build/jvm"
rm -rf "$OUT"; mkdir -p "$OUT"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/VolumeCompensation.kt" "$HERE/JniSmokeTest.kt" -d "$OUT"
java -Djava.library.path="$HERE/../build" -cp "$OUT:$KOTLIN_STDLIB" JniSmokeTestKt "$OUT/jni_out.f32"
python3 "$HERE/compare_jni.py" "$HERE/../build/libpvbcapi.so" "$OUT/jni_out.f32"
# measurement math (pure Kotlin)
OUTM="$HERE/../build/jvm-measure"
rm -rf "$OUTM"; mkdir -p "$OUTM"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbMeasureMath.kt" "$HERE/MeasureMathTest.kt" -d "$OUTM"
java -cp "$OUTM:$KOTLIN_STDLIB" MeasureMathTestKt
# bass fit ("저음 맞추기") test logic (pure Kotlin)
OUTB="$HERE/../build/jvm-bassfit"
rm -rf "$OUTB"; mkdir -p "$OUTB"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbMeasureMath.kt" "$APP/BassFit.kt" "$HERE/BassFitTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" BassFitTestKt
# bass fit session: step order, a fresh question order per seed, what the answers apply (pure Kotlin)
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbMeasureMath.kt" "$APP/BassFit.kt" "$APP/BassFitSession.kt" "$HERE/BassFitSessionTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" BassFitSessionTestKt
# "마이크가 듣는 값": the microphone's reference floor from the probe sweep (pure Kotlin)
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbMeasureMath.kt" "$APP/BassFit.kt" "$APP/DevTestSound.kt" "$APP/SpeakerProbe.kt" "$HERE/SpeakerProbeTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" SpeakerProbeTestKt
# service read/write arithmetic (pure Kotlin)
OUTP="$HERE/../build/jvm-pump"
rm -rf "$OUTP"; mkdir -p "$OUTP"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/service/PcmPump.kt" "$HERE/PcmPumpTest.kt" -d "$OUTP"
java -cp "$OUTP:$KOTLIN_STDLIB" PcmPumpTestKt
# spatial speaker balance, cross method with the phone's microphones (pure Kotlin)
OUTSB="$HERE/../build/jvm-spatial-balance"
rm -rf "$OUTSB"; mkdir -p "$OUTSB"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/DevTestSound.kt" "$APP/SpatialBalance.kt" "$HERE/SpatialBalanceTest.kt" -d "$OUTSB"
java -cp "$OUTSB:$KOTLIN_STDLIB" SpatialBalanceTestKt
# service silence pause (battery; pure Kotlin)
OUTG="$HERE/../build/jvm-silence"
rm -rf "$OUTG"; mkdir -p "$OUTG"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/service/SilenceGate.kt" "$HERE/SilenceGateTest.kt" -d "$OUTG"
java -cp "$OUTG:$KOTLIN_STDLIB" SilenceGateTestKt
# archive and import path checks (pure Kotlin)
OUTS="$HERE/../build/jvm-safepaths"
rm -rf "$OUTS"; mkdir -p "$OUTS"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/utils/storage/SafePaths.kt" "$HERE/SafePathsTest.kt" -d "$OUTS"
java -cp "$OUTS:$KOTLIN_STDLIB" SafePathsTestKt
# Opt-in diagnostic rolling history and exact WAV export (pure Kotlin, concurrent freeze included).
OUTB="$HERE/../build/jvm-buzz"
rm -rf "$OUTB"; mkdir -p "$OUTB"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/BuzzRing.kt" "$APP/BuzzWav.kt" "$HERE/BuzzRingTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" BuzzRingTestKt
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/BuzzMute.kt" "$HERE/BuzzMuteTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" BuzzMuteTestKt
# Same-pass generated/full stems through the actual native bridge (both PCM formats).
OUTD="$HERE/../build/jvm-diagnostic-stems"
mkdir -p "$OUTD"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/BuzzRing.kt" "$HERE/DiagnosticJniTest.kt" -d "$OUTD"
java -Djava.library.path="$HERE/../build" -cp "$OUTD:$KOTLIN_STDLIB" DiagnosticJniTestKt

# Full-resolution harmonic history ownership and window coverage.
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/BuzzRing.kt" "$HERE/HarmonicHistoryTest.kt" -d "$OUTB"
java -cp "$OUTB:$KOTLIN_STDLIB" HarmonicHistoryTestKt

# Actual saved-settings migration and the selectable model catalogue (Android-free host stub).
OUTA="$HERE/../build/jvm-alpha2"
mkdir -p "$OUTA"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$HERE/Alpha3SettingsTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" Alpha3SettingsTestKt
# Alpha 3.1 per-song level memory: key normalisation, LRU store, recall/save decisions (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/TrackLevelMemory.kt" "$HERE/TrackLevelMemoryTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" TrackLevelMemoryTestKt
# Alpha 3.2 volume-linked virtual bass strength: volume %, reduction, effective level, settings (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$HERE/VolumeLevelLinkTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" VolumeLevelLinkTestKt
# engine parameter encoding (PvbController.push's rules; pure Kotlin)
OUTEP="$HERE/../build/jvm-engine-params"
rm -rf "$OUTEP"; mkdir -p "$OUTEP"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbEngine.kt" "$APP/PvbNative.kt" "$APP/PvbEngineParams.kt" "$HERE/PvbEngineParamsTest.kt" -d "$OUTEP"
java -cp "$OUTEP:$KOTLIN_STDLIB" PvbEngineParamsTestKt
# "pause fully while an excluded app is in front": main-window rule (pure Kotlin)
OUTFP="$HERE/../build/jvm-foreground-pause"
rm -rf "$OUTFP"; mkdir -p "$OUTFP"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/service/ForegroundPause.kt" "$HERE/ForegroundPauseTest.kt" -d "$OUTFP"
java -cp "$OUTFP:$KOTLIN_STDLIB" ForegroundPauseTestKt
# Alpha 3.3 live blind A/B: seeded shuffle, record JSON/CSV, tally, file store, comparison catalogue (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/PvbRuntime.kt" "$APP/PvbAbConditions.kt" "$APP/LiveAb.kt" "$APP/LiveAbComparisons.kt" "$HERE/LiveAbTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" LiveAbTestKt
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/Alpha2JniTest.kt" -d "$OUTA"
java -Djava.library.path="$HERE/../build" -cp "$OUTA:$KOTLIN_STDLIB" Alpha2JniTestKt "$OUTA"
python3 "$HERE/compare_alpha2_jni.py" "$HERE/../build/libpvbcapi.so" "$OUTA"

# General distribution build: device profiles (shipped assets), safe caps, first-run gate, backup exclusions.
OUTG="$HERE/../build/jvm-general"
rm -rf "$OUTG"; mkdir -p "$OUTG"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/DeviceProfiles.kt" "$APP/HomeLogic.kt" "$HERE/GeneralBuildTest.kt" -d "$OUTG"
java -cp "$OUTG:$KOTLIN_STDLIB" GeneralBuildTestKt "$HERE/../../.."

# Experimental layer options: keys, defaults off in settings and preference XML, not in device profiles, en/ko strings.
OUTX="$HERE/../build/jvm-experimental"
rm -rf "$OUTX"; mkdir -p "$OUTX"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/DeviceProfiles.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/ExperimentalSettingsTest.kt" -d "$OUTX"
java -cp "$OUTX:$KOTLIN_STDLIB" ExperimentalSettingsTestKt "$HERE/../../.."

# General build home screen: master/headline, preset chips from model + level, caps, volume-link line, en/ko strings.
OUTH="$HERE/../build/jvm-home"
rm -rf "$OUTH"; mkdir -p "$OUTH"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/HomeLogic.kt" "$HERE/HomeLogicTest.kt" -d "$OUTH"
java -cp "$OUTH:$KOTLIN_STDLIB" HomeLogicTestKt "$HERE/../../.."

# General build, first week: onboarding pages, battery step, kill detection, quick exclusions (= manifest queries),
# en/ko strings of these screens and of the first-run notice (pure Kotlin).
OUTF="$HERE/../build/jvm-firstweek"
rm -rf "$OUTF"; mkdir -p "$OUTF"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/FirstWeek.kt" "$APP/KeepWords.kt" "$HERE/FirstWeekTest.kt" -d "$OUTF"
java -cp "$OUTF:$KOTLIN_STDLIB" FirstWeekTestKt "$HERE/../../.."

# JamesDSP -> PVB chain: route table, module sealing and restore of the user's values, 16-bit conversion against the
# PVB engine's own 16-bit path (host libpvbengine.so), en/ko strings of the chain notes.
OUTC="$HERE/../build/jvm-chain"
rm -rf "$OUTC"; mkdir -p "$OUTC"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/JdspChain.kt" "$HERE/JdspChainTest.kt" -d "$OUTC"
java -Djava.library.path="$HERE/../build" -cp "$OUTC:$KOTLIN_STDLIB" JdspChainTestKt "$HERE/../../.." --jni

# Developer mode (general build): value specs and settings, share code, warning rules and counting, evidence badges from
# the device profile, test sounds, en/ko strings, and the engine's developer-mode meters through JNI.
OUTV="$HERE/../build/jvm-devmode"
rm -rf "$OUTV"; mkdir -p "$OUTV"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/DeviceProfiles.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/DevShareCode.kt" "$APP/SettingsSummary.kt" "$APP/DevWarnings.kt" "$APP/DevTestSound.kt" "$HERE/DevModeTest.kt" -d "$OUTV"
java -Djava.library.path="$HERE/../build" -cp "$OUTV:$KOTLIN_STDLIB" DevModeTestKt "$HERE/../../.." --jni
