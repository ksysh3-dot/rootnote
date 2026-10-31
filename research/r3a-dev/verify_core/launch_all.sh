#!/bin/bash
chmod +x ~/r3a-dev/verify_core/run_suite.sh
cd ~/r3a-dev/verify_core
nohup ./run_suite.sh verify_A "voicing=0,ampSource=0" --v0 > /dev/null 2>&1 &
nohup ./run_suite.sh verify_B "voicing=0,ampSource=1" > /dev/null 2>&1 &
nohup ./run_suite.sh verify_C "voicing=1,levelDb=6,ampSource=0" > /dev/null 2>&1 &
nohup ./run_suite.sh verify_D "voicing=1,levelDb=9,ampSource=0" > /dev/null 2>&1 &
sleep 1
echo launched
