#!/usr/bin/env bash
# JVM tests touched by APP16d (strength -6..12, model level trim, chip), as in run_jvm_test.sh, against build_app16c
# (engine unchanged since), with the Android Studio kotlinc 2.3.20.
set -euo pipefail
source ~/venv-rootnote/bin/activate
K='/mnt/c/Program Files/Android/Android Studio/plugins/Kotlin/kotlinc'
KOTLINC="$K/bin/kotlinc"
STD="$K/lib/kotlin-stdlib.jar"
R=/home/ksysh/r3-app
HERE=$R/tools/pvb-harness/jvm
APP=$R/app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb
B=$R/tools/pvb-harness/build_app16c
O=$B/jvm-d
rm -rf "$O"; mkdir -p "$O"
COMMON=("$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt")
run() { # name, extra sources..., then test file (last), args after --
  local name="$1"; shift
  local srcs=(); local args=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do srcs+=("$1"); shift; done
  [ $# -gt 0 ] && shift
  args=("$@")
  mkdir -p "$O/$name"
  "$KOTLINC" -classpath "$STD" "${srcs[@]}" -d "$O/$name" 2>&1 | grep -v '^warning' || true
  java -Djava.library.path="$B" -cp "$O/$name:$STD" "$name" "${args[@]}"
}
run Alpha3SettingsTestKt "${COMMON[@]}" "$HERE/Alpha3SettingsTest.kt"
run VolumeLevelLinkTestKt "${COMMON[@]}" "$HERE/VolumeLevelLinkTest.kt"
run LiveAbTestKt "${COMMON[@]}" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/PvbRuntime.kt" "$APP/PvbAbConditions.kt" "$APP/LiveAb.kt" "$APP/LiveAbComparisons.kt" "$HERE/LiveAbTest.kt"
run HomeLogicTestKt "${COMMON[@]}" "$APP/HomeLogic.kt" "$HERE/HomeLogicTest.kt" -- $R
run TrackLevelMemoryTestKt "${COMMON[@]}" "$APP/TrackLevelMemory.kt" "$HERE/TrackLevelMemoryTest.kt"
run PvbEngineParamsTestKt "${COMMON[@]}" "$APP/PvbEngine.kt" "$APP/PvbNative.kt" "$APP/PvbEngineParams.kt" "$HERE/PvbEngineParamsTest.kt"
run ExperimentalSettingsTestKt "${COMMON[@]}" "$APP/DeviceProfiles.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/ExperimentalSettingsTest.kt" -- $R
run DevModeTestKt "${COMMON[@]}" "$APP/DeviceProfiles.kt" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/DevShareCode.kt" "$APP/SettingsSummary.kt" "$APP/DevWarnings.kt" "$APP/DevTestSound.kt" "$HERE/DevModeTest.kt" -- $R --jni
run GeneralBuildTestKt "${COMMON[@]}" "$APP/DeviceProfiles.kt" "$APP/HomeLogic.kt" "$HERE/GeneralBuildTest.kt" -- $R
run Alpha2JniTestKt "${COMMON[@]}" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/Alpha2JniTest.kt" -- "$O/jni"
python3 "$HERE/compare_alpha2_jni.py" "$B/libpvbcapi.so" "$O/jni"
