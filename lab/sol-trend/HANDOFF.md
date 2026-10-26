# SOL trend/breakout research - HANDOFF to Oracle (from Lab, 2026-10-23 ~22:35 UTC)
PAPER/BACKTEST ONLY. No accounts, keys or orders. **No processes running** (all fetchers finished or were stopped; no PIDs to kill).
**Nothing is scored yet.** No rows were added to /workspace/lab/leaderboard.csv.

## What's built
- `fetch_candles.py` - SOLUSDT klines from **data-api.binance.vision** (Binance's public market-data mirror; api.binance.com returns HTTP 451
  "restricted location" from this box, and api.binance.us has thin volume). It also fetches Coinbase Exchange SOL-USD 1h candles as a cross-check. 0.6 s spacing, cached in `cache/`.
- `fetch_extra.py` - OKX SOL-USDT-SWAP funding history, a proxy for perp funding. A 1m kline fetch was started and then killed; its partial data is in cache only, with no csv.
- `engine.py` - numba engine. Resamples 5m into 15m/1h/4h (complete bars only). Indicators: EMA50/200, ATR14 (Wilder), N-bar hi/lo (N = 10..100, shifted, so no lookahead),
  confirmed pivots (k = 3, known 3 bars later), volume SMA20. `signals()` combines a trend filter (none / ema200 / ema50_200 / hhhl) with the level
  (nN / pivot) and a confirmation (close / vol > 1.5x SMA20 / retest within 6 bars). The signal must be a fresh close beyond the level. `simulate()`: one position at a time;
  entry at the 5m open at (TF close + bot cycle). Cycle 0 = venue-side stop/TP order checked on 5m OHLC (stop checked before target, a gap fills at the open).
  Cycle 5/10/15 = the bot only checks at those clock times and exits at that 5m open. Exits: fixed R:R or a chandelier trail updated at TF closes. Carry arrays are per 5m bar.
- `run.py` - full study, **written but never run** (stopped by the handoff). Grid: 4 TF x 4 trend x 3 level x 3 confirm x 3 stop x 3 exit = 1,296 per track.
  Tracks: A = spot long-only, B = long+short on Jupiter perps. Selection is by in-sample t-stat (top 5) plus 2 pre-registered defaults. For each finalist it runs:
  bootstrap CI, 1,000-run Monte Carlo of drawdown, monthly stability, neighbour sweep with a lucky-number flag, cost lo/mid/hi x cycle 0/5/10/15,
  Jupiter vs Drift, and a random-entry baseline (1,000 runs). It also does a rolling walk-forward re-optimisation (train 9 months, trade the next 3) and buy-and-hold over IS/OOS. Output goes to out/grid.csv and out/summary.json.
  Still TODO: write the leaderboard rows (columns = /workspace/lab/leaderboard.csv header; persist via out/leaderboard_extra_soltrend.json, which backtest.py keeps)
  and render the report. Scoring follows METHOD.md, with stability on calendar months instead of nights.
- `smoke.py` - sanity run of the 2 pre-registered defaults only (output in out/smoke.txt).
- Run: `cd /workspace/lab/sol-trend && .venv/bin/python run.py`. The venv has numba and scipy, with system pandas. smoke.py takes about 2 s; the full grid was not timed.

## Data (data/)
| file | source | coverage | gaps |
|---|---|---|---|
| SOLUSDT_5m.csv | binance.vision | 2024-10-23 22:30 -> 2026-10-23 22:25 UTC, 210,240 bars | 0 |
| SOLUSDT_15m/1h/4h.csv | binance.vision | ~2 years, 70,079 / 17,519 / 4,379 bars | 0 |
| COINBASE_SOLUSD_1h.csv | Coinbase Exchange | 1 year, 8,751 bars (cross-check only; basis not computed yet) | small |
| OKX_SOL_funding.csv | OKX public | 2026-07-20 -> 2026-10-23 only (286 x 8h; OKX keeps ~3 months) | - |
Time is in ms in the csv files; engine converts it to seconds. Price is SOL/USDT, not SOL/USDC (the USDT/USDC basis is ignored).

## Cost assumptions (in run.py)
- A spot (Jupiter/DEX swap SOL<->USDC): all-in 0.1 / 0.2 / 0.3% per side (lo/mid/hi); no carry. Idle USDC yield is ignored.
- B perps, 1x: fee 0.06%/side (Jupiter base fee; Drift, apparently rebranded **Velocity** after an exploit, 6 bps regular taker) + impact/slippage
  0.05 / 0.10 / 0.20% -> 0.11 / 0.16 / 0.26% per side.
  Jupiter borrow: assumed 0.003%/h on both sides (a third-party page showed 0.0016%/h long and 0.0007%/h short; it varies with utilisation).
  Drift funding: **data.api.drift.trade is unreachable from this box (TLS reset)**, so OKX funding is used signed where available (rate/8 per hour).
  Before 2026-07-20 the fallback is to pay 0.003%/h on either side (conservative). Verify the current Drift/Velocity status and funding source.

## Results so far (smoke only: 2 untuned defaults, mid costs, 5-min cycle, OOS = last 40% of time from 2026-01-04). NOT SCORED
| setup | trades (OOS) | win | mean/trade | sum IS | sum OOS | OOS compounded |
|---|---|---|---|---|---|---|
| A spot 1h ema50>200 + close>20-bar high, 2ATR stop, 3ATR trail | 113 (44) | 36% | +0.31% | +20.7% | +14.1% | +10.9% |
| B perp L+S, same rule | 268 (101) | 32% | -0.08% | -34.6% | +13.2% | +6.1% |
| A spot 4h ema200 + 55-bar high | 28 (11) | 32% | +0.44% | +4.3% | +8.1% | +2.8% |
| B perp L+S, same | 58 (23) | 33% | -0.17% | -20.4% | +10.7% | +1.6% |
Buy and hold SOL: OOS -22.8%, full 2 years -39.2%. Both setups beat buy-and-hold OOS, mostly by staying flat in a falling market: the spot bot is in cash much of the time.
B loses in-sample, so it fails "in-sample P&L > 0" and is not a candidate. No CIs, Monte Carlo, neighbours or random baseline have been run yet.
The smoke split uses the raw data start, not run.py's warm-up-adjusted split.

## Open questions / next steps
1. Run run.py and score A and B separately; add SOLT_* rows to the leaderboard.
2. Measure the Coinbase-Binance basis and USDT vs USDC.
3. Find a real Drift/Velocity funding history (the API is blocked here) and Jupiter's historical borrow rates.
4. Compare A against "flat when below EMA200" as a simpler trend baseline: much of the edge may just be avoiding a downtrend.
5. Polymarket parts were dropped. Stub and partial cache are in polymarket/ (see polymarket/HANDOFF.md).
