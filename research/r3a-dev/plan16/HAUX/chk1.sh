#!/bin/bash
cd ~/r3a-dev/plan16
for f in D/cache/*.npz; do b=$(basename $f); [ -e K/cache/$b ] || echo MISSING $b; done
ls D/cache | head -40
sed -n 1,40p D/dsig.py
