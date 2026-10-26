#!/bin/bash
# One logging + paper cycle (read-only public APIs, paper only). Safe to run every 30-60 min.
cd /workspace/polymarket-lab/weather || exit 1
exec 9>/tmp/oracle_pmw_cycle.lock; flock -n 9 || { echo "$(date -u +%FT%TZ) previous cycle still running"; exit 0; }
timeout 1500 python3 logger.py && python3 paper.py && python3 score_weather.py > /dev/null
echo "$(date -u +%FT%TZ) cycle exit=$?"
