#!/bin/bash
# R4 v2 (corner skipped for harmonic-of-lower tracks) and an onset-protection sweep, phone-model roughness + bass band
cd ~/r3-work/tools/pvb-harness
export PYTHONPATH=.:study; PY=~/venv-rootnote/bin/python; L=build_r4b/libpvbcapi.so
V='vb_on=1,vb_algo=6,vb_level_db=6'
PAIRS="default+6:$V;r4c+6:$V,stage=16777216;p24f0+6:$V,stage=50331648,r4hold=24,r4floor=0,r4tau=60"
PAIRS="$PAIRS;p12f0+6:$V,stage=50331648,r4hold=12,r4floor=0,r4tau=40;p8f0+6:$V,stage=50331648,r4hold=8,r4floor=0,r4tau=30"
PAIRS="$PAIRS;p24f5+6:$V,stage=50331648,r4hold=24,r4floor=0.5,r4tau=60;p12f5+6:$V,stage=50331648,r4hold=12,r4floor=0.5,r4tau=40"
for f in 45 55 100 125; do
  echo "== bass$f"; $PY ~/r3a-dev/roughness.py ~/r3a-dev/synth/bass$f.wav $L --phone-hz -1 --pairs "$PAIRS" 2>&1 | grep -v -E '^(off|default|12dB|flat) '
done
echo "== LOGOFF 30-90 s"; $PY ~/r3a-dev/roughness.py ~/r3a-dev/songs/logoff.mp3 $L --start 30 --dur 60 --phone-hz -1 --pairs "$PAIRS" 2>&1 | grep -v -E '^(off|default|12dB|flat) '
