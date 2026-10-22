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
# service read/write arithmetic (pure Kotlin)
OUTP="$HERE/../build/jvm-pump"
rm -rf "$OUTP"; mkdir -p "$OUTP"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/../../../app/src/main/java/me/timschneeberger/rootlessjamesdsp/service/PcmPump.kt" "$HERE/PcmPumpTest.kt" -d "$OUTP"
java -cp "$OUTP:$KOTLIN_STDLIB" PcmPumpTestKt
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
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$HERE/Alpha3SettingsTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" Alpha3SettingsTestKt
# Alpha 3.1 per-song level memory: key normalisation, LRU store, recall/save decisions (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/TrackLevelMemory.kt" "$HERE/TrackLevelMemoryTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" TrackLevelMemoryTestKt
# Alpha 3.2 volume-linked virtual bass strength: volume %, reduction, effective level, settings (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$HERE/VolumeLevelLinkTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" VolumeLevelLinkTestKt
# Alpha 3.3 live blind A/B: seeded shuffle, record JSON/CSV, tally, file store, comparison catalogue (pure Kotlin).
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/PvbRuntime.kt" "$APP/PvbAbConditions.kt" "$APP/LiveAb.kt" "$APP/LiveAbComparisons.kt" "$HERE/LiveAbTest.kt" -d "$OUTA"
java -cp "$OUTA:$KOTLIN_STDLIB" LiveAbTestKt
$KOTLINC -classpath "$KOTLIN_STDLIB" "$APP/PvbModels.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/Alpha2JniTest.kt" -d "$OUTA"
java -Djava.library.path="$HERE/../build" -cp "$OUTA:$KOTLIN_STDLIB" Alpha2JniTestKt "$OUTA"
python3 "$HERE/compare_alpha2_jni.py" "$HERE/../build/libpvbcapi.so" "$OUTA"

# General distribution build: device profiles (shipped assets), safe caps, first-run gate, backup exclusions.
OUTG="$HERE/../build/jvm-general"
rm -rf "$OUTG"; mkdir -p "$OUTG"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/DeviceProfiles.kt" "$APP/HomeLogic.kt" "$HERE/GeneralBuildTest.kt" -d "$OUTG"
java -cp "$OUTG:$KOTLIN_STDLIB" GeneralBuildTestKt "$HERE/../../.."

# General build home screen: master/headline, preset chips from model + level, caps, volume-link line, en/ko strings.
OUTH="$HERE/../build/jvm-home"
rm -rf "$OUTH"; mkdir -p "$OUTH"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/HomeLogic.kt" "$HERE/HomeLogicTest.kt" -d "$OUTH"
java -cp "$OUTH:$KOTLIN_STDLIB" HomeLogicTestKt "$HERE/../../.."

# JamesDSP -> PVB chain: route table, module sealing and restore of the user's values, 16-bit conversion against the
# PVB engine's own 16-bit path (host libpvbengine.so), en/ko strings of the chain notes.
OUTC="$HERE/../build/jvm-chain"
rm -rf "$OUTC"; mkdir -p "$OUTC"
$KOTLINC -classpath "$KOTLIN_STDLIB" "$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/JdspChain.kt" "$HERE/JdspChainTest.kt" -d "$OUTC"
java -Djava.library.path="$HERE/../build" -cp "$OUTC:$KOTLIN_STDLIB" JdspChainTestKt "$HERE/../../.." --jni
