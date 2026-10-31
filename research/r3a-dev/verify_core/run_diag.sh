#!/bin/bash
# usage: run_diag.sh SCRIPT (a python file in ~/r3a-dev/verify_core/) [args]
S="$1"; shift
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study:$HOME/r3a-dev/verify_core ~/venv-rootnote/bin/python $HOME/r3a-dev/verify_core/$S "$@"
