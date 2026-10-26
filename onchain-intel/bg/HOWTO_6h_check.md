# 6-hourly BG copy-list check (single pass, hard cap ~10 min). Read-only. Recommend only.
All RPC goes through `fetchlayer.py` (publicnode -> api.mainnet-beta -> leorpc FREE -> Helius only if HELIUS_CAP>0).
`/workspace/scout/pub.py` and `ftx.py` already delegate to it. Never add wallets or change Chunk settings.

```bash
cd /workspace/onchain-intel/bg
ACTIVE="dmuXAmcXJcdNuK264vsJQNBpVBPAx4JLujBzBMahJ6C AHXvezMkJhyrXodVeTtbq53p6AZ8PPsCarF8RDy5KeeT GM8C8B5Ybx5eUthFDAQhQnW4A4R3jEgnhwS81goQ1h7d"  # update from Chunk's current list
CANDS=""   # at most 3 pre-screened wallets (e.g. top of bg_search_v2_*.json near_passes / kolscan_daily); empty = re-score only
# 1) refresh 24h data (~4 min max total). Busy wallets are capped by the timeouts; ftx is incremental.
for W in $ACTIVE $CANDS; do timeout 60 python3 sigs24.py $W; PUBT=6 HCAP=0 HOURS=24 timeout 60 python3 ftx.py $W; done
# 2) score v2 (~1 min/wallet at MAXC=20; GeckoTerminal ~30 calls/min)
MAXC=20 timeout 330 python3 scorer_v2.py $ACTIVE $CANDS > /tmp/v2_6h.log
# 3) make sure nothing is left running
pkill -f "python3 ftx.py"; pkill -f "python3 sigs24.py"; pkill -f "python3 scorer_v2.py"
```
Read results from `an/<wallet>.v2.json` (`pass_`, `fails`, `score`, `median_pct`, `sum_ex_top2`, `top_trade_share`, `stop_hits`, `exits`).
Rule: active wallet fails -> it is a "replace" only if a candidate has `pass_: true`; one line per swap to Chunk ("replace X with Y").
List never grows. Nothing fails, or no passing candidate -> send nothing. If time runs out, report what you have.
Data sanity: if `last_tx_utc` of an active wallet is >6h old while it is known active, mark "data incomplete", don't fail it.
