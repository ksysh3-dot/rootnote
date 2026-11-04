#!/usr/bin/env bash
# Builds the JamesDSP engine (libjamesdsp submodule) for the host with a small C API (jdsp_capi.c), for the
# JamesDSP -> PVB chain test (test_jdsp_chain.py). Needs the submodule: git submodule update --init
# app/src/main/cpp/libjamesdsp. Exits 3 (and builds nothing) when the submodule sources are missing.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CPP="$HERE/../../app/src/main/cpp"
J="$CPP/libjamesdsp/Main/libjamesdsp/jni/jamesdsp/jdsp"
OUT="${1:-$HERE/build}"
if [ ! -f "$J/jdspController.c" ]; then
    echo "libjamesdsp submodule missing ($J)" >&2
    exit 3
fi
mkdir -p "$OUT"
CC="${CC:-gcc}"
# Same language mode as the app (CMakeLists: -std=gnu11, -O2); upstream warnings are not ours to fix (newer GCC
# turns some old-C warnings into errors by default: keep them warnings, as the NDK clang build does).
"$CC" -std=gnu11 -O2 -fPIC -shared -w -Wno-error=implicit-function-declaration -Wno-error=incompatible-pointer-types \
    -Wno-error=int-conversion -Wno-error=implicit-int -I"$J" $(find "$J" -name '*.c' | sort) "$CPP/EELStdOutExtension.c" \
    "$HERE/jdsp_capi.c" -o "$OUT/libjdspcapi.so" -lm -lpthread
echo "built: $OUT/libjdspcapi.so"
