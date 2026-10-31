#!/bin/bash
# A1' suite rows with the 16b library. usage: run_suite_b.sh LABEL:capRho:windowCreep:creepMode ...
V=~/r3a-dev/plan16/V16A
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr mode <<< "$spec"
  ./runpy.sh $V/fmetrics16b.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=$rho,windowCreep=$cr,creepMode=$mode --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo ALLDONE_B >> $OUT/done.txt
