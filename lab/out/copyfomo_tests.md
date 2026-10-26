# Copyfomo leader tests (2026-10-24T15:25:34+00:00, PAPER ONLY)

Closed leader round trips: 140 (ExactTallTakin, _benjitrades). With 1-min candles: 131; candle fetch attempted: 140; trades with a rugcheck report: 140; leader fill from own swap: 131/131. This run: 0 GeckoTerminal + 0 rugcheck calls.
Costs: 2%/side + $0.05, slippage on $20,000 assumed pool, stop -25% with 5 pts extra slippage (gap: open - 5 pts), bot lag 10s, $10/trade, exit at leader's sell price. No max-open cap (per-trade comparison). OOS = buys after 2026-10-07T20:45:53+00:00.

## 1. Chase cap sweep (copyfomo has max chase 15% on; our fill = chart price at buy + bot lag vs leader's own fill)

| variant | trades | win | mean | CI95 | net $ | net ex best $ | skipped (chase) | OOS mean |
|---|---|---|---|---|---|---|---|---|
| chase off (lag 10s) | 87 (37 OOS) | 38% | +4.6% | [-0.15,+0.24] | +40.09 | -43.94 | 0 | -5.5% |
| chase 10% (lag 10s) | 83 (36 OOS) | 36% | +5.1% | [-0.15,+0.26] | +42.71 | -41.32 | 4 | -5.8% |
| chase 15% (lag 10s) | 85 (37 OOS) | 38% | +5.1% | [-0.15,+0.25] | +43.43 | -40.60 | 2 | -5.5% |
| chase 25% (lag 10s) | 87 (37 OOS) | 38% | +4.6% | [-0.15,+0.24] | +40.09 | -43.94 | 0 | -5.5% |

Chase at 10s: median -2.7%, share > 10/15/25%: 5% / 2% / 0%.

## 2. Rugcheck hard rejects at buy time (skip rejects) -- chase 15%, lag as above

PIT: mint/freeze is reconstructable (authority can only be revoked, and pump.fun mints are revoked at creation). LP lock, top10, creator %, danger flags come from a report fetched AFTER the trade = LOOKAHEAD (buy-time holders cannot be reconstructed: no holder history for these mints; Scout's early-buyer files do not cover them).

| variant | trades | win | mean | CI95 | net $ | net ex best $ | skipped (chase) | OOS mean |
|---|---|---|---|---|---|---|---|---|
| no filter (coins with report) | 85 (37 OOS) | 38% | +5.1% | [-0.15,+0.25] | +43.43 | -40.60 | 2 | -5.5% |
| skip mint_freeze_open [LOOKAHEAD] | 85 (37 OOS) | 38% | +5.1% | [-0.15,+0.25] | +43.43 | -40.60 | 2 | -5.5% | rejected 0 |
| skip lp_unlocked [LOOKAHEAD] | 82 (36 OOS) | 38% | -4.5% | [-0.09,-0.00] | -37.26 | -44.30 | 2 | -5.2% | rejected 8 coins-trades (3 simulable): their mean +269.0% |
| skip top10_gt18 [LOOKAHEAD] | 65 (27 OOS) | 40% | +8.4% | [-0.17,+0.34] | +54.85 | -29.18 | 2 | -8.7% | rejected 39 coins-trades (20 simulable): their mean -5.7% |
| skip top10_gt25 [LOOKAHEAD] | 75 (30 OOS) | 39% | +7.2% | [-0.15,+0.30] | +54.21 | -29.82 | 2 | -5.4% | rejected 18 coins-trades (10 simulable): their mean -10.8% |
| skip creator_gt5 [LOOKAHEAD] | 85 (37 OOS) | 38% | +5.1% | [-0.15,+0.25] | +43.43 | -40.60 | 2 | -5.5% | rejected 0 |
| skip danger_flags [LOOKAHEAD] | 32 (11 OOS) | 31% | +20.3% | [-0.32,+0.73] | +64.83 | -19.20 | 0 | -2.7% | rejected 70 coins-trades (53 simulable): their mean -4.0% |
| skip ALL (mint/freeze, LP, top10>25, creator, danger) [LOOKAHEAD] | 20 (4 OOS) | 35% | -2.1% | [-0.13,+0.09] | -4.29 | -11.33 | 0 | +9.5% | rejected 91 coins-trades (65 simulable): their mean +7.3% |

## 3. Entry delay cost (alerts + filtered manual copy; chase cap 15%)

1-min candles interpolated open->close: sub-minute delays are approximations.

| variant | trades | win | mean | CI95 | net $ | net ex best $ | skipped (chase) | OOS mean |
|---|---|---|---|---|---|---|---|---|
| delay 0s | 85 (36 OOS) | 44% | +4.7% | [-0.15,+0.25] | +40.37 | -43.79 | 2 | -7.2% |
| delay 10s | 85 (37 OOS) | 38% | +5.1% | [-0.15,+0.25] | +43.43 | -40.60 | 2 | -5.5% |
| delay 20s | 86 (37 OOS) | 33% | +3.4% | [-0.16,+0.23] | +28.88 | -55.02 | 1 | -5.9% |
| delay 40s | 83 (37 OOS) | 34% | +4.4% | [-0.16,+0.25] | +36.74 | -46.97 | 4 | -4.1% |
| delay 60s | 80 (35 OOS) | 39% | +6.9% | [-0.14,+0.28] | +55.03 | -28.51 | 7 | -0.2% |

## Caveats

- Leader P&L/exit from Scout's trader_trades.csv (their round trips); open positions excluded.
- Pool depth assumed; real slippage on small pools is larger. Candle history for dead coins may be missing (no_data).
- 2 leaders only; trades are not independent (same leader, same nights).
