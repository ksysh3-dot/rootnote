#!/bin/bash
# usage: run.sh script.py [args]   (script in b12/)
S=$1; shift
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study ~/venv-rootnote/bin/python ~/r3a-dev/plan16/B1/b12/$S "$@"
