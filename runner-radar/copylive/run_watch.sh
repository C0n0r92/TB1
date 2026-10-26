#!/bin/bash
# copylive supervisor: keeps watch.py running CONTINUOUSLY (24/7, user 21:25Z 24 Oct: "Yes, run it 24/7 with the same caps").
# watch.py itself is single-instance (flock watch.lock), so a second supervisor or a manual start cannot double-run it.
# No session-end exit any more: the supervisor never exits on its own; it restarts watch.py after any exit/crash.
# Backoff 10 s; if > 3 restarts in 60 s, back off 60 s (logged to watch.err).
cd "$(dirname "$0")"
if [ -f supervisor.pid ] && kill -0 "$(cat supervisor.pid)" 2>/dev/null; then echo "supervisor already running: $(cat supervisor.pid)"; exit 0; fi
echo $$ > supervisor.pid
restarts=()
while true; do
  python3 -u watch.py >> watch.out 2>> watch.err
  rc=$?
  nowts=$(date +%s); keep=(); for r in "${restarts[@]}"; do [ $((nowts - r)) -lt 60 ] && keep+=("$r"); done; restarts=("${keep[@]}" "$nowts")
  if [ "${#restarts[@]}" -gt 3 ]; then
    echo "$(date -u +%FT%TZ) watch.py exited rc=$rc; ${#restarts[@]} restarts in 60s, backing off 60s" >> watch.err; sleep 60
  else
    echo "$(date -u +%FT%TZ) watch.py exited rc=$rc; restarting in 10s" >> watch.err; sleep 10
  fi
done
