#!/usr/bin/env bash
# Builds the Rootnote audio effect (app/src/main/cpp/rootfx: JamesDSP effect wrapper + PVB engine) for the host as
# build/librootnotefx.so, and the test harness, then runs it (test_rootfx.c). Needs the libjamesdsp submodule and
# tools/pvb-harness/build/libpvbcapi.so (tools/pvb-harness/build_host.sh) for the bit-exact comparison.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CPP="$HERE/../../app/src/main/cpp"
J="$CPP/libjamesdsp/Main/libjamesdsp/jni/jamesdsp"
P="$CPP/libpvb"
OUT="${1:-$HERE/build}"
if [ ! -f "$J/jdsp/jdspController.c" ]; then echo "libjamesdsp submodule missing ($J)" >&2; exit 3; fi
mkdir -p "$OUT/obj"
CC="${CC:-gcc}"; CXX="${CXX:-g++}"
objs=()
# JamesDSP (upstream C; its warnings are not ours: same leniency as build_host_jdsp.sh)
for f in "$HERE/../../app/src/main/cpp/rootfx/jamesdsp_rootnote.c" "$J/cpthread.c" $(find "$J/jdsp" -name '*.c' | sort) "$CPP/EELStdOutExtension.c" "$HERE/android_log_stub.c"; do
    o="$OUT/obj/$(echo "$f" | md5sum | cut -c1-12).o"
    "$CC" -std=gnu11 -O2 -fPIC -w -Wno-error=implicit-function-declaration -Wno-error=incompatible-pointer-types \
        -Wno-error=int-conversion -fvisibility=hidden -I"$J" -I"$J/jdsp" -I"$CPP/rootfx" -c "$f" -o "$o"
    objs+=("$o")
done
for f in "$CPP/rootfx/rootfx_pvb.cpp" "$P/pvb_engine.cpp" "$P/pvb_analysis.cpp" "$P/pvb_vb52.cpp" "$P/pvb_vb.cpp"; do
    o="$OUT/obj/$(echo "$f" | md5sum | cut -c1-12).o"
    "$CXX" -std=c++17 -O2 -fno-fast-math -fPIC -Wall -Wextra -Werror -fvisibility=hidden -I"$P" -I"$CPP/rootfx" -c "$f" -o "$o"
    objs+=("$o")
done
"$CXX" -shared -fPIC "${objs[@]}" -o "$OUT/librootnotefx.so" -lm -lpthread
"$CXX" -std=c++17 -O2 -I"$P" -c "$HERE/param_count.cpp" -o "$OUT/obj/param_count.o"
"$CC" -std=gnu11 -O2 -Wall -Wextra -Werror -I"$J" -I"$CPP/rootfx" -c "$HERE/test_rootfx.c" -o "$OUT/obj/test_rootfx.o"
"$CXX" "$OUT/obj/test_rootfx.o" "$OUT/obj/param_count.o" -o "$OUT/test_rootfx" -ldl -lm
echo "built: $OUT/librootnotefx.so"
"$OUT/test_rootfx" "$OUT/librootnotefx.so" "${PVB_CAPI:-$HERE/../pvb-harness/build/libpvbcapi.so}"
