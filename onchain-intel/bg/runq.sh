#!/bin/bash
# queue runner: per wallet add->sigs24->ftx(public)->step.sh->rank (atomic). Skips wallets already analysed. Read-only.
cd /workspace/onchain-intel/bg
for W in $(cat "$1"); do
  [ -f an/$W.json ] && [ -f an/$W.fsim.json ] && continue
  python3 addcand.py $W
  timeout 120 python3 sigs24.py $W
  n=$(python3 -c "import json;print(len(json.load(open('sig/$W.json'))['sigs']))")
  if [ "$n" -gt 1500 ]; then echo "$W skip busy $n"; echo "$W" >> busy_skip.txt; continue; fi
  PUBT=3 HOURS=24 timeout 900 python3 ftx.py $W
  timeout 600 bash step.sh $W
  [ -f an/$W.json ] || echo "{\"name\":\"GT2-${W:0:6}\",\"wallet\":\"$W\",\"finding\":\"no own swaps parsed in 24h txs\"}" >> noswap_new.jsonl
  PARTIAL=1 python3 rank.py > /dev/null 2>&1 && echo "RANKED after $W $(date -u +%H:%M)"
done
echo QDONE
