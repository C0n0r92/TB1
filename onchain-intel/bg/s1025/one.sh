#!/bin/bash
cd /workspace/onchain-intel/bg; W=$1
timeout 100 python3 sigs24.py $W >/dev/null 2>&1
PUBT=3 HCAP=11193 HOURS=24 timeout 200 python3 ftx.py $W >/dev/null 2>&1
timeout 200 bash step.sh $W > s1025/step_$W.log 2>&1
timeout 90 python3 mtm.py $W > s1025/mtm_$W.log 2>&1
echo "DONE $W $(date -u +%T)"
