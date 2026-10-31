#!/bin/bash
cd ~/r3a-dev/plan16/V16A
for s in rerise16b burst16b logoff45b diag35; do
  ./runpy.sh /home/ksysh/r3a-dev/plan16/V16A/$s.py > $s.log 2>&1
done
echo MISCDONE_B > misc_done_b.txt
