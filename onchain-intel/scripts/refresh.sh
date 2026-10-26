#!/bin/sh
# Scout daily refresh (18:00, read-only). Helius used automatically if /home/box/.scout-secrets/helius.env exists (key never printed).
# Budget-trimmed 2026-10-24: target <= ~10k Helius credits per run (was ~30k on 2026-10-23, mostly one-off backfills).
#  - one shared budget file for every step (sol.py budget_take): RPC 1/call, enhanced 100/page, gtfa 10/call
#  - SCOUT_PUBLIC_FIRST=1: public RPC first, Helius only as last resort (sol.py)
#  - early_buyers: mint-history paging capped (EARLY_MINT_PAGES=60, was 400; bonding curve 40, was 60); over-cap mints are
#    deferred to data/early_deferred.txt instead of caching a wrong early-buyer list; existing data/early/*.json reused
#  - trader_trades: TT_MAXPAGES=3 (was 20) incremental pages per trader (stops at newest cached tx anyway)
#  - rugcheck_creator for radar mints: only mints added in the last 2 days (was every radar mint every run)
#  - weekly leader re-rank: LR_MAXPAGES=4 (was 10), watch-list backfill LR_WATCH_MAXPAGES=8 (was 25); resumes next week
#  Per-step spend is logged to data/refresh_budget.log.
set -e
cd /workspace/onchain-intel
export SCOUT_HELIUS_BUDGET_FILE=/workspace/onchain-intel/data/refresh_budget.json
export SCOUT_PUBLIC_FIRST=1 EARLY_MINT_PAGES=${EARLY_MINT_PAGES:-60} EARLY_BC_PAGES=${EARLY_BC_PAGES:-40} TT_MAXPAGES=${TT_MAXPAGES:-3}
export LR_MAXPAGES=${LR_MAXPAGES:-4} LR_WATCH_MAXPAGES=${LR_WATCH_MAXPAGES:-8}
echo "{\"limit\": ${REFRESH_HELIUS_LIMIT:-10000}, \"used\": 0, \"denied\": 0, \"started\": \"$(date -u +%FT%TZ)\"}" > "$SCOUT_HELIUS_BUDGET_FILE"
BLOG=data/refresh_budget.log
used() { python3 -c "import json;b=json.load(open('$SCOUT_HELIUS_BUDGET_FILE'));print(b.get('used',0), b.get('denied',0))"; }
step() { name=$1; shift; b0=$(used); "$@" || true; b1=$(used); echo "$(date -u +%FT%TZ) $name used/denied before=[$b0] after=[$b1]" >> $BLOG; }
echo "$(date -u +%FT%TZ) refresh start limit=${REFRESH_HELIUS_LIMIT:-10000}" >> $BLOG
step add_radar_mints python3 scripts/add_radar_mints.py
step early_buyers sh -c "cd scripts && python3 early_buyers.py \$(cut -d' ' -f1 ../data/tokens.txt) > ../data/early_refresh.log 2>&1"
step analyze sh -c "python3 scripts/analyze.py > data/analyze.log 2>&1"
step build_outputs python3 scripts/build_outputs.py
step build_known_ruggers python3 scripts/build_known_ruggers.py
step custodial_ignore python3 scripts/apply_custodial_ignore.py                # strip labelled exchange funders
# rugcheck_creator only for radar mints first seen in the last 2 days (its 600 s cache made re-checks of old mints pure cost)
step rugcheck_creator sh -c 'for m in $(python3 scripts/recent_radar_mints.py 2); do python3 rugcheck_creator.py "$m" > /dev/null || true; done'
step tag_signals python3 scripts/tag_signals.py                                   # -> signal_verdicts.jsonl (new radar signals only)
step operator_watch sh -c "python3 scripts/operator_watch.py --forward > data/opfwd.log 2>&1"
step merge_operator python3 scripts/merge_operator.py                             # -> avoid.csv / known_ruggers.json / known_funders.csv
step custodial_ignore2 python3 scripts/apply_custodial_ignore.py
step early_buyer_miner sh -c "python3 scripts/early_buyer_miner.py > data/miner.log 2>&1"
step trader_trades sh -c "python3 scripts/trader_trades.py > data/tt.log 2>&1"
# weekly (Sunday UTC): copyfomo leader re-rank (enhanced API 100 credits/page; mostly cached)
if [ "$(date -u +%u)" = "7" ] || [ "${FORCE_LEADER_RANK:-0}" = "1" ]; then step leader_rank sh -c "python3 scripts/leader_rank.py > data/leader_rank.log 2>&1"; fi
echo "$(date -u +%FT%TZ) refresh done $(cat $SCOUT_HELIUS_BUDGET_FILE)" >> $BLOG
echo "refreshed $(date -u +%FT%TZ); Helius budget $(cat $SCOUT_HELIUS_BUDGET_FILE). Now update NOTES.md top line + reports/scout-<date>.md"
