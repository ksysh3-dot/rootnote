#!/bin/bash
cd ~/r3a-dev/plan16/S19/SL
for s in "$@"; do
  nohup ~/r3a-dev/plan16/V16A/runpy.sh ~/r3a-dev/plan16/S19/SL/sl_dev.py $s > logs/dev_$s.log 2>&1 &
done
wait
