#!/usr/bin/env bash
#   ./start.sh         -> start; LIVE only if the file ./LIVE exists
#   ./start.sh --live  -> create ./LIVE and start with live trading for _benjitrades
cd "$(dirname "$0")"
if [ -f loop.pid ] && kill -0 "$(cat loop.pid)" 2>/dev/null; then echo "already running (loop pid $(cat loop.pid))"; exit 0; fi
[ "$1" = "--live" ] && { rm -f LIVE.off; touch LIVE; }
rm -f STOP
nohup ./run_loop.sh > /dev/null 2>&1 &
sleep 1; echo "started loop pid $(cat loop.pid); LIVE=$([ -f LIVE ] && echo ON || echo OFF)"
