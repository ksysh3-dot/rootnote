#!/bin/bash
cd ~/r3a-freeze-v1/tools/pvb-harness
L=build/libpvbcapi.so; PY=~/venv-rootnote/bin/python; export PYTHONPATH=.
$PY ~/r3a-dev/band_anatomy.py ~/datasets/slakh2100/train $L --reference midi --midi-transpose auto --crop 30,60 \
  --skip 'Track000[01][0-9]|Track00020' --limit 60 --out ~/r3a-dev/anat_slakh.json > ~/r3a-dev/anat_slakh.log 2>&1
$PY ~/r3a-dev/band_anatomy.py ~/datasets/musdb7 $L --reference yin --out ~/r3a-dev/anat_musdb.json > ~/r3a-dev/anat_musdb.log 2>&1
tail -n 3 ~/r3a-dev/anat_slakh.log ~/r3a-dev/anat_musdb.log
