#!/usr/bin/env bash
# Start the live bot in the background with a restart loop. Needs HL_ACCOUNT and HL_API_KEY in the environment
# (or in ./.env, chmod 600, lines like: export HL_ACCOUNT=0x...). Stops restarting on exit code 3 (no creds/config), 4 (KILL) or 5 (lock held by another instance).
cd "$(dirname "$0")"
[ -f .env ] && . ./.env
if [ -z "$HL_ACCOUNT" ] || [ -z "$HL_API_KEY" ]; then echo "HL_ACCOUNT / HL_API_KEY not set - not starting."; exit 1; fi
if [ -f bot.pid ] && kill -0 "$(cat bot.pid)" 2>/dev/null; then echo "already running (pid $(cat bot.pid))"; exit 0; fi
rm -f KILL
nohup bash -c '
  while true; do
    .venv/bin/python bot.py; code=$?
    if [ $code -eq 5 ]; then echo "$(date -u +%FT%TZ) bot exited (5): another instance holds bot.lock - this loop ends (no restart)"; break; fi
    if [ $code -eq 3 ] || [ $code -eq 4 ] || [ -f STOP_LOOP ]; then echo "bot exited ($code), loop ends"; break; fi
    echo "bot exited ($code), restarting in 30s"; sleep 30
  done
' >> runner.log 2>&1 &
echo $! > bot.pid; echo "started, loop pid $(cat bot.pid). Logs: bot.log runner.log fills.jsonl status.json"
