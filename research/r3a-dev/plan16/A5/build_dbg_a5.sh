#!/bin/bash
# diagnostic-only libraries (NOT part of the diff): scratch copies of the core sources under A5/dbgsrc
#  F : trace fields A / c / sigma = (ampR, 1, 1), so that the trace-based right-layer F (la0/rows.py voices_core: amp = A c sigma) measures the RENDERED amplitude
#  K : F + oracle slewOnsetMode 3 = the slew limit applied to every harmonic amplitude a_k (not only to A c sigma), mode-0 otherwise
set -euo pipefail
V=~/r3a-dev/plan16/A5
rm -rf $V/dbgsrc; mkdir -p $V/dbgsrc
cp ~/r3-work/app/src/main/cpp/libpvb/* $V/dbgsrc/
cp ~/r3-work/tools/pvb-harness/pvb_capi.cpp $V/dbgsrc/
cd $V/dbgsrc
python3 - <<'EOF'
from pathlib import Path
p = Path.home() / 'r3a-dev/plan16/A5/dbgsrc/pvb_resultant.inc'
t = p.read_text()
old = "row[8] = u.A; row[9] = u.c; row[10] = u.sigma;"
assert t.count(old) == 1
t = t.replace(old, "row[8] = u.ampR; row[9] = 1.0; row[10] = 1.0;")
Path(p.parent / 'pvb_resultant_F.inc').write_text(t)
# K: per-harmonic limit after the a_k are formed
old2 = "        u.a[kk - 2] = gl * g * w[kk - 2] * r * base;\n    }\n"
assert t.count(old2) == 1
new2 = '''        u.a[kk - 2] = gl * g * w[kk - 2] * r * base;
    }
    if (p_.slewOnsetMode == 3 && p_.ampSlewDb > 0) {
        const double gk = std::pow(10.0, p_.ampSlewDb / 20);
        for (int k = 0; k < kPartials; ++k) {
            const double prev = std::max(u.aStart[k], kRSlewFloor), tg = u.a[k];
            double rr = tg;
            if (rr > prev * gk && u.slewFree <= 0) rr = prev * gk;
            else if (rr < prev / gk) { rr = prev / gk; if (rr < kRSlewFloor) rr = tg; }
            u.a[k] = rr;
        }
    }
'''
t = t.replace(old2, new2)
t = t.replace("!(q[20] == 0.0 || q[20] == 1.0 || q[20] == 2.0)", "!(q[20] == 0.0 || q[20] == 1.0 || q[20] == 2.0 || q[20] == 3.0)")
Path(p.parent / 'pvb_resultant_K.inc').write_text(t)
EOF
build() { # name incfile
  mkdir -p $V/dbgsrc/$1; cp $V/dbgsrc/*.h $V/dbgsrc/*.cpp $V/dbgsrc/$1/; cp $V/dbgsrc/$2 $V/dbgsrc/$1/pvb_resultant.inc
  (cd $V/dbgsrc/$1 && g++ -std=c++17 -O2 -fno-fast-math -Wall -Wextra -fPIC -shared -I. pvb_engine.cpp pvb_analysis.cpp pvb_vb.cpp pvb_vb52.cpp pvb_capi.cpp -o libpvbcapi.so)
}
build F pvb_resultant_F.inc
build K pvb_resultant_K.inc
ls -la $V/dbgsrc/F/libpvbcapi.so $V/dbgsrc/K/libpvbcapi.so
