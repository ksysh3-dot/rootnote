#!/bin/bash
# A5'' suite rows with the 16d library. usage: run_suite_pp.sh LABEL:betaMin:betaMax:psiSlew:susMin:susMax:onsetMs ...  (parallel)
V=~/r3a-dev/plan16/A5PP
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16d/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab b0 b1 ps s0 s1 ms <<< "$spec"
  ~/r3a-dev/plan16/V16A/runpy.sh $V/fmetrics16d.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=1.5,windowCreep=16,creepMode=2,betaMin=$b0,betaMax=$b1,psiSlew=$ps,betaSusMin=$s0,betaSusMax=$s1,betaOnsetMs=$ms --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo BATCHDONE $@ >> $OUT/done.txt
