#!/bin/bash
# usage: run_right_b.sh LABEL:rho:creep:mode ...   (sequential rows, each uses a pool of 10)
V=~/r3a-dev/plan16/V16A
LIB=~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr mode <<< "$spec"
  ./runpy.sh $V/right16b.py $lab $LIB $rho $cr $mode > $V/right_$lab.log 2>&1
done
echo RIGHTDONE_B >> $V/right_done.txt
