#!/bin/bash
# R4 candidates vs P1 and the flat developer roll-off: phone-model roughness (noise proxy) and audible bass band
cd ~/r3-work/tools/pvb-harness
export PYTHONPATH=.:study; PY=~/venv-rootnote/bin/python; L=build/libpvbcapi.so
PAIRS='r4c:vb_on=1,vb_algo=6,stage=16777216;r4cp:vb_on=1,vb_algo=6,stage=50331648;default+6:vb_on=1,vb_algo=6,vb_level_db=6;flat+6:vb_on=1,vb_algo=6,vb_level_db=6,dev_on=1,d_rolloff_db_oct=-24;r4c+6:vb_on=1,vb_algo=6,vb_level_db=6,stage=16777216;r4cp+6:vb_on=1,vb_algo=6,vb_level_db=6,stage=50331648'
for f in 45 55 100 125; do
  echo "== bass$f"; $PY ~/r3a-dev/roughness.py ~/r3a-dev/synth/bass$f.wav $L --phone-hz -1 --pairs "$PAIRS" 2>&1 | grep -v '^off'
done
echo "== LOGOFF 30-90 s"; $PY ~/r3a-dev/roughness.py ~/r3a-dev/songs/logoff.mp3 $L --start 30 --dur 60 --phone-hz -1 --pairs "$PAIRS" 2>&1 | grep -v '^off'
