#!/bin/bash
# usage: run_xcheck.sh PARTS OUTNAME [CFGS]
PARTS="$1"; NAME="$2"; CFGS="${3:-A,B,C,D}"
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study ~/venv-rootnote/bin/python research_core_xcheck.py --parts "$PARTS" --cfgs "$CFGS" \
  --out ~/r3a-dev/verify_core/xcheck_$NAME.json > ~/r3a-dev/verify_core/logs/xcheck_$NAME.out 2> ~/r3a-dev/verify_core/logs/xcheck_$NAME.err
echo "exit $?" >> ~/r3a-dev/verify_core/logs/xcheck_$NAME.err
tail -n 25 ~/r3a-dev/verify_core/logs/xcheck_$NAME.err
