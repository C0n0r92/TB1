#!/usr/bin/env bash
# Full halt, PAPER and LIVE.
#   ./stop.sh            -> disable LIVE (LIVE -> LIVE.off), SELL ALL open live positions, then stop the bot
#   ./stop.sh --no-sell  -> disable LIVE and stop immediately, leaving any live tokens in the wallet (unmanaged!)
cd "$(dirname "$0")"
[ -f LIVE ] && mv -f LIVE LIVE.off          # no new live buys even if something restarts the loop
if [ "$1" = "--no-sell" ]; then echo nosell > STOP; WAIT=20; else echo flatten > STOP; WAIT=240; fi
for i in $(seq 1 $WAIT); do pgrep -f "selfcopy.py run" >/dev/null || break; sleep 1; done
pkill -f "selfcopy.py run" 2>/dev/null; [ -f loop.pid ] && kill "$(cat loop.pid)" 2>/dev/null; rm -f loop.pid
pkill -f "run_loop.sh" 2>/dev/null
python3 - <<'P'
import json
s = json.load(open("state.json")).get("live", {})
o = [p["mint"] for p in s.get("positions", []) if p["status"] == "open"]
print("stopped. LIVE disabled. open live positions:", o or "none")
P
