#!/bin/bash
cd ~/r3-work/tools/pvb-harness
export PYTHONPATH=.:study; PY=~/venv-rootnote/bin/python; L=build_r4b/libpvbcapi.so
$PY ~/r3a-dev/coherent_gain.py ~/datasets/musdb7 $L --reference yin --out ~/r3a-dev/coh_musdb.json > ~/r3a-dev/coh_musdb.log 2>&1
$PY ~/r3a-dev/coherent_gain.py ~/datasets/slakh2100/train $L --reference midi --midi-transpose auto --crop 30,60 \
  --skip 'Track000[01][0-9]|Track00020' --limit 20 --out ~/r3a-dev/coh_slakh.json > ~/r3a-dev/coh_slakh.log 2>&1
grep -v ITEM ~/r3a-dev/coh_musdb.log; echo; grep -v ITEM ~/r3a-dev/coh_slakh.log
