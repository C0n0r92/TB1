#!/usr/bin/env bash
# Restart-safe loop. PAPER for all leaders; LIVE (_benjitrades only) when ./LIVE exists. Halts on ./STOP.
cd "$(dirname "$0")"
echo $$ > loop.pid
while [ ! -f STOP ]; do
  python3 -u selfcopy.py run >> run.log 2>&1
  rc=$?
  [ -f STOP ] && break
  echo "$(date -u +%FT%TZ) selfcopy exited ($rc), restarting in 10s" >> run.log
  sleep 10
done
echo "$(date -u +%FT%TZ) loop stopped (STOP file)" >> run.log
rm -f loop.pid
