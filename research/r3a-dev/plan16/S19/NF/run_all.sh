#!/bin/bash
# S19-NF driver: phases run one after another (memory); logs in NF/logs
N=~/r3a-dev/plan16/S19/NF
RP=~/r3a-dev/plan16/V16A/runpy.sh
cd $N; mkdir -p logs
sed -i "s#R\['b0p0'\]#R['b3p2']#" a5_ptable.py
echo START $(date) > logs/progress.txt
./run_suite_p.sh nfa48:.2:.9:.12:48 nfa72:.2:.9:.12:72 nfa96:.2:.9:.12:96 nfb48:.05:.1:.03:48
echo SUITE1 $(date) >> logs/progress.txt
./run_suite_p.sh nfb96:.05:.1:.03:96 b3p2:.05:.1:.03:24
echo SUITE2 $(date) >> logs/progress.txt
$RP $N/p_primary.py nfa48 nfa72 nfa96 nfb48 nfb96 b3p2 > logs/primary.log 2>&1
$RP $N/a5_ptable.py > logs/ptable.log 2>&1
echo PRIMARY $(date) >> logs/progress.txt
$RP $N/songs12.py p1 b0p0 b3p2 nfa48 nfa72 nfa96 nfb48 nfb96 > logs/songs12.log 2>&1
echo SONGS12 $(date) >> logs/progress.txt
$RP $N/burst_p.py > logs/burst.log 2>&1 &
$RP $N/rerise_p.py > logs/rerise.log 2>&1 &
$RP $N/logoff45_p.py > logs/logoff45.log 2>&1 &
$RP $N/fosc_p.py > logs/fosc.log 2>&1 &
wait
echo MISC $(date) >> logs/progress.txt
for l in nfa48 nfa72 nfa96 nfb48 nfb96; do $RP $N/right_p.py $l > logs/right_$l.log 2>&1; done
echo RIGHT $(date) >> logs/progress.txt
$RP $N/a5_song14.py render b0p0 b3p2 nfa48 nfa72 nfa96 nfb48 nfb96 > logs/song14_render.log 2>&1
$RP $N/a5_song14.py table b0p0 b3p2 nfa48 nfa72 nfa96 nfb48 nfb96 > song14_table.txt 2> logs/song14_table.err
echo SONG14 $(date) >> logs/progress.txt
echo ALLDONE >> logs/progress.txt
