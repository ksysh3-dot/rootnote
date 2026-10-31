#!/bin/bash
V=~/r3a-dev/plan16/A5P
cd $V
# batches of 4 (memory: 11 parallel suite jobs were OOM-killed in A5)
./run_suite_p.sh b0p0:.2:.9:.12 b0p1:.2:.9:.06 b0p2:.2:.9:.03 b1p0:.1:.45:.12
./run_suite_p.sh b1p1:.1:.45:.06 b1p2:.1:.45:.03 b2p0:.1:.2:.12 b2p1:.1:.2:.06
./run_suite_p.sh b2p2:.1:.2:.03 b3p0:.05:.1:.12 b3p1:.05:.1:.06 b3p2:.05:.1:.03
echo SUITEALL >> $V/suite/done.txt
