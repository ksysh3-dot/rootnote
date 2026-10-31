#!/bin/bash
# One script, end to end:   run_la0.sh [--dev] [--lag N] [--out NAME]
#   runs the analysis (stages A-C, cached) and then the report/decision (stage D) -> la0/NAME.json, NAME_report.md, NAME_decision.json
#   primary reading:        run_la0.sh --out results            (TRK_LAG 191: a tracker hop is usable at t iff c + 191 <= t + L)
#   sensitivity reading:    run_la0.sh --lag 0 --out results_lag0   (hop usable iff c <= t + L; labelled sensitivity, not used for the decision)
#   --dev: train songs + synthetic signals only (no evaluation song is touched)
# Input provenance: bh / band streams and the core-v1.5 trace come from the CANDIDATE lib capture (build_core, algo 15, config A); the tracker tracks of LA and the P1 row come from
# the P1 REFERENCE build's harmonic trace (build_ref core, algo 6); the two hop grids are identical (asserted).  Slakh TRAIN only.
OUT=results; DEV=""
args=("$@")
for ((i=0;i<${#args[@]};i++)); do
  [ "${args[$i]}" = "--out" ] && OUT="${args[$((i+1))]}"
  [ "${args[$i]}" = "--dev" ] && DEV="--dev"
done
cd ~/r3a-dev/diag16 && ./run.sh ../la0/run_la0.py "$@" && ~/venv-rootnote/bin/python ../la0/report.py /home/ksysh/r3a-dev/la0/$OUT.json $DEV > /home/ksysh/r3a-dev/la0/${OUT}_report.txt && tail -n 3 /home/ksysh/r3a-dev/la0/${OUT}_report.txt
