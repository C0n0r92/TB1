#!/bin/bash
# refresh 24h tx for wallets then rerun step.sh + mtm.py. Helius free window (until 00:00Z), HCAP absolute counter. Read-only.
cd /workspace/onchain-intel/bg
for W in "$@"; do
  timeout 180 python3 sigs24.py $W
  PUBT=3 HCAP=${HCAP:-20000} HOURS=24 timeout 900 python3 ftx.py $W
  timeout 600 bash step.sh $W
  timeout 200 python3 mtm.py $W
  echo "REFRESHED $W $(date -u +%H:%M)"
done
echo RDONE
