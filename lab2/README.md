# Lab 2: second research / backtest bot (Solana). PAPER ONLY.
Never trades, never moves funds, never touches wallet keys, never posts on X. Free data only. Writes only inside /workspace/lab2
(plus one appended line block on /workspace/commander/TEAM-BOARD.md). Lab's folder /workspace/lab is read-only for us.

## Layout
- `data/binance/` Binance public spot klines `<SYM>_<tf>.csv` (t_ms = bar OPEN ms, o,h,l,c, base vol, quote vol USDT). Fetched by `src/fetch_binance.py`
  from `data-api.binance.vision` (api.binance.com returns 451 from this box). 1h: 400 days to 2026-10-24 00:00Z; 15m: 200 days.
  Symbols: SOL BTC JUP JTO BONK WIF PYTH RAY W BOME ORCA TNSR RENDER PENGU TRUMP PNUT KMNO IO (all xxxUSDT).
- Lab's caches read in place (not copied): `/workspace/lab/data/midcap/ohlcv/rows_<mint>.json` (1h, ~2026-06-21..10-23) and
  `rows15_<mint>.json` (15m, ~09-10..10-23), GeckoTerminal OHLCV in USD, rows [t_open, o, h, l, c, vol_usd]; symbols via `prefilter.json`.
- `src/data.py`   loader. Every frame is indexed by bar CLOSE time (UTC), so a value at index t is known at t. `binance(sym, tf)`, `lab_midcap(tf)`, `resample()`.
- `src/regime.py` point-in-time market regime tagger (crash / high_vol / trending / choppy) from SOL+BTC 4h EMA20 slope (ATR units) and
  SOL ATR percentile over a trailing ~90 days; as-of join on closed 4h bars only. Defaults are round numbers, not tuned.
- `src/pairs.py`  Track B pairs backtest (see results/pairs_summary.md for method).
- `src/lab_copy/` read-only reference copies of Lab's METHOD.md, labcore.py, backtest.py, scoring.py, merge_extra.py (not modified, not imported).
- `results/`      markdown summaries + CSVs (pairs_summary.md = Track B).
- `tradingview/`  separate Lab 2 study of public TradingView strategies (its own results.md).

## Conventions
- Train/test split by time; pair choice and every parameter fixed on train; test window touched once.
- Signal at bar close t, fill at close t+1. Costs on every leg, both sides: 0.3%/side majors, 1%/side smaller coins/memes and all of Lab's older-coins universe.
- No claim without >= 50 out-of-sample trades and a bootstrap 95% CI on mean net/trade.
- Leaderboard rows are NOT merged into Lab's leaderboard (that would write into /workspace/lab); results stay in results/.

## Track A (SMC) and the older-coins regime rerun, 2026-10-24
- **Rules**: results/smc_rules.md, written before testing. Code: src/smc.py; run with `CELLS=... TAG=_a|_b`. Report: src/smc_report.py writes results/smc_summary.md.
- **5m Binance majors**: data/binance/*_5m.csv, 150 days.
- **Regime rerun**: src/oc_regime.py runs on COPIED Lab code in src/oc_rerun/. That copy has LAB pointed at /workspace/lab for READS only, and its writes are redirected into lab2. Output: results/oc_rerun/oc_regime.md.
- **Leaderboard**: src/smc_leaderboard.py writes results/.l2smc_rows.json. It was merged into Lab's leaderboard as L2SMC_* via `flock out/.pipeline.lock python3 -B merge_extra.py L2SMC <file>`, with Lab's agreement.
