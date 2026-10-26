#!/usr/bin/env bash
# Restart-on-death supervisor for the PAPER forward test. PID files + logs in /workspace/sol-trend/logs/.
cd /workspace/sol-trend || exit 1
echo $$ > logs/supervisor.pid
while true; do
  echo "$(date -u +%FT%TZ) supervisor: starting forward.py" >> logs/supervisor.log
  .venv/bin/python scripts/forward.py >> logs/forward.log 2>&1; rc=$?
  echo "$(date -u +%FT%TZ) supervisor: forward.py exited code $rc - restarting in 30s" >> logs/supervisor.log
  sleep 30
done
