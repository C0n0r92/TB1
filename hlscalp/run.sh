#!/bin/bash
# LIVE scalper launcher (same account + trade-only API key as perpbot). Exit 3/4/5 or STOP_LOOP file end the loop.
cd /workspace/hlscalp
set -a; . /workspace/perpbot/.env; set +a
nohup bash -c '
  while true; do
    /workspace/perpbot/.venv/bin/python scalper.py; code=$?
    if [ $code -eq 3 ] || [ $code -eq 4 ] || [ $code -eq 5 ] || [ -f STOP_LOOP ]; then echo "$(date -u +%FT%TZ) scalper exited ($code), loop ends"; break; fi
    echo "$(date -u +%FT%TZ) scalper exited ($code), restarting in 30s"; sleep 30
  done' >> run.out 2>&1 &
echo $! > run.pid
