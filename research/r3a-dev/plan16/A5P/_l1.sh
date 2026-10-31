#!/bin/bash
cd ~/r3a-dev/plan16/A5P
cp ../A5/primary_p1.json ../A5/primary_v15.json .
sed -i "s/R\['base'\]/R['b0p0']/" a5_ptable.py
nohup ~/r3a-dev/plan16/V16A/runpy.sh ~/r3a-dev/plan16/A5P/p_primary.py b0p0 b0p1 b0p2 b1p0 b1p1 b1p2 b2p0 b2p1 b2p2 b3p0 b3p1 b3p2 > primary.log 2>&1 &
sleep 15; cat primary.log; free -g | head -2
