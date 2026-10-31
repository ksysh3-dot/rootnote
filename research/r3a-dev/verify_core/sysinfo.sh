#!/bin/bash
nproc
free -g | head -2
ls -la ~/r3a-dev/core_results/ ~/r3a-dev/core_results/p1_baseline/
~/venv-rootnote/bin/python - <<'EOF'
import json
j = json.load(open('/home/ksysh/r3a-dev/core_results/p1_baseline/results.json'))
print(j['meta'])
EOF
cd ~/r3-work
git diff --stat HEAD | tail -3
sha256sum tools/pvb-harness/build_core/libpvbcapi.so ~/r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so
ls -la tools/pvb-harness/build_core/libpvbcapi.so ~/r3-ref-core/tools/pvb-harness/build_ref/libpvbcapi.so
cd ~/r3-ref-core && git log --oneline | head -2 && git status --short | head
