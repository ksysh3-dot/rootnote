#!/usr/bin/env bash
set -euo pipefail
cd /home/ksysh/r3a-dev/plan16/APP16/ref_wt/tools/pvb-harness
rm -rf ./C:Users*
./build_host.sh /home/ksysh/r3a-dev/plan16/APP16/ref_wt/tools/pvb-harness/build_app16c_ref | tail -1
cd /home/ksysh/r3-app/tools/pvb-harness
rm -rf ./C:Users*
./build_host.sh /home/ksysh/r3-app/tools/pvb-harness/build_app16c | tail -1
git -C /home/ksysh/r3-app status --short
