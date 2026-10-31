#!/bin/bash
# full existing suite (research_core_metrics) for the 18.3 rows, all with the v1.6-a library (v1.5 row = both params 0, bit identical, see v0_check16.log)
# usage: run_suite.sh LABEL:capRho:windowCreep ...
V=~/r3a-dev/plan16/V16A
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16a/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr <<< "$spec"
  ./runpy.sh $V/fmetrics16.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=$rho,windowCreep=$cr --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo ALLDONE >> $OUT/done.txt
