#!/bin/bash
cd ~/r3a-dev/plan16/B1
rm -f win_.txt
while read a b; do bash runwin.sh $a $b; done < wins.txt
