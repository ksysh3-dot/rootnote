#!/bin/bash
cd ~/r3-work/tools/pvb-harness
export PYTHONPATH=.:study; PY=~/venv-rootnote/bin/python; L=build_r4b/libpvbcapi.so
V='vb_on=1,vb_algo=6'
PAIRS="r4c:$V,stage=16777216;p8:$V,stage=50331648,r4hold=8,r4floor=0,r4tau=30;default+6:$V,vb_level_db=6;r4c+6:$V,vb_level_db=6,stage=16777216;p8+6:$V,vb_level_db=6,stage=50331648,r4hold=8,r4floor=0,r4tau=30"
for t in Track00040 Track00060 Track00031; do
  echo "== $t 30-60 s"; $PY ~/r3a-dev/roughness.py ~/datasets/slakh2100/train/$t/mix.flac $L --start 30 --dur 30 --phone-hz -1 --pairs "$PAIRS" 2>&1 | grep -v -E '^(off|12dB|flat) '
done > ~/r3a-dev/rough_real.log
~/venv-rootnote/bin/python ~/r3a-dev/sum_rough.py ~/r3a-dev/rough_real.log
