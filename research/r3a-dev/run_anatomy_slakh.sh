#!/bin/bash
cd ~/r3a-freeze-v1/tools/pvb-harness
export PYTHONPATH=.
~/venv-rootnote/bin/python ~/r3a-dev/band_anatomy.py ~/datasets/slakh2100/train build/libpvbcapi.so --reference midi --midi-transpose auto --crop 30,60 \
  --skip 'Track000[01][0-9]|Track00020' --limit 60 --out ~/r3a-dev/anat_slakh.json > ~/r3a-dev/anat_slakh.log 2>&1
tail -n 2 ~/r3a-dev/anat_slakh.log
