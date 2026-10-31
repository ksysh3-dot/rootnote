#!/bin/bash
# chain 3 (after the primary): burst / RERISE / LOGOFF 4.5 / f_osc, right-layer F per row, 14-song render
V=~/r3a-dev/plan16/A5PP
cd $V
while [ ! -f $V/primary_done.txt ]; do sleep 10; done
PY=~/r3a-dev/plan16/V16A/runpy.sh
for s in rerise_pp logoff45_pp burst_pp fosc_pp; do
  $PY $V/$s.py > $V/$s.log 2>&1 &
done
for lab in b0 bb sA30 sA60 sA100 sB30 sB60 sB100; do
  $PY $V/right_pp.py $lab > $V/right_$lab.log 2>&1
done
wait
echo MISCDONE > $V/misc_done.txt
$PY $V/a5pp_song14.py render b0 bb sA30 sA60 sA100 sB30 sB60 sB100 > song14_render.log 2>&1
$PY $V/a5pp_song14.py table b0 bb sA30 sA60 sA100 sB30 sB60 sB100 > song14_table.txt 2>&1
echo SONG14DONE > $V/song14_done.txt