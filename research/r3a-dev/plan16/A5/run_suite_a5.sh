#!/bin/bash
# A5 suite rows (research_core_metrics via fmetrics_a5.py) with the 16c library. usage: run_suite_a5.sh LABEL:capRho:windowCreep:creepMode:slew:onset ...
V=~/r3a-dev/plan16/A5
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16c/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr mode sl on <<< "$spec"
  ~/r3a-dev/plan16/V16A/runpy.sh $V/fmetrics_a5.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=$rho,windowCreep=$cr,creepMode=$mode,ampSlewDb=$sl,slewOnsetMode=$on --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo ALLDONE_A5 >> $OUT/done.txt
