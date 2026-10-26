#!/bin/bash
# Usage: supervise.sh NAME INTERVAL_S CMD...   Runs CMD every INTERVAL_S seconds forever; restarts on crash; logs to logs/NAME.log
# Stop: kill $(cat /workspace/polymarket-lab/logs/NAME.pid)
NAME=$1; IV=$2; shift 2
cd /workspace/polymarket-lab || exit 1
echo $$ > logs/$NAME.pid
while true; do
  t0=$(date +%s)
  echo "$(date -u +%FT%TZ) [$NAME] start" >> logs/$NAME.log
  timeout $(( IV>600 ? IV*3 : 600 )) "$@" >> logs/$NAME.log 2>&1
  echo "$(date -u +%FT%TZ) [$NAME] exit=$?" >> logs/$NAME.log
  el=$(( $(date +%s) - t0 )); sl=$(( IV - el )); [ $sl -lt 5 ] && sl=5
  sleep $sl
done
