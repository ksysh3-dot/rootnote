#!/bin/bash
cd ~/r3a-dev/plan16/S19/BY
for s in beyond lastcarn; do
  nohup ~/venv-rootnote/bin/python by_attr.py $s > attr_$s.txt 2> attr_$s.err &
done
wait
