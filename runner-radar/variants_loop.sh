#!/usr/bin/env bash
# One-off companion for a run_loop.sh that was started BEFORE variants.py existed (23 Oct 2026).
# Snapshots intel every 5 min, full variant grading every 30 min, until UNTIL (epoch). Paper only.
cd "$(dirname "$0")"
UNTIL=${1:?epoch}; i=0
while [ "$(date +%s)" -lt "$UNTIL" ]; do
  python3 variants.py --snapshot-only >> variants.log 2>&1
  [ $((i % 6)) -eq 0 ] && python3 variants.py > /dev/null 2>> variants.log
  i=$((i+1)); sleep 300
done
python3 variants.py > /dev/null 2>> variants.log
