#!/bin/bash
# S19-SL suite row nf48 (v1.6-c + nFuture 48) on build_core19. v1.6-c / P1 values come from S19/HP/suite/hp8_150c1/results.json
SL=~/r3a-dev/plan16/S19/SL
OUT=$SL/suite; mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so
lab=nf48
~/r3a-dev/plan16/V16A/runpy.sh ~/r3a-dev/plan16/S19/HP/fmetrics19.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=1.5,windowCreep=16,creepMode=2,betaMin=.05,betaMax=.1,psiSlew=.03,layerHpHz=150,layerHpOrder=8,layerHpComp=1,nFuture=48 --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1
echo DONE $lab >> $OUT/done.txt
