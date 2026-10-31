#!/bin/bash
bash ~/r3a-dev/run_r4_rough.sh > ~/r3a-dev/r4_rough.log 2>&1
~/venv-rootnote/bin/python ~/r3a-dev/sum_rough.py ~/r3a-dev/r4_rough.log
