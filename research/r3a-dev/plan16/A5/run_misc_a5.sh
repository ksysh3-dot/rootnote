#!/bin/bash
cd ~/r3a-dev/plan16/A5
for s in burst_a5 rerise_a5 logoff45_a5; do
  ~/r3a-dev/plan16/V16A/runpy.sh /home/ksysh/r3a-dev/plan16/A5/$s.py > $s.log 2>&1 &
done
wait
echo MISCDONE_A5 > misc_done.txt
