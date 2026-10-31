#!/bin/bash
V=~/r3a-dev/plan16/A5P
cd $V
for s in rerise_p logoff45_p; do
  ~/r3a-dev/plan16/V16A/runpy.sh $V/$s.py > $V/$s.log 2>&1 &
done
for lab in b0p0 b0p1 b0p2 b1p0 b1p1 b1p2 b2p0 b2p1 b2p2 b3p0 b3p1 b3p2; do
  ~/r3a-dev/plan16/V16A/runpy.sh $V/right_p.py $lab > $V/right_$lab.log 2>&1
done
wait
echo MISCDONE > $V/misc_done.txt
