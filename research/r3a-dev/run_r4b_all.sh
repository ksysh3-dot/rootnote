#!/bin/bash
cd ~/r3-work && bash tools/pvb-harness/build_host.sh ~/r3-work/tools/pvb-harness/build_r4b 2>&1 | tail -1
bash ~/r3a-dev/run_r4b_rough.sh > ~/r3a-dev/r4b_rough.log 2>&1
~/venv-rootnote/bin/python ~/r3a-dev/sum_rough.py ~/r3a-dev/r4b_rough.log
