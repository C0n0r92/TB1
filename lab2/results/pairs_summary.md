# Track B: pairs mean reversion (Chan): results, 2026-10-24 (PAPER ONLY, research only)

**Verdict: nothing clears costs out of sample.** Of 20 held-out variants (4 universe/timeframe books x OLS/Kalman x pair/long-only, plus regime gates), 19 lose money.
The one positive row (majors 15m, rolling OLS, long-only: +3.3%, 178 trades) has a bootstrap CI on mean net/trade of [-0.70%, +0.98%]. Its train result was -36%. It turns negative without its single best trade. It also trailed simply holding SOL (+35.5%) over the same window. It is long beta in a rally (RAY +188%, KMNO +126%), not a spread edge.

## Setup (all fixed before the test window was run)
- Data: Binance public spot klines (data-api.binance.vision) for 17 Solana majors/mid tokens, 1h (400 d) and 15m (200 d). Lab's GeckoTerminal older-coins cache (read-only) covers 22 tokens incl. SOL: 1h 06-21..10-23 and 15m 09-10..10-23. Stablecoin-like series (log-price std < 5%, e.g. CASH) are dropped.
- Windows (train / test):
  - majors 1h: 2025-09-20..2026-06-30 / 06-30..10-23
  - majors 15m: 04-08..08-15 / 08-15..10-23
  - old 1h: 06-22..08-31 / 08-31..10-23
  - old 15m: 09-12..10-05 / 10-05..10-23 (only 18 days, thin)
- Pair choice on train only: Engle-Granger on log prices (both orderings, min p) < 0.05, Johansen trace r=0 rejected at 95%, hedge ratio > 0. Pairs are ranked by p. Max 10 pairs, max 2 per token (without the cap, ZEREBRO, which looks stationary on its own, filled every slot).
  Pairs tested / passing EG / passing EG+Johansen: majors 1h 136/14/6, majors 15m 136/19/18, old 1h 120/30/30, old 15m 103/16/13. At p<0.05 about 5% of pairs pass by chance, so the majors-1h list is close to the false-positive rate.
- Trading: entry |z|>2, exit when z crosses 0 (Zero spec). The signal is taken at bar close t and filled at close t+1. Shares are fixed for the life of the trade. Each pair gets equal capital, gross exposure 1, no compounding, marked to market every bar. Open trades are force-closed at the end of the window.
- Hedge: (a) rolling OLS on log prices, lookback L picked on train from {48, 96, 192, 384}; every book chose 384. (b) Kalman (Chan 3.3, z = forecast error / sqrt(Q)), (delta, Ve) picked on train from {1e-5, 1e-4} x {1e-4, 1e-3}. (c) long-only: hold only the long leg (the laggard) at full size.
- Costs per side on every leg's notional: 0.3% for SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP; 1% for BOME TNSR PNUT KMNO IO and the whole older-coins universe. A round trip therefore costs 0.6-2% of the position.
- Regime (src/regime.py, point-in-time, closed 4h bars only): crash / high_vol / trending / choppy, from SOL+BTC 4h EMA20 slope and SOL ATR percentile. Gate = regimes whose TRAIN mean net/trade > 0 with >= 10 train trades, then applied once to test.

