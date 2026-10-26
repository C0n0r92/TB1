#!/bin/bash
# Free box-cron watchdog (backstop only since 2026-10-25: all HL HTTP calls now have 5s/10s timeouts + retries, so a hang should not happen). If the live bot stops writing status.json for 5+ min while the computer is awake (a real hang), SIGTERM it; run.sh restarts it.
# The computer pauses when idle, so after a wake everything looks stale. If this script's own last run was >4 min ago, it only notes the time and waits for the next run, so the bot can catch up on its own.
cd /workspace/perpbot || exit 0
[ -f STOP_LOOP ] && exit 0
nowt=$(date +%s); last=$(cat .watchdog_last 2>/dev/null || echo 0); echo "$nowt" > .watchdog_last
[ $((nowt - last)) -gt 240 ] && exit 0
pid=$(pgrep -f "^.venv/bin/python bot.py$" | head -1); [ -z "$pid" ] && exit 0
# newest of status.json (written every loop) and .heartbeat (touched by every successful HL request, so long entry waits count as alive)
hb=$(stat -c %Y .heartbeat 2>/dev/null || echo 0); stt=$(stat -c %Y status.json 2>/dev/null || echo 0); [ "$hb" -gt "$stt" ] && stt=$hb
age=$(( nowt - stt ))
if [ "$age" -gt 300 ]; then echo "$(date -u +%FT%TZ) watchdog: status.json ${age}s old while awake, SIGTERM pid $pid" >> watchdog.log; kill -TERM "$pid"; sleep 20; kill -0 "$pid" 2>/dev/null && kill -KILL "$pid"; fi
