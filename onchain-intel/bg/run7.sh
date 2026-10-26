#!/bin/bash
# 7d on-chain realized PnL via public RPC only (free): sigs2 (7d sig list) -> ftx7 (getTransaction) -> p7. Read-only.
cd /workspace/onchain-intel/bg
for W in "$@"; do
  [ -f an/$W.p7.json ] && continue
  timeout 300 python3 sigs2.py $W
  PUBT=3 HOURS=168 timeout 1500 python3 ftx7.py $W
  SRC="public RPC getSignaturesForAddress+getTransaction 168h (all own txs); realized closed rounds only" python3 p7.py $W
  timeout 120 python3 openpos.py $W | tail -1
  PARTIAL=1 python3 rank.py > /dev/null 2>&1 && echo "RANKED7 after $W $(date -u +%H:%M)"
done
echo R7DONE
