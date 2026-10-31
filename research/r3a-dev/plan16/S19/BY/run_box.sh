#!/bin/bash
cd ~/r3a-dev/plan16/S19/BY
bash ~/r3a-dev/plan16/V16A/runpy.sh ~/r3a-dev/plan16/S19/BY/by_box.py beyond,lastcarn > box.log 2>&1
for s in beyond lastcarn; do
  ~/venv-rootnote/bin/python by_attr.py $s 140 > attr140_$s.txt 2> attr140_$s.err &
done
wait
