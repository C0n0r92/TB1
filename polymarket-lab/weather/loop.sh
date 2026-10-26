#!/bin/bash
# Background loop: one cycle every ~30 min. Stop with: kill $(cat /workspace/polymarket-lab/weather/loop.pid)
cd /workspace/polymarket-lab/weather
while true; do ./run_cycle.sh >> logs/cycle.log 2>&1; sleep 1800; done
