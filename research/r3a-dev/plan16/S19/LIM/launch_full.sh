#!/bin/bash
cd ~/r3a-dev/plan16/S19/LIM
export PYTHONDONTWRITEBYTECODE=1 LIM_FULL=1
for r in p1 v15 v16b v16c; do for i in 9 6 0 1 2 3 4 5 7 8 10 11 12 13; do echo "$r $i"; done; done | xargs -P 12 -L1 bash -c '~/venv-rootnote/bin/python lim_worker.py $0 $1' > run_full.log 2>&1
echo DONE >> run_full.log
