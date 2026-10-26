#!/usr/bin/env bash
# Stop the bot. Default: stop the process, leave positions open WITH their exchange stop/TP orders.
# ./stop.sh --flatten : create KILL so the bot closes all positions/orders itself, then exits.
cd "$(dirname "$0")"
if [ "$1" = "--flatten" ]; then touch KILL; echo "KILL created: bot will close everything and exit within ~1s"; sleep 15; fi
touch STOP_LOOP
if [ -f bot.pid ]; then pkill -TERM -P "$(cat bot.pid)" 2>/dev/null; kill "$(cat bot.pid)" 2>/dev/null; rm -f bot.pid; fi
pkill -TERM -f "python bot.py$" 2>/dev/null
rm -f STOP_LOOP; echo "stopped"
