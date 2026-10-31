#!/bin/bash
# dev reruns (4) + held-out (12 vanila + 23 Rayark), 8 parallel
cd ~/r3a-dev/plan16/S19/SL
{
  for s in lastcarn beyond v09 v06; do echo "sl_dev.py $s"; done
  for i in 00 01 02 03 04 05 07 08 10 11 12 13; do echo "sl_held.py v$i"; done
  for i in $(seq -w 0 22); do echo "sl_held.py r$i"; done
} | xargs -P 8 -L 1 sh -c '$HOME/r3a-dev/plan16/V16A/runpy.sh $HOME/r3a-dev/plan16/S19/SL/$1 $2 > $HOME/r3a-dev/plan16/S19/SL/logs/${1%.py}_$2.log 2>&1' _
echo ALLDONE > logs/held_done.txt
