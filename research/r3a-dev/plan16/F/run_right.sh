#!/bin/bash
F=~/r3a-dev/plan16/F
cd $F
for r in 1.5 2 3; do
  ./runpy.sh $F/f_right.py rho$r ~/r3-work/tools/pvb-harness/build_core151/libpvbcapi.so $r 2>&1 | tail -2 | cut -c1-600
done
