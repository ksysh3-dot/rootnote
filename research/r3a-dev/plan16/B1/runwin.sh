#!/bin/bash
# usage: runwin.sh t0 t1   -> win_<t0>.txt
cd ~/r3-work/tools/pvb-harness
PYTHONPATH=.:study ~/venv-rootnote/bin/python ~/r3a-dev/plan16/B1/b1_win.py $1 $2 > ~/r3a-dev/plan16/B1/win_$1.txt 2>&1
