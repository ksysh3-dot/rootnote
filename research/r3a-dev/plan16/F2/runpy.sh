#!/bin/bash
# usage: runpy.sh SCRIPT.py [args]  (same environment as plan16/F/runpy.sh plus plan16/F2)
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study:$HOME/r3a-dev/diag16:$HOME/r3a-dev/verify_core:$HOME/r3a-dev/la0:$HOME/r3a-dev/plan16/A:$HOME/r3a-dev/plan16/S:$HOME/r3a-dev/plan16/D:$HOME/r3a-dev/plan16/F:$HOME/r3a-dev/plan16/F2 exec ~/venv-rootnote/bin/python "$@"
