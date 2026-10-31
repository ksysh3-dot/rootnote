#!/bin/bash
# usage: build.sh OUTDIR [extra g++ flags]   -- libpvbcapi.so with the same flags as tools/pvb-harness/build_host.sh (capi only)
set -euo pipefail
OUT="$1"; shift
cd ~/r3-work/tools/pvb-harness
S=../../app/src/main/cpp/libpvb
mkdir -p "$OUT"
g++ -std=c++17 -O2 -fno-fast-math -Wall -Wextra -Wpedantic -Werror -fPIC -shared "$@" -I$S $S/pvb_engine.cpp $S/pvb_analysis.cpp $S/pvb_vb.cpp $S/pvb_vb52.cpp pvb_capi.cpp -o "$OUT/libpvbcapi.so"
sha256sum "$OUT/libpvbcapi.so" | tee "$OUT/sha256.txt"
