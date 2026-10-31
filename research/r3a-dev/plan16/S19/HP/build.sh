#!/usr/bin/env bash
# usage: build.sh OUTDIR [extra g++ flags]   (same flags as tools/pvb-harness/build_host.sh, libpvbcapi.so only)
set -euo pipefail
cd ~/r3-work
OUT="$1"; shift
mkdir -p "$OUT"
SRC=app/src/main/cpp/libpvb
F="-std=c++17 -O2 -fno-fast-math -Wall -Wextra -Wpedantic -Werror -fPIC -shared"
g++ $F "$@" -I$SRC $SRC/pvb_engine.cpp $SRC/pvb_analysis.cpp $SRC/pvb_vb.cpp $SRC/pvb_vb52.cpp tools/pvb-harness/pvb_capi.cpp -o "$OUT/libpvbcapi.so"
sha256sum "$OUT/libpvbcapi.so" | tee "$OUT/sha256.txt"
