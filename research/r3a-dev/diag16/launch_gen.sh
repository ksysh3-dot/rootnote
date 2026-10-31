#!/bin/bash
cd ~/r3a-dev/diag16
for t in 60 40 01 05 12 20 23 24 25 26; do
  nohup ./run.sh gen_cache.py Track000$t > logs_gen_$t.txt 2>&1 &
done
wait
echo done > gen_done.txt
