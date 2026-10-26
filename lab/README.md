# Lab: paper-trading / backtest harness (PAPER ONLY)
Never trades, never touches wallets/keys. Reads other bots' folders read-only and writes only inside /workspace/lab.

## Rerun everything
    /workspace/lab/run_pipeline.sh            # fetch (<=~9 req/min, cached) -> backtest -> leaderboard.csv -> reports/lab-<date>.md
    /workspace/lab/run_pipeline.sh --no-network   # cache only
Scheduling: cron `*/15 * * * * /workspace/lab/run_pipeline.sh`, or a nohup loop (see header of run_pipeline.sh). flock prevents overlap; log goes to out/pipeline.log.

## Files
- config.toml: all assumptions (costs, sim, fetch limits, variant defaults) plus the `[[variant]]` list
- labcore.py: config loading, time, HTTP with per-host spacing, caches, point-in-time intel
- sources.py: radar scanned.jsonl, Chunk live/trades-log.md buys, copyfomo skips-log.csv / trades
- fetch.py: GeckoTerminal 5m candles, DexScreener liquidity polls, rugcheck snapshots (only <=15 min after a scan, so they count as point-in-time) -> data/
- backtest.py [--only NAME]: simulation + stats -> leaderboard.csv, out/trades.csv, out/summary.{json,txt}
- report.py [YYYY-MM-DD]: daily markdown in reports/

## Assumptions (config.toml)
- Fee 2% per side, $0.05 fixed per transaction. Slippage = 0.5% + 2×bet/liquidity, capped at 50%. Between polls, liquidity is modelled as liq0·sqrt(price/price0).
- The stop is checked before TP in the same candle. A stop gapped through fills at the candle close (or the open, if the candle opened lower).
- Rug = drawdown ≥80% from entry, or polled liquidity down ≥80%. Recovery is capped at 10% of the stake.
- Max 3 open positions per variant. When signals tie on time, the higher score wins. Positions are flat by 08:00 Dublin, with a 24h horizon.
- Point-in-time only: entries use the first candle after signal plus delay. Intel files are valid from their mtime. Holder and LP data count only if captured ≤15 min after the signal.
- Out of sample: signals after the 60th percentile of signal times, or after `holdout_start` if set. "yes" needs ≥20 OOS trades and an OOS mean-return 95% CI above 0. Bootstrap: 5000 iterations, seed 7.

## Adding a variant
Append to config.toml; any key in [defaults] can be overridden:

    [[variant]]
    name = "X_delay30_liq40k"
    entry_delay_min = 30      # survival window
    survive_max_dd = 0.3      # skip if price fell >30% during the window
    survive_max_up = 0.2      # skip if price is already up >20%
    min_liq = 40000
    stop = 0.2
    trail = 0.25              # trailing stop (0 = off)
    max_hold_h = 2
    pulse = "require_rising"  # off | filter | require_rising
    scout = "filter"          # off | filter (avoid-list reject, smart-wallet boost)
    min_lp_locked = 0.9

source = radar | chunk_live | copyfomo_skips | copyfomo_trades

## Added 2026-10-23 (Zero: guarded radar + METHOD)
- `METHOD.md` rules (scoring /25, candidate rule, sweeps/lucky_number, MC drawdown, WHY THIS COULD FAIL, weekly review). `backlog.md` status of every item.
- `guards.py`: rugguard reject classification + replay of /workspace/runner-radar/rugguard.py on pre-guard rows; Scout verdict lookup (point-in-time window [-2h, +15min]).
- `relabel.py`: 24h final labels (data/labels.csv, data/ds_24h.json) + guard evaluation `out/guard_eval.md`. Runs inside the pipeline.
- `scoring.py`: scores, 1,000-run MC drawdown, nights, lucky flags, variants_tried (data/variants_tried.json).
- `copytrade.py`: weekly top-trader swap from onchain-intel/trader_trades.csv.
- fetch.py also captures Scout's creator verdict for fresh signals (data/scout/, <= 3 script runs per pipeline run) and keeps candle volume.
- Variants ending in `_LOOKAHEAD` use information captured after the signal: OPTIMISTIC, never candidates.
