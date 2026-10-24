#!/usr/bin/env bash
# Builds librootnotefx.so (app/src/main/cpp/rootfx) with the NDK for arm64-v8a and armeabi-v7a (API 26), then the
# Magisk module zip (package_module.sh). NDK from $ANDROID_NDK_HOME, else $ANDROID_NDK_LATEST_HOME (GitHub runners),
# else the newest under $ANDROID_HOME/ndk.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../../app/src/main/cpp/rootfx"
OUT="${1:-$HERE/build-android}"
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_LATEST_HOME:-}}"
if [ -z "$NDK" ] && [ -n "${ANDROID_HOME:-}" ]; then NDK="$(ls -d "$ANDROID_HOME"/ndk/* 2>/dev/null | sort -V | tail -1)"; fi
[ -f "$NDK/build/cmake/android.toolchain.cmake" ] || { echo "Android NDK not found" >&2; exit 3; }
for abi in arm64-v8a armeabi-v7a; do
    cmake -S "$SRC" -B "$OUT/$abi" -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI="$abi" -DANDROID_PLATFORM=android-26 -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release
    cmake --build "$OUT/$abi" -j"$(nproc)"
    "$NDK"/toolchains/llvm/prebuilt/*/bin/llvm-strip --strip-unneeded "$OUT/$abi/librootnotefx.so"
    # the only exported symbol must be the effect library entry (AELI)
    syms=$("$NDK"/toolchains/llvm/prebuilt/*/bin/llvm-nm -D --defined-only "$OUT/$abi/librootnotefx.so" | awk '{print $3}')
    echo "$syms" | grep -qx AELI || { echo "$abi: AELI not exported" >&2; exit 1; }
    echo "$abi: $(stat -c %s "$OUT/$abi/librootnotefx.so") bytes; exports: $(echo "$syms" | tr '\n' ' ')"
done
"$HERE/package_module.sh" "$OUT"
