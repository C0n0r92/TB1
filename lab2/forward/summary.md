# Forward paper test: maj_1h FVG retest, trend on, gate=trending (PAPER ONLY)
Updated 2026-10-24T16:05Z. Start 2026-10-24T00:55:32Z. Config sha256 `4fd60b74901ba41d…`. R=2.0, cost 0.3%/side.

- Closed trades: **0** so far.
- Open positions: 0 
- Skipped (position open / risk filter): 0 / 0
- Benchmarks: hold from the last 1h close at or before start to the close of 2026-10-24T16:00Z, one round trip of costs:
  - Hold SOL: -3.57%
  - Equal-weight majors (13): -5.09%
  - Strategy, equal capital split across the 13 tokens (sum of returns / 13): +0.00%

Records: forward/fvg_trend.jsonl (signal + outcome, append-only, de-duplicated by id). Log: forward/cron.log.
Backtest reference: test 2026-08-15..10-23 trending subset n=71, +1.63%/trade; train trending n=138, -0.51%/trade. The gate was not train-selected.
