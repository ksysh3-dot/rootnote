#!/bin/bash
# provenance: build libpvbcapi.so from a clean export of 83c862d (outside the repo) and compare with build_core
set -e
D=~/r3a-dev/verify_core/src_83c862d
rm -rf $D; mkdir -p $D
git -C ~/r3-work archive 83c862d | tar -x -C $D
cd $D/tools/pvb-harness
SRC=$D/app/src/main/cpp/libpvb
mkdir -p ~/r3a-dev/verify_core/build_83c862d
time g++ -std=c++17 -O2 -fno-fast-math -Wall -Wextra -Wpedantic -Werror -fPIC -shared -I$SRC $SRC/pvb_engine.cpp $SRC/pvb_analysis.cpp $SRC/pvb_vb.cpp $SRC/pvb_vb52.cpp pvb_capi.cpp -o ~/r3a-dev/verify_core/build_83c862d/libpvbcapi.so
sha256sum ~/r3a-dev/verify_core/build_83c862d/libpvbcapi.so ~/r3-work/tools/pvb-harness/build_core/libpvbcapi.so
ls -la ~/r3a-dev/verify_core/build_83c862d/libpvbcapi.so ~/r3-work/tools/pvb-harness/build_core/libpvbcapi.so
git -C ~/r3-work diff --stat 91aac1a 83c862d | tail -5
