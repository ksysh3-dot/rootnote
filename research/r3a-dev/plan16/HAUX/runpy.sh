#!/bin/bash
# usage: runpy.sh SCRIPT.py [args]   -- same environment as plan16/K (D/V), plus HAUX; no bytecode written outside HAUX
export PYTHONDONTWRITEBYTECODE=1
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study:$HOME/r3a-dev/diag16:$HOME/r3a-dev/verify_core:$HOME/r3a-dev/la0:$HOME/r3a-dev/plan16/A:$HOME/r3a-dev/plan16/S:$HOME/r3a-dev/plan16/D:$HOME/r3a-dev/plan16/K:$HOME/r3a-dev/plan16/HAUX exec ~/venv-rootnote/bin/python "$@"
