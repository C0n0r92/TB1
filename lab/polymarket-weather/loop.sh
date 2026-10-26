#!/bin/bash
# Background loop: one cycle every ~30 min. Stop with: kill $(cat /workspace/lab/polymarket-weather/loop.pid)
cd /workspace/lab/polymarket-weather
while true; do ./run_cycle.sh >> logs/cycle.log 2>&1; sleep 1800; done
