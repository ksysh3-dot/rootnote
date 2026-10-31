#!/bin/bash
# chain 2: guard suite, batches of 4 rows (spec: label:betaMin:betaMax:psiSlew:susMin:susMax:onsetMs)
V=~/r3a-dev/plan16/A5PP
cd $V
./run_suite_pp.sh b0:.2:.9:.12:0:0:0 bb:.05:.1:.03:0:0:0 sA30:.2:.9:.03:.05:.1:30 sA60:.2:.9:.03:.05:.1:60
./run_suite_pp.sh sA100:.2:.9:.03:.05:.1:100 sB30:.2:.9:.03:.1:.2:30 sB60:.2:.9:.03:.1:.2:60 sB100:.2:.9:.03:.1:.2:100
# v15: no v1.6-a params
OUT=$V/suite
LIB=~/r3-work/tools/pvb-harness/build_core16d/libpvbcapi.so
~/r3a-dev/plan16/V16A/runpy.sh $V/fmetrics16d.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0 --label v15 --outroot $OUT --ref-json ~/r3a-dev/core_results/p1_baseline/results.json > $OUT/v15.log 2>&1
echo SUITEALL >> $OUT/done.txt