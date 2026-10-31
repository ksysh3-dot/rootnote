#!/bin/bash
# 19.7 suite rows with the build_core19 library (v1.6-b base). usage: run_suite_hp.sh LABEL:hz:order:comp ...  (parallel, <= 4)
HP=~/r3a-dev/plan16/S19/HP
OUT=$HP/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so
for spec in "$@"; do
  IFS=: read lab hz ord comp <<< "$spec"
  ~/r3a-dev/plan16/V16A/runpy.sh $HP/fmetrics19.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=1.5,windowCreep=16,creepMode=2,betaMin=.05,betaMax=.1,psiSlew=.03,layerHpHz=$hz,layerHpOrder=$ord,layerHpComp=$comp --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo BATCHDONE $@ >> $OUT/done.txt
