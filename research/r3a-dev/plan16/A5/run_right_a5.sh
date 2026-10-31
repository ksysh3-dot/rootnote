#!/bin/bash
# usage: run_right_a5.sh LABEL ...   (sequential rows, each uses a pool of 10)
V=~/r3a-dev/plan16/A5
cd $V
for lab in "$@"; do
  ~/r3a-dev/plan16/V16A/runpy.sh $V/right_a5.py $lab > $V/right_$lab.log 2>&1
done
echo RIGHTDONE_A5 >> $V/right_done.txt
