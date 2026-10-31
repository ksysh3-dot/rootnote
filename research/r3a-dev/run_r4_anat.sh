#!/bin/bash
# R4 v2 on the development sets: layer harmonic profile / layer-to-native per f0 band (Slakh train 30, MUSDB 144)
cd ~/r3-work/tools/pvb-harness
export PYTHONPATH=.; PY=~/venv-rootnote/bin/python; L=build_r4b/libpvbcapi.so
run() {  # name stage r4
  $PY ~/r3a-dev/band_anatomy.py ~/datasets/slakh2100/train $L --reference midi --midi-transpose auto --crop 30,60 \
    --skip 'Track000[01][0-9]|Track00020' --limit 30 --stage $2 ${3:+--r4 $3} --out ~/r3a-dev/anat2_slakh_$1.json > ~/r3a-dev/anat2_slakh_$1.log 2>&1
  $PY ~/r3a-dev/band_anatomy.py ~/datasets/musdb7 $L --reference yin --stage $2 ${3:+--r4 $3} --out ~/r3a-dev/anat2_musdb_$1.json > ~/r3a-dev/anat2_musdb_$1.log 2>&1
}
run p1 0 ''; run r4c 16777216 ''; run p8 50331648 8,0,30
for s in slakh musdb; do for v in p1 r4c p8; do echo "#### $s $v"; $PY ~/r3a-dev/anat_table.py ~/r3a-dev/anat2_${s}_$v.json | grep -E 'frames|layer share'; done; done
