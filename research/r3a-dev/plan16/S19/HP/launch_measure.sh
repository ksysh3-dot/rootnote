#!/bin/bash
cd ~/r3a-dev/plan16/S19/HP
NP=6 nohup ~/r3a-dev/plan16/V16A/runpy.sh /home/ksysh/r3a-dev/plan16/S19/HP/s19hp_measure.py b3p2,hp8_150c1,hp8_135c1,hp8_150c0,p1,v15,b3p2_19 > measure.log 2>&1 &
sleep 2
echo launched
