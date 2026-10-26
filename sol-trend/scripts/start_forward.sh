#!/usr/bin/env bash
# Start (idempotent) the supervisor in the background.  Stop: kill $(cat logs/supervisor.pid) $(cat logs/forward.pid)
cd /workspace/sol-trend
if [ -f logs/supervisor.pid ] && kill -0 "$(cat logs/supervisor.pid)" 2>/dev/null; then echo "already running: supervisor $(cat logs/supervisor.pid)"; exit 0; fi
nohup setsid scripts/supervisor.sh > /dev/null 2>&1 < /dev/null &
sleep 1; echo "supervisor $(cat logs/supervisor.pid)"
