#!/bin/bash
# diagnostic-only library (NOT part of the diff): copy of the core sources + a per-hop log of N_J (held / applied), max LS SNR and the set-falling flag; scratch copy under V16A/dbgsrc
set -euo pipefail
V=~/r3a-dev/plan16/V16A
rm -rf $V/dbgsrc; mkdir -p $V/dbgsrc
cp ~/r3-work/app/src/main/cpp/libpvb/* $V/dbgsrc/
cp ~/r3-work/tools/pvb-harness/pvb_capi.cpp $V/dbgsrc/
python3 - <<'EOF'
from pathlib import Path
p = Path.home() / 'r3a-dev/plan16/V16A/dbgsrc/pvb_resultant.inc'
t = p.read_text()
old = "void ResultantCore::solveLs(Ctx& cx) {"
new = '''static double gDbg[6 * 40000]; static int gDbgN = 0;
extern "C" __attribute__((visibility("default"))) int a1p_dbg_n() { return gDbgN; }
extern "C" __attribute__((visibility("default"))) void a1p_dbg_copy(double* o) { for (int i = 0; i < 6 * gDbgN; ++i) o[i] = gDbg[i]; gDbgN = 0; }
void ResultantCore::solveLs(Ctx& cx) {'''
assert t.count(old) == 1
t = t.replace(old, new)
old2 = "    cx.npJ = npJ; cx.nf = nf;\n"
new2 = old2 + '''    if (gDbgN < 40000) { double* o = gDbg + 6 * gDbgN++; o[0] = static_cast<double>(hopCount_); o[1] = npJh; o[2] = npJ; o[3] = sMax; o[4] = rSnrFalling(sMaxH_, sMaxHn_, sMax) ? 1 : 0; o[5] = nv; }
'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
p.write_text(t)
EOF
cd $V/dbgsrc
g++ -std=c++17 -O2 -fno-fast-math -Wall -Wextra -fPIC -shared -DPVB_RESEARCH_CAPSTATS -I. pvb_engine.cpp pvb_analysis.cpp pvb_vb.cpp pvb_vb52.cpp pvb_capi.cpp -o $V/dbgsrc/libpvbcapi_dbg.so
ls -la $V/dbgsrc/libpvbcapi_dbg.so
