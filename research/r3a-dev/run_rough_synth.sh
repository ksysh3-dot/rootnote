#!/bin/bash
cd ~/rootnote/tools/pvb-harness
export PYTHONPATH=.:study; PY=~/venv-rootnote/bin/python; L=~/r3a-freeze-v1/tools/pvb-harness/build/libpvbcapi.so
$PY ~/r3a-dev/make_synth.py ~/r3a-dev/synth
for f in 45 55 100 125; do
  echo "== bass$f"
  $PY ~/r3a-dev/roughness.py ~/r3a-dev/synth/bass$f.wav $L --phone-hz -1 \
    --pairs 'default+6:vb_on=1,vb_algo=6,vb_level_db=6;flat+6:vb_on=1,vb_algo=6,vb_level_db=6,dev_on=1,d_rolloff_db_oct=-24' 2>&1 \
    | grep -v '^off' | sed -E 's/"total_hits".*"change_pct"/"change_pct"/'
done
