#!/usr/bin/env bash
# Lab pipeline (PAPER ONLY): fetch (rate-limited, cached; Scout creator check point-in-time) -> 24h relabel + guard eval -> copyfomo leader tests -> copy candidates + stake test -> benji probation tracker
# -> backtest -> leaderboard -> daily report (weekly review on Sundays).
# Polymarket + SOL-trend tracks moved to the Oracle bot 2026-10-23: NOT run or merged here (files left in place).
# Usage: /workspace/lab/run_pipeline.sh [--no-network]
# Scheduled by: bash -c 'while true; do /workspace/lab/run_pipeline.sh >/dev/null 2>&1; sleep 900; done'
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p out
exec 9>out/.pipeline.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) already running, skip" >> out/pipeline.log; exit 0; }
{
  echo "=== $(date -u +%FT%TZ) pipeline start"
  python3 fetch.py "$@" || echo "fetch failed (continuing with cache)"
  python3 relabel.py "$@" || echo "relabel failed (continuing)"
  python3 copytests.py "$@" || echo "copytests failed (continuing)"
  python3 copy_candidates.py "$@" || echo "copy_candidates failed (continuing)"   # reruns only when trader_trades/leader-rank/copyfomo leaderboard*/x-watch-log/candles change
  python3 benji_probation.py || echo "benji_probation failed (continuing)"   # reads Copycat x-watch-log only
  python3 survivor_momentum.py || echo "survivor_momentum failed (continuing)"   # SM_* rows -> out/leaderboard_extra_SM.json (no network)
  python3 backtest.py && python3 report.py
  echo "=== $(date -u +%FT%TZ) done rc=$?"
} >> out/pipeline.log 2>&1
tail -n 3 out/pipeline.log
