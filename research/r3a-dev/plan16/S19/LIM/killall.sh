#!/bin/bash
for p in $(ps -eo pid,cmd | grep -E 'launch.sh|xargs -P|lim_worker' | grep -v grep | grep -v killall | awk '{print $1}'); do kill -9 $p; done
sleep 2
ps -eo pid,cmd | grep -E 'launch|lim_worker' | grep -v grep | wc -l
