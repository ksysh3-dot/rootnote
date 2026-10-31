#!/bin/bash
set -e
A=~/r3a-dev/plan16/A5P
N=~/r3a-dev/plan16/S19/NF
cd $N
for f in a5pcommon.py p_primary.py a5_ptable.py a5_song14.py burst_p.py rerise_p.py logoff45_p.py fosc_p.py right_p.py run_suite_p.sh; do cp $A/$f $N/$f; done
sed -i "s#/home/ksysh/r3a-dev/plan16/S19/NF#/home/ksysh/r3a-dev/plan16/S19/NF#g" *.py *.sh
sed -i "s#^V=~/r3a-dev/plan16/A5P#V=~/r3a-dev/plan16/S19/NF#" run_suite_p.sh
# a5pcommon: A5_DIR
sed -i "s#^A5_DIR = .*#A5_DIR = HOME / 'r3a-dev/plan16/S19/NF'#" a5pcommon.py
# row lists
sed -i "s#for k in \['v15'\] + AR.GRID:#for k in AR.REFN + AR.NEW:#" burst_p.py
sed -i "s#^ROWS = \['p1', 'v15'\] + AR.GRID#ROWS = ['p1'] + AR.REFN + AR.NEW#" rerise_p.py
sed -i "s#for name in \['v15'\] + AR.GRID:#for name in AR.REFN + AR.NEW:#" logoff45_p.py
sed -i "s#labels = sys.argv\[1:\] or \['v15'\] + AR.GRID#labels = sys.argv[1:] or AR.REFN + AR.NEW#" fosc_p.py
# suite script: 5th field nFuture
sed -i 's#IFS=: read lab b0 b1 ps <<< "\$spec"#IFS=: read lab b0 b1 ps nf <<< "$spec"#' run_suite_p.sh
sed -i 's#psiSlew=\$ps --label#psiSlew=$ps,nFuture=$nf --label#' run_suite_p.sh
sed -i 's#^\# A5.*#\# S19-NF suite rows. usage: run_suite_p.sh LABEL:betaMin:betaMax:psiSlew:nFuture ...#' run_suite_p.sh
mkdir -p cache14 cache suite
cp $A/cache14/*_b0p0_lo.npy $A/cache14/*_b3p2_lo.npy cache14/
grep -n "NF\|A5P" *.py *.sh | grep -v '^_' | head -40
cat run_suite_p.sh
