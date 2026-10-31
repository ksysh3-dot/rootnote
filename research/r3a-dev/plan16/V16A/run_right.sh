#!/bin/bash
# usage: run_right.sh LABEL:rho:creep ...   (sequential rows, each uses a pool of 10)
V=~/r3a-dev/plan16/V16A
LIB=~/r3-work/tools/pvb-harness/build_core16a/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr <<< "$spec"
  ./runpy.sh $V/right16.py $lab $LIB $rho $cr > $V/right_$lab.log 2>&1
done
echo RIGHTDONE >> $V/right_done.txt
