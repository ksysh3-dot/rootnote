#!/usr/bin/env bash
# Builds the engine for the host: libpvbcapi.so (Python tests) and libpvbengine.so (JVM/JNI tests).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../../app/src/main/cpp/libpvb"
OUT="${1:-$HERE/build}"
mkdir -p "$OUT"
CXX="${CXX:-g++}"
FLAGS="-std=c++17 -O2 -fno-fast-math -Wall -Wextra -Wpedantic -Werror -fPIC -shared"
"$CXX" $FLAGS -I"$SRC" "$SRC/pvb_engine.cpp" "$SRC/pvb_analysis.cpp" "$SRC/pvb_vb.cpp" "$SRC/pvb_vb52.cpp" "$HERE/pvb_capi.cpp" -o "$OUT/libpvbcapi.so"
if [ -z "${JAVA_HOME:-}" ]; then JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"; fi
"$CXX" $FLAGS -I"$SRC" -I"$JAVA_HOME/include" -I"$JAVA_HOME/include/linux" \
    "$SRC/pvb_engine.cpp" "$SRC/pvb_analysis.cpp" "$SRC/pvb_vb.cpp" "$SRC/pvb_vb52.cpp" "$SRC/pvb_jni.cpp" -o "$OUT/libpvbengine.so"
# Which source this build is (review question 74): a WAV rendered with it can name the exact engine.
REPO="$HERE/../.."
if SHA="$(git -C "$REPO" rev-parse --short=12 HEAD 2>/dev/null)"; then
    git -C "$REPO" diff --quiet HEAD -- app/src/main/cpp tools/pvb-harness/pvb_capi.cpp || SHA="$SHA-dirty"
else
    SHA="unknown"
fi
echo "$SHA" > "$OUT/source_commit.txt"
echo "built: $OUT/libpvbcapi.so $OUT/libpvbengine.so" "(source $SHA)"
