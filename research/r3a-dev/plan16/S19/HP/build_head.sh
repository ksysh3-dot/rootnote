#!/usr/bin/env bash
# builds libpvbcapi.so from the committed HEAD (git archive, no working-tree changes) into HP/lib_head
set -euo pipefail
HP=~/r3a-dev/plan16/S19/HP
rm -rf $HP/head_src; mkdir -p $HP/head_src $HP/lib_head
cd ~/r3-work
git archive HEAD app/src/main/cpp tools/pvb-harness/pvb_capi.cpp | tar -x -C $HP/head_src
cd $HP/head_src
SRC=app/src/main/cpp/libpvb
g++ -std=c++17 -O2 -fno-fast-math -Wall -Wextra -Wpedantic -Werror -fPIC -shared -I$SRC $SRC/pvb_engine.cpp $SRC/pvb_analysis.cpp $SRC/pvb_vb.cpp $SRC/pvb_vb52.cpp tools/pvb-harness/pvb_capi.cpp -o $HP/lib_head/libpvbcapi.so
sha256sum $HP/lib_head/libpvbcapi.so ~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
