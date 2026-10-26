#!/bin/bash
# cron */2: (1) if live_enabled and no scalper loop alive -> start run.sh (bot.lock prevents doubles);
# (2) SIGTERM a hung scalper (heartbeat older than 300s while the box is awake); the run.sh loop restarts it.
cd /workspace/hlscalp
python3 -c "import json,sys;c=json.load(open('config.json'));sys.exit(0 if c.get('live_enabled') and c.get('base_capital_usd') else 1)" || exit 0
[ -f STOP_LOOP ] && exit 0
now=$(date +%s); last=$(cat .wd_last 2>/dev/null || echo 0); echo $now > .wd_last
if ! kill -0 "$(cat run.pid 2>/dev/null)" 2>/dev/null && ! pgrep -f "python scalper.py$" >/dev/null; then
  echo "$(date -u +%FT%TZ) no scalper loop - starting run.sh" >> watchdog.log; ./run.sh; exit 0; fi
[ $((now-last)) -gt 240 ] && exit 0   # box just woke from a pause; give the bot a cycle
pid=$(pgrep -f "python scalper.py$") || exit 0
hb=$(stat -c %Y .heartbeat 2>/dev/null || echo 0)
if [ $((now-hb)) -gt 300 ]; then echo "$(date -u +%FT%TZ) heartbeat stale $((now-hb))s, SIGTERM $pid" >> watchdog.log; kill -TERM $pid; fi
