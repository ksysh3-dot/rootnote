#!/bin/bash
# chain 1: primary layer ratio in batches of 4 rows
V=~/r3a-dev/plan16/A5PP
cd $V
PY=~/r3a-dev/plan16/V16A/runpy.sh
$PY $V/pp_primary.py p1 v15 b0 bb > primary_1.log 2>&1
$PY $V/pp_primary.py sA30 sA60 sA100 sB30 > primary_2.log 2>&1
$PY $V/pp_primary.py sB60 sB100 > primary_3.log 2>&1
$PY $V/a5pp_table.py > primary_table.log 2>&1
echo PRIMARYDONE > $V/primary_done.txt