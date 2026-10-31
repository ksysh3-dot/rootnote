#!/bin/bash
cd ~/r3a-dev/diag16
./run.sh ../plan16/A/leak.py --trklag 360 > ../plan16/A/leak_run_360.log 2>&1
./run.sh ../plan16/A/leak.py --trklag 400 > ../plan16/A/leak_run_400.log 2>&1
./run.sh ../plan16/A/leak.py --song Track00040 --start 10 > ../plan16/A/leak_run_t40.log 2>&1
echo done > ../plan16/A/leaks_done.txt
