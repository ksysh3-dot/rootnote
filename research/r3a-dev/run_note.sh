#!/bin/bash
cd ~/r3a-freeze-v1/tools/pvb-harness
L=build/libpvbcapi.so; PY=~/venv-rootnote/bin/python
PYTHONPATH=. $PY ~/r3a-dev/note_level.py ~/datasets/babyslakh $L --reference midi --midi-transpose -12 --out ~/r3a-dev/note_baby.json > ~/r3a-dev/note_baby.log 2>&1
PYTHONPATH=. $PY ~/r3a-dev/note_level.py ~/datasets/musdb7 $L --reference yin --out ~/r3a-dev/note_musdb.json > ~/r3a-dev/note_musdb.log 2>&1
tail -n 40 ~/r3a-dev/note_baby.log; tail -n 40 ~/r3a-dev/note_musdb.log
