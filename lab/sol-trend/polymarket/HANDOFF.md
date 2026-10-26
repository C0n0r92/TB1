# HANDOFF to Oracle (Polymarket owner) - from Lab, 2026-10-23 ~22:30 UTC
Lab started a Polymarket SOL Up-or-Down check, then the scope moved to Oracle. Nothing was analysed. Read-only, public endpoints only; no account, no orders.

What exists here
- fetch_pm.py - Gamma closed events for series `sol-up-or-down-5m` (last 7 d) + data-api taker tape for every 3rd market; `books` mode snapshots CLOB books
  of the next 4 windows. Cache in ./cache (sha1 of URL). It was stopped mid-run (~550 of 2,015 markets), so data/markets.json was NOT written; the cached
  responses in ./cache are reusable (rerun = mostly cache hits). Uses /workspace/lab/polymarket-weather/pmw_common.py (http + 1 s spacing).
- data/book_snapshots.jsonl - 4 CLOB book snapshots (22:2x UTC).

Facts seen (Gamma, 2026-10-23)
- Series slugs: `sol-up-or-down-5m` (event slug sol-updown-5m-<unix start>), `sol-up-or-down-15m` (sol-updown-15m-<unix start>),
  `solana-up-or-down-hourly`. (`?closed=false&order=endDate&ascending=true` returns stale Dec-2025 leftovers; query by slug with the current unix start.)
- Resolution (5m and 15m): "Up" if the Chainlink SOL/USD **TWAP** over the window >= the price at the start of the window
  (data.chain.link/streams/sol-usd-twap-60s-streams). Hourly uses the Binance SOL/USDT 1h candle close vs open. Not plain close-vs-open for 5m/15m.
- Fees: feeSchedule {rate 0.07, exponent 1, takerOnly, rebateRate 0.2} -> taker fee = 0.07*p*(1-p) per share (~1.75c at p=0.5).
- Pre-window books at ~0.49/0.51 (1-2c spread), liquidityNum ~$2.3-4.2k per 5m window; a live 15m window mid-way was 0.26/0.27.
- Binance public klines: api.binance.com = HTTP 451 from this box; data-api.binance.vision works (1m..4h). Lab saved SOLUSDT 5m/15m/1h/4h (2 y) in ../data/.
