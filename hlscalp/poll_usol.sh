#!/bin/bash
for i in $(seq 1 60); do
  r=$(curl -s -m 10 -X POST https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' -d '{"type":"spotClearinghouseState","user":"0x8bf46912296ecE936D446f3448e383054100c482"}')
  u=$(echo "$r" | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(float(b['total']) for b in d['balances'] if b['coin'] in ('USOL','SOL')))" 2>/dev/null)
  echo "$(date -u +%T) USOL=$u"
  python3 -c "import sys;sys.exit(0 if float('${u:-0}')>=0.80 else 1)" && { echo FULL; exit 0; }
  sleep 30
done; echo TIMEOUT
