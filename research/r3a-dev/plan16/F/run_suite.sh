#!/bin/bash
# full existing suite (research_core_metrics) for v1.5 (HEAD lib, 16 params) and rho 1.5/2/3 (new lib, 17 params); also V8 for v15/rho=2 is skipped (timing is report-only, run separately)
F=~/r3a-dev/plan16/F
OUT=$F/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
cd $F
./runpy.sh $F/fmetrics.py --lib $F/build_v15/libpvbcapi.so --algo 15 --resultant voicing=0,ampSource=0 --label v15 --outroot $OUT --ref-json $REFJ > $OUT/v15.log 2>&1 &
for r in 1.5 2 3; do
  ./runpy.sh $F/fmetrics.py --p17 --lib ~/r3-work/tools/pvb-harness/build_core151/libpvbcapi.so --algo 15 --resultant voicing=0,ampSource=0,capRho=$r --label rho$r --outroot $OUT --ref-json $REFJ > $OUT/rho$r.log 2>&1 &
done
wait
echo ALLDONE > $OUT/done.txt
