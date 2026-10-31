#!/usr/bin/env bash
source ~/venv-rootnote/bin/activate
cd /home/ksysh/r3a-dev/plan16/APP16
export OPENBLAS_NUM_THREADS=1
python v0_app16c.py > v0_app16c.log 2>&1; tail -2 v0_app16c.log; echo "PASS $(grep -c '^PASS' v0_app16c.log) FAIL $(grep -c '^FAIL' v0_app16c.log)"
grep -E 'HP really|E1sw|sanity' v0_app16c.log | head -20
python e2_rule_c.py 2>&1 | tail -14
bash jvm_app16c.sh 2>&1 | tail -8
python jni_1516c.py
