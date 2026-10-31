#!/bin/bash
# S19-NF suite rows. usage: run_suite_p.sh LABEL:betaMin:betaMax:psiSlew:nFuture ...
V=~/r3a-dev/plan16/S19/NF
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab b0 b1 ps nf <<< "$spec"
  ~/r3a-dev/plan16/V16A/runpy.sh ~/r3a-dev/plan16/V16A/fmetrics16b.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=1.5,windowCreep=16,creepMode=2,betaMin=$b0,betaMax=$b1,psiSlew=$ps,nFuture=$nf --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo BATCHDONE $@ >> $OUT/done.txt
