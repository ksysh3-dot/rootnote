#!/bin/bash
cd ~/r3-work
git log -3 --format='%h %ci %s' | cat
echo "--- sources newer than the lib?"
find . -newer tools/pvb-harness/build_core/libpvbcapi.so \( -name '*.cpp' -o -name '*.h' -o -name '*.inc' -o -name '*.c' \) -not -path './tools/pvb-harness/build_*' | head
echo "--- python: source_commit + code hash"
cd tools/pvb-harness
PYTHONPATH=.:study ~/venv-rootnote/bin/python - <<'EOF'
import research_core_metrics as M, test_engine as T
print('cand', T.source_commit('build_core/libpvbcapi.so'))
print('ref ', T.source_commit(str(M.REF_LIB)))
print('code_hash now', M.code_hash())
EOF
ls ~/r3a-dev/core_results/_scratch | head
ls ~/r3-work/tools/pvb-harness/study | head -50
sed -n 1,60p ~/r3-work/tools/pvb-harness/test_engine.py
