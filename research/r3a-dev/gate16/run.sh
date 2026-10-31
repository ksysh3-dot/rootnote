#!/bin/bash
# usage: run.sh SCRIPT.py [args]   (script in ~/r3a-dev/gate16/)
S="$1"; shift
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study:$HOME/r3a-dev/diag16:$HOME/r3a-dev/verify_core ~/venv-rootnote/bin/python $HOME/r3a-dev/gate16/$S "$@"