## Out-of-sample results (net of costs)
| book | hedge | mode | params (train) | train trades / net | OOS trades | OOS net | Sharpe | max DD | mean net/trade [95% CI] | gross mean/trade |
|---|---|---|---|---|---|---|---|---|---|---|
| majors 1h | OLS | pair | L=384 | 131 / -26.6% | 49 | -31.3% | -3.30 | -33.3% | -3.20% [-6.46, -0.42] | -1.84% |
| majors 1h | OLS | long | L=384 | 131 / -26.1% | 49 | -21.0% | -2.21 | -28.7% | -2.14% [-5.46, +0.80] | -0.81% |
| majors 1h | Kalman | pair | 1e-5, 1e-3 | 60 / -18.8% | 45 | -7.8% | -1.75 | -11.3% | -0.87% [-2.46, +0.54] | +0.46% |
| majors 1h | Kalman | long | 1e-5, 1e-3 | 60 / -21.5% | 45 | -4.1% | -0.80 | -11.2% | -0.46% [-2.11, +1.11] | +0.83% |
| majors 15m | OLS | pair | L=384 | 279 / -45.3% | 178 | -32.7% | -8.21 | -37.5% | -1.10% [-1.55, -0.68] | +0.43% |
| majors 15m | OLS | long | L=384 | 279 / -36.3% | 178 | **+3.3%** | +0.73 | -16.0% | +0.11% [-0.70, +0.98] | +1.36% |
| majors 15m | Kalman | pair | 1e-5, 1e-3 | 24 / -5.5% | 9 | -3.2% | -3.82 | -3.8% | -2.14% | -0.44% |
| majors 15m | Kalman | long | 1e-5, 1e-3 | 24 / +0.7% | 9 | -1.2% | -3.09 | -1.3% | -0.80% | -0.04% |
| old 1h | OLS | pair | L=384 | 38 / +4.9% | 37 | -13.0% | -2.08 | -23.8% | -2.45% [-4.31, -0.70] | -0.44% |
| old 1h | OLS | long | L=384 | 38 / +23.9% | 37 | -4.5% | -0.86 | -13.2% | -0.86% [-4.15, +2.75] | +1.15% |
| old 1h | Kalman | pair | 1e-5, 1e-4 | 95 / -20.3% | 86 | -27.7% | -5.41 | -27.7% | -2.25% [-3.62, -1.06] | -0.25% |
| old 1h | Kalman | long | 1e-5, 1e-4 | 95 / -15.6% | 86 | -28.8% | -9.98 | -28.8% | -2.34% [-3.36, -1.39] | -0.34% |
| old 15m | OLS | pair | L=384 | 28 / +2.8% | 48 | -18.7% | -21.3 | -19.0% | -1.95% [-2.76, -1.27] | +0.04% |
| old 15m | OLS | long | L=384 | 28 / +10.0% | 48 | -31.8% | -16.4 | -32.0% | -3.31% [-4.90, -1.99] | -1.33% |
| old 15m | Kalman | pair | 1e-5, 1e-4 | 31 / -9.3% | 13 | -6.8% | -9.19 | -6.8% | -2.60% | -0.61% |
| old 15m | Kalman | long | 1e-5, 1e-4 | 31 / -11.7% | 13 | -8.0% | -7.91 | -8.0% | -3.09% | -1.10% |

Regime-gated reruns (gate chosen on train): majors 1h OLS pair [trending] 25 tr -9.8%; majors 1h OLS long [high_vol] 12 tr -19.3%; majors 15m OLS long [high_vol] 42 tr -5.3%; old 1h OLS pair/long [choppy, high_vol, trending] = ungated, -13.1% / -4.7%; old 1h Kalman long [high_vol] 29 tr -11.2%; old 15m OLS pair/long [trending] 5 tr -1.2% / -3.3%. **No gate helps out of sample.**
By regime (OOS, ungated): no book is positive in a regime with >= 50 trades. The small positive cells (e.g. majors 1h OLS long in 'trending': 16 trades, +2.4%/trade) are in regimes that train did not pick, so they don't count.

Only books with >= 50 OOS trades can support any claim: majors 15m OLS (pair, long), old 1h Kalman (pair, long). Three of the four are clearly negative (CI below 0); the fourth is the long-only row above (CI spans 0).

## Buy-and-hold over the same test windows (one round trip of cost)
- majors 1h (06-30..10-23): SOL +35.5% (Sharpe 2.16, DD -19.0%); legs: RAY +184%, KMNO +113%, BOME +46%, PENGU +22%, WIF +5%, PNUT -4%, TNSR -15%.
- majors 15m (08-15..10-23): SOL +35.5% (DD -19.2%); RAY +188%, KMNO +126%, W +55%, WIF +35%, PENGU +26%, PNUT +2%, TNSR -8%.
- old 1h (08-31..10-23): SOL -1.5% (DD -19.0%); MEW +15%, pippin -13%, Pnut -14%, POPCAT -17%, ZEREBRO -24%, Fartcoin -25%, TRUMP -30%, BOME -33%.
- old 15m (10-05..10-23): SOL -17.6%; all legs -17% to -41%.
Pairs books avoided most of the old-coins drawdown, but they still lost 5-32% net. On majors they badly lagged holding.

## Why it fails
- The spread edge before costs is tiny. Pair-mode gross mean per trade is -1.8% to +0.5%, against a 0.6-2% round trip. Most "cointegrated" pairs break in the test window: the half-lives of 25-300 bars do not hold up.
- Long-only gross returns are mostly beta: positive in the rising majors window, negative in the falling old-coins window.
- Selection is multiple-tested (495 pairs) and every OLS book chose the edge of its lookback grid (384), so even the train fits are fragile.
- Untested: a lower-cost venue (perps with maker fees ~0.02-0.05%) could change the arithmetic for majors pairs. Shorting a leg on Solana spot is not practical anyway.

## Files
pairs_summary.csv (all rows incl. holds), pairs_trades_oos.csv (every OOS trade with regime), pairs_selection_train.csv (all pairs with EG p, Johansen, beta, half-life), pairs_params_train.json, pairs_run.log. Code: src/pairs.py, src/regime.py, src/data.py.
