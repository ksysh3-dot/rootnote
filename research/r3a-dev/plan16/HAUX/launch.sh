#!/bin/bash
# usage: launch.sh SCRIPT.py LOG  -- run in background, detached
cd ~/r3a-dev/plan16/HAUX
setsid nohup bash ./runpy.sh "$1" > "$2" 2>&1 < /dev/null &
echo started
