#!/usr/bin/env bash
# The JVM tests touched by APP16, run as in tools/pvb-harness/jvm/run_jvm_test.sh but against build_app16c and with the
# Kotlin compiler bundled with Android Studio (2.3.20; CI pins its own).
set -euo pipefail
K='/mnt/c/Program Files/Android/Android Studio/plugins/Kotlin/kotlinc'
KOTLINC="$K/bin/kotlinc"
STD="$K/lib/kotlin-stdlib.jar"
HERE=/home/ksysh/r3-app/tools/pvb-harness/jvm
APP=/home/ksysh/r3-app/app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb
B=/home/ksysh/r3-app/tools/pvb-harness/build_app16c
OUTA=$B/jvm-alpha2
rm -rf "$OUTA"; mkdir -p "$OUTA"
COMMON=("$HERE/stubs/SharedPreferences.kt" "$APP/PvbModels.kt" "$APP/PvbSettings.kt" "$APP/DevParams.kt" "$APP/PvbBuild.kt" "$APP/VolumeLevelLink.kt")
"$KOTLINC" -classpath "$STD" "${COMMON[@]}" "$HERE/Alpha3SettingsTest.kt" -d "$OUTA"
java -cp "$OUTA:$STD" Alpha3SettingsTestKt
"$KOTLINC" -classpath "$STD" "${COMMON[@]}" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$APP/PvbRuntime.kt" "$APP/PvbAbConditions.kt" "$APP/LiveAb.kt" "$APP/LiveAbComparisons.kt" "$HERE/LiveAbTest.kt" -d "$OUTA"
java -cp "$OUTA:$STD" LiveAbTestKt
"$KOTLINC" -classpath "$STD" "${COMMON[@]}" "$APP/PvbNative.kt" "$APP/PvbEngine.kt" "$HERE/Alpha2JniTest.kt" -d "$OUTA"
java -Djava.library.path="$B" -cp "$OUTA:$STD" Alpha2JniTestKt "$OUTA"
python3 "$HERE/compare_alpha2_jni.py" "$B/libpvbcapi.so" "$OUTA"
