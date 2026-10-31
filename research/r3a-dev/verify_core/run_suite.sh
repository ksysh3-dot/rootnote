#!/bin/bash
# usage: run_suite.sh LABEL "resultant k=v,.." [extra args...]
# Runs the pre-registered metric suite (unmodified) on algo 15 of the candidate build.
LABEL="$1"; RES="$2"; shift 2
cd ~/r3-work/tools/pvb-harness
mkdir -p ~/r3a-dev/verify_core/logs
PYTHONPATH=.:study ~/venv-rootnote/bin/python research_core_metrics.py \
  --lib build_core/libpvbcapi.so --algo 15 --resultant "$RES" --label "$LABEL" "$@" \
  > ~/r3a-dev/verify_core/logs/$LABEL.out 2> ~/r3a-dev/verify_core/logs/$LABEL.err
echo "exit $?" >> ~/r3a-dev/verify_core/logs/$LABEL.err
