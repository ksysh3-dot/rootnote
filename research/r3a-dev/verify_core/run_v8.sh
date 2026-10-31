#!/bin/bash
# V8 alone (nothing else running), unmodified suite code, defaults = config A
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study ~/venv-rootnote/bin/python research_core_metrics.py \
  --lib build_core/libpvbcapi.so --algo 15 --resultant "voicing=0,ampSource=0" --label verify_A_v8 --metrics ZZ --v8 \
  > ~/r3a-dev/verify_core/logs/verify_A_v8.out 2> ~/r3a-dev/verify_core/logs/verify_A_v8.err
echo "exit $?" >> ~/r3a-dev/verify_core/logs/verify_A_v8.err
