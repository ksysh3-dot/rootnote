#!/usr/bin/env bash
set -euo pipefail
cd /home/ksysh/r3a-dev/plan16/APP16
sed -e 's#build_app16/#build_app16c/#; s#build_app16_ref#build_app16c_ref#' \
    -e 's#params=V16B#params=V16C#g' \
    -e "s#'v16b': V16B, #'v16b': V16B, 'v16c': V16C, #" \
    -e 's#V0_app16.json#v0_app16c.json#; s#v0_app16.json#v0_app16c.json#' \
    -e 's#16 + set(v1.6-b)#16 + set(v1.6-c)#' v0_app16.py > v0_app16c.py
python3 - <<'EOF'
p='/home/ksysh/r3a-dev/plan16/APP16/v0_app16c.py'
s=open(p).read()
s=s.replace("V16B = dict(capRho=1.5, windowCreep=16, creepMode=2, betaMin=0.05, betaMax=0.1, psiSlew=0.03)",
"V16B = dict(capRho=1.5, windowCreep=16, creepMode=2, betaMin=0.05, betaMax=0.1, psiSlew=0.03)\nV16C = dict(V16B, layerHpHz=150, layerHpOrder=8, layerHpComp=1)")
s=s.replace("        y15d, _, _ = run(NEW, xx, [(0, 15)], blk, trace=True)\n",
"        y15d, _, _ = run(NEW, xx, [(0, 15)], blk, trace=True)\n        y15b, _, _ = run(NEW, xx, [(0, 15)], blk, params=V16B, trace=True)\n")
s=s.replace("            rec('E1', f'16 != plain 15 (sanity) {nm}'",
"            rec('E1', f'16 != 15+set(v1.6-b) (HP really on) {nm}', not eq(y16, y15b), f'max|d|={float(np.max(np.abs(y16 - y15b))):.3g}')\n            rec('E1', f'16 != plain 15 (sanity) {nm}'")
s=s.replace("params=V16B, trace=True)\n    rec('E1sw'","params=V16C, trace=True)\n    rec('E1sw'")
open(p,'w').write(s)
EOF
grep -n 'V16' v0_app16c.py | head -30
sed -e 's#v0_app16.py#v0_app16c.py#' -e 's#build_app16/#build_app16c/#' e2_rule.py > e2_rule_c.py
sed -e 's#build_app16/#build_app16c/#g' jni_1516.py > jni_1516c.py
sed -e 's#build_app16#build_app16c#g' jvm_app16.sh > jvm_app16c.sh
sed -n 1,12p e2_rule_c.py | head -5
