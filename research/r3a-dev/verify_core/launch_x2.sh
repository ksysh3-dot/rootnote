#!/bin/bash
cd ~/r3a-dev/verify_core
for spec in "v4 v4" "v5 v5" "v3c v3c" "v0 v0" "sanity sanity" "v7d v7d"; do
  set -- $spec
  nohup bash ./run_xcheck.sh $1 $2 A,B,C,D > /dev/null 2>&1 &
done
sleep 2
echo launched
