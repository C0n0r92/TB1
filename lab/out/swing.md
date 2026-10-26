# Swing trading on liquid Solana large caps, 4h + daily, long-only spot (2026-10-24T10:50Z, PAPER research only)

Scripts: sw_fetch.py (data/sw_candles/, Binance spot USDT full history), sw_backtest.py, sw_report.py. Grid: out/sw_grid.csv. Variants in this study: 30 rule settings x 2 cost levels; Lab variants_tried now 939.

## Plain reading

**Plain reading: nothing here is a candidate, and nothing beats buy-and-hold on its merits.** 0 of 60 rows (30 settings x lo/hi cost) pass METHOD, which needs score >= 18, >= 50 trades, and to hold out with >= 20 OOS trades and CI low > 0. On 4h every family loses money held out after costs (mean -0.2% to -1.3% per trade). On daily the trade counts are tiny (10-33 held-out trades across all 7 tokens), so no daily result can be told apart from zero.

- **The held-out window (2026-01-07 to the end) is a bear market for SOL.** SOL hold is -27.5% with a 58% max DD; the equal-weight 7-token hold is -13.4%. Daily trend rules (a) and (b) "beat" SOL there mainly by sitting in cash (exposure 14-30%). The same rules **lost in-sample**: the pre-registered Donchian 1d book is -23% and EMA 1d k3 is -2.9%, with mean trades of -3% to -5%. The long-history view (holdout from 2024-12-13) flips the other way: big IS gains from SOL's 2021 and 2023 runs, then losses held out. That is regime exposure (trend following is long in bulls and chopped in ranges), not a stable edge.
- **(c) RSI(2) daily** is the only family that is positive in BOTH halves and in both history views, with positive medians and low drawdown. But it is tiny and thin:
  - The pre-registered X=10 is flat held out (-0.04% per trade, n=21).
  - The stricter neighbour X=5 makes +3.4% per trade held out, but on n=10 in the common window and n=32 in the long history (CI [-0.6%, +5.4%]).
  - Exposure is about 2-3%, so it earns a few % a year on the book.
  - Pooled long-history X=5: 62 trades, +2.3% per trade, CI [+0.3%, +4.3%], 68% win rate, and still positive without its best trade.
  - RSI(2) on 4h loses: about 0.6% of costs against about 0.3% of gross edge.
- Costs matter less here than in our intraday studies (0.6% against multi-% moves). Even so, the 4h versions lose 0.5-1% per trade at hi cost, and they are also negative or flat at lo cost held out.
- **Worth paper-forward-testing?** Only `SW_rsi2_1d_X5`/`X10`, as a boring, low-exposure watch-list (about 1-2 signals a month across 7 tokens). Keep it paper only and judge it after >= 30 forward trades. Not live: n is far below 50, X=5 is the edge of the sweep, and the pre-registered X=10 is about 0 held out.

## Per-rule headline (hi cost = 0.6% round trip + 0.1% on stop fills; selection never uses OOS)

- **(a) EMA20/50 + ATR trail, 4h, pre-registered `SW_ema_4h_k3`**: held out 99 trades (all tokens), win 32%, mean -1.01%, median -4.90%; book (10%/pos, max 3) OOS -8.7% (max DD 13.0%), per-token fully invested OOS avg -10.4% (median token DD 41%, exposure 19%) vs SOL hold -25.7% (DD 58%) and equal-weight hold -9.2%. IS: 254 trades, mean +0.15%, book +1.9%. Score 12/25, holds OOS no, lucky n/a (not profitable), candidate no.
- **(a) EMA20/50 + ATR trail, 1d, pre-registered `SW_ema_1d_k3`**: held out 18 trades (all tokens), win 33%, mean +1.88%, median -6.45%; book (10%/pos, max 3) OOS +2.8% (max DD 4.4%), per-token fully invested OOS avg +2.6% (median token DD 33%, exposure 22%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 43 trades, mean -4.95%, book -2.9%. Score 13/25, holds OOS insufficient (n_out=12<20), lucky n/a (not profitable), candidate no.
- **(a) EMA20/50 + ATR trail, 1d, best in-sample `SW_ema_1d_k2`**: held out 19 trades (all tokens), win 37%, mean +3.20%, median -4.86%; book (10%/pos, max 3) OOS +3.2% (max DD 2.7%), per-token fully invested OOS avg +7.8% (median token DD 21%, exposure 14%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 44 trades, mean +0.44%, book +3.3%. Score 15/25, holds OOS insufficient (n_out=14<20), lucky yes, candidate no.
- **(b) Donchian breakout, 4h, pre-registered `SW_don_4h_N20_M10`**: held out 166 trades (all tokens), win 29%, mean -0.83%, median -3.01%; book (10%/pos, max 3) OOS -16.5% (max DD 16.5%), per-token fully invested OOS avg -19.9% (median token DD 46%, exposure 32%) vs SOL hold -25.7% (DD 58%) and equal-weight hold -9.2%. IS: 415 trades, mean -0.35%, book +0.7%. Score 12/25, holds OOS no, lucky n/a (not profitable), candidate no.
- **(b) Donchian breakout, 4h, best in-sample `SW_don_4h_N15_M7`**: held out 212 trades (all tokens), win 29%, mean -0.89%, median -3.10%; book (10%/pos, max 3) OOS -16.1% (max DD 19.2%), per-token fully invested OOS avg -24.7% (median token DD 42%, exposure 30%) vs SOL hold -25.7% (DD 58%) and equal-weight hold -9.2%. IS: 528 trades, mean -0.26%, book +18.1%. Score 13/25, holds OOS no, lucky n/a (not profitable), candidate no.
- **(b) Donchian breakout, 1d, pre-registered `SW_don_1d_N20_M10`**: held out 25 trades (all tokens), win 28%, mean +5.49%, median -4.58%; book (10%/pos, max 3) OOS +9.4% (max DD 9.6%), per-token fully invested OOS avg +16.4% (median token DD 28%, exposure 30%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 71 trades, mean -3.45%, book -23.1%. Score 13/25, holds OOS insufficient (n_out=14<20), lucky n/a (not profitable), candidate no.
- **(b) Donchian breakout, 1d, best in-sample `SW_don_1d_N30_M7`**: held out 23 trades (all tokens), win 48%, mean +5.69%, median -2.71%; book (10%/pos, max 3) OOS -1.9% (max DD 7.8%), per-token fully invested OOS avg +14.2% (median token DD 26%, exposure 21%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 53 trades, mean -2.92%, book -20.1%. Score 11/25, holds OOS insufficient (n_out=16<20), lucky n/a (not profitable), candidate no.
- **(c) RSI(2) pullback > 200d SMA, 4h, pre-registered `SW_rsi2_4h_X10`**: held out 157 trades (all tokens), win 58%, mean -0.16%, median +0.53%; book (10%/pos, max 3) OOS -4.1% (max DD 5.5%), per-token fully invested OOS avg -4.6% (median token DD 21%, exposure 6%) vs SOL hold -25.7% (DD 58%) and equal-weight hold -9.2%. IS: 429 trades, mean -0.73%, book -23.0%. Score 12/25, holds OOS no, lucky n/a (not profitable), candidate no.
- **(c) RSI(2) pullback > 200d SMA, 4h, best in-sample `SW_rsi2_4h_X5`**: held out 89 trades (all tokens), win 52%, mean -0.35%, median +0.36%; book (10%/pos, max 3) OOS -3.2% (max DD 5.2%), per-token fully invested OOS avg -4.0% (median token DD 16%, exposure 3%) vs SOL hold -25.7% (DD 58%) and equal-weight hold -9.2%. IS: 256 trades, mean -0.79%, book -14.0%. Score 14/25, holds OOS no, lucky n/a (not profitable), candidate no.
- **(c) RSI(2) pullback > 200d SMA, 1d, pre-registered `SW_rsi2_1d_X10`**: held out 21 trades (all tokens), win 57%, mean -0.04%, median +0.52%; book (10%/pos, max 3) OOS -0.1% (max DD 3.4%), per-token fully invested OOS avg -0.7% (median token DD 12%, exposure 5%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 78 trades, mean +0.53%, book +0.9%. Score 14/25, holds OOS no, lucky yes, candidate no.
- **(c) RSI(2) pullback > 200d SMA, 1d, best in-sample `SW_rsi2_1d_X5`**: held out 10 trades (all tokens), win 60%, mean +3.38%, median +0.92%; book (10%/pos, max 3) OOS +3.4% (max DD 1.0%), per-token fully invested OOS avg +4.7% (median token DD 5%, exposure 2%) vs SOL hold -27.5% (DD 58%) and equal-weight hold -13.4%. IS: 39 trades, mean +1.68%, book +6.3%. Score 18/25, holds OOS insufficient (n_out=10<20), lucky no, candidate no.

## Setup

- Universe: SOL, JUP, BONK, WIF, JTO, PYTH, RAY, Binance spot USDT klines (proxy for Jupiter fills), full history from data-api.binance.vision: SOL 2020-08-11, JUP 2024-01-31, BONK 2023-12-15, WIF 2024-03-05, JTO 2023-12-07, PYTH 2024-02-02, RAY 2021-08-10. All 7 have data, so nothing was dropped.
- Common evaluation window (all tokens listed): 2024-03-05 .. 2026-10-24 (963 days). Indicators warm up on each token's full history (RSI's 200-day SMA needs 200 days, so WIF/JUP/PYTH/JTO/BONK only become eligible for (c) from late 2024).
- Holdout (untouched for selection): last 30% of that window, from **2026-01-08** (4h) / **2026-01-07** (1d) to the end. In-sample 2024-03-05..2026-01-08.
- Fills: signal on a bar's close, fill at the NEXT bar's open. ATR trailing stop is intrabar and fills at min(open, stop) (gap-through). Donchian/RSI exits fill at the next open. Positions still open at the end are closed at the last close (exit 'eod').
- Costs: **lo** = 0.15%/side + 2 x $50 / pool liquidity ($30M SOL, $2M others) = ~0.31% round trip; **hi** = 0.30%/side + the same slippage + 0.10% extra on stop fills = ~0.6-0.7% round trip. At $10-50 tickets size impact is < 0.01%, fees dominate.
- Book: one equal-weight portfolio across the 7 tokens, max 3 open, 10% of realised equity per position (max 30% deployed), one position per token, simultaneous signals taken in list order SOL, JUP, BONK, WIF, JTO, PYTH, RAY. Book max DD is on realised equity. Per-token 'fully invested' = 100% of that token's sleeve in every trade, compounding, mark-to-market DD on bar closes; 'avg ret' is the equal-weight average over the 7 sleeves.
- Rules exactly as pre-registered (textbook): (a) enter on the EMA20 cross above EMA50, exit only on the trailing stop = highest close since entry - k x ATR14 (k = 3; neighbours 2, 4); a fresh cross is needed to re-enter. (b) enter when the close is above the prior 20-bar high, exit when the close is below the prior 10-bar low (N 15/20/30 x M 7/10/15). (c) when close > 200-day SMA (1200 bars on 4h) and RSI(2) < 10 buy; exit when RSI(2) > 70 or close > SMA5 (X 5/10/15). No stops on (b)/(c) beyond the rule exit, as in the textbook versions.
- Scoring per METHOD on the 10% book at hi cost, with one adaptation: sc_stability uses calendar MONTHS (by exit month) instead of Dublin nights, since these trades last days. MC = 1,000 reshuffles of trade order on $100.

## Buy-and-hold over the same windows (hi cost round trip, daily closes)

| token | IS ret | IS max DD | IS ret/DD | OOS ret | OOS max DD | OOS ret/DD | full ret | full CAGR | full max DD |
|---|---|---|---|---|---|---|---|---|---|
| SOL | +1.7% | 60% | +0.03 | -27.5% | 58% | -0.48 | -23.3% | -9.6% | 76% |
| JUP | -63.4% | 90% | -0.70 | +29.1% | 44% | +0.66 | -49.6% | -22.9% | 92% |
| BONK | -70.5% | 86% | -0.82 | -73.9% | 81% | -0.91 | -91.7% | -61.1% | 96% |
| WIF | -67.4% | 94% | -0.72 | -55.4% | 68% | -0.82 | -84.2% | -50.4% | 97% |
| JTO | -84.7% | 93% | -0.91 | -9.8% | 51% | -0.19 | -84.3% | -50.4% | 95% |
| PYTH | -89.6% | 95% | -0.94 | -1.7% | 57% | -0.03 | -89.2% | -57.0% | 97% |
| RAY | +5.1% | 89% | +0.06 | +45.2% | 55% | +0.82 | +57.5% | +18.8% | 93% |
| equal-weight 7 | -52.7% | | | -13.4% | | | -52.1% | | |

The held-out window is a falling market for SOL, BONK and WIF (SOL about -27%, max DD ~58%), and up for JUP and RAY. 'Beating SOL hold' held out mostly means 'being in cash'; the fair yardstick is return per unit of drawdown and the result at the 10% book vs a 30%-deployed hold.

### All settings, 4h, cost hi

| variant (* = pre-registered) | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% ret IS / OOS | book max DD IS / OOS | per-token 100% avg ret IS / OOS | median token max DD IS / OOS | exposure IS / OOS | median hold (d) | score /25 | MC p95 DD | lucky | cand |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `SW_don_4h_N15_M10` | 484 / 193 | +33% / +30% | -0.54% / -1.06% | -4.09% / -3.36% | +12.3% / -14.5% | 22.3% / 19.6% | -37.3% / -25.1% | 83% / 43% | 39% / 36% | 3.2 | 13 | 44.8% | n/a (not profitable) | no |
| `SW_don_4h_N15_M15` | 417 / 174 | +34% / +29% | -0.55% / -1.26% | -4.87% / -4.48% | -2.5% / -10.7% | 30.4% / 19.5% | -44.8% / -27.8% | 78% / 50% | 46% / 42% | 4.0 | 12 | 46.9% | n/a (not profitable) | no |
| `SW_don_4h_N15_M7` | 528 / 212 | +33% / +29% | -0.26% / -0.89% | -3.02% / -3.10% | +18.1% / -16.1% | 20.2% / 19.2% | -25.4% / -24.7% | 79% / 42% | 34% / 30% | 2.4 | 13 | 46.3% | n/a (not profitable) | no |
| `SW_don_4h_N20_M10` * | 415 / 166 | +33% / +29% | -0.35% / -0.83% | -3.51% / -3.01% | +0.7% / -16.5% | 28.5% / 16.5% | -24.6% / -19.9% | 80% / 46% | 33% / 32% | 3.2 | 12 | 48.4% | n/a (not profitable) | no |
| `SW_don_4h_N20_M15` | 362 / 148 | +33% / +30% | -0.32% / -0.97% | -4.72% / -3.67% | -4.9% / -10.9% | 27.6% / 16.9% | -31.5% / -22.7% | 68% / 53% | 40% / 38% | 4.0 | 12 | 43.3% | n/a (not profitable) | no |
| `SW_don_4h_N20_M7` | 444 / 184 | +33% / +29% | -0.05% / -0.81% | -2.87% / -2.83% | +7.2% / -16.2% | 27.3% / 17.1% | -8.3% / -22.8% | 75% / 44% | 29% / 26% | 2.5 | 12 | 46.7% | n/a (not profitable) | no |
| `SW_don_4h_N30_M10` | 322 / 140 | +35% / +29% | -0.29% / -1.03% | -3.51% / -3.29% | +4.4% / -11.3% | 17.3% / 14.3% | -4.8% / -22.1% | 74% / 38% | 26% / 27% | 3.2 | 12 | 38.6% | n/a (not profitable) | no |
| `SW_don_4h_N30_M15` | 287 / 126 | +35% / +26% | -0.36% / -1.14% | -4.72% / -4.43% | -0.5% / -10.4% | 22.3% / 17.4% | -20.2% / -25.0% | 60% / 46% | 32% / 32% | 4.0 | 12 | 40.0% | n/a (not profitable) | no |
| `SW_don_4h_N30_M7` | 340 / 152 | +36% / +29% | +0.10% / -0.92% | -2.46% / -3.15% | +4.8% / -10.7% | 19.2% / 13.8% | +10.5% / -22.3% | 62% / 39% | 23% / 22% | 2.5 | 12 | 39.0% | n/a (not profitable) | no |
| `SW_ema_4h_k2` | 264 / 102 | +41% / +28% | -0.12% / -0.97% | -2.37% / -2.73% | -3.0% / -10.7% | 16.1% / 15.8% | -7.3% / -13.2% | 55% / 33% | 12% / 10% | 1.8 | 12 | 32.2% | n/a (not profitable) | no |
| `SW_ema_4h_k3` * | 254 / 99 | +34% / +32% | +0.15% / -1.01% | -4.06% / -4.90% | +1.9% / -8.7% | 22.9% / 13.0% | -16.0% / -10.4% | 65% / 41% | 23% / 19% | 3.2 | 12 | 38.5% | n/a (not profitable) | no |
| `SW_ema_4h_k4` | 247 / 93 | +31% / +35% | -0.65% / -0.58% | -5.32% / -4.28% | -18.2% / -6.4% | 32.2% / 19.5% | -38.1% / -7.4% | 76% / 40% | 34% / 31% | 5.0 | 11 | 50.6% | n/a (not profitable) | no |
| `SW_rsi2_4h_X10` * | 429 / 157 | +52% / +58% | -0.73% / -0.16% | +0.14% / +0.53% | -23.0% / -4.1% | 24.5% / 5.5% | -38.5% / -4.6% | 52% / 21% | 7% / 6% | 0.7 | 12 | 31.9% | n/a (not profitable) | no |
| `SW_rsi2_4h_X15` | 564 / 209 | +51% / +56% | -0.83% / -0.34% | +0.10% / +0.40% | -32.9% / -8.4% | 34.7% / 10.0% | -49.7% / -10.7% | 61% / 21% | 9% / 8% | 0.7 | 12 | 43.1% | n/a (not profitable) | no |
| `SW_rsi2_4h_X5` | 256 / 89 | +54% / +52% | -0.79% / -0.35% | +0.33% / +0.36% | -14.0% / -3.2% | 15.6% / 5.2% | -27.1% / -4.0% | 40% / 16% | 4% / 3% | 0.7 | 14 | 21.5% | n/a (not profitable) | no |

### All settings, 1d, cost hi

| variant (* = pre-registered) | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% ret IS / OOS | book max DD IS / OOS | per-token 100% avg ret IS / OOS | median token max DD IS / OOS | exposure IS / OOS | median hold (d) | score /25 | MC p95 DD | lucky | cand |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `SW_don_1d_N15_M10` | 84 / 30 | +26% / +30% | -3.79% / +3.99% | -11.10% / -5.45% | -25.0% / +20.6% | 29.9% / 5.1% | -32.9% / +12.7% | 84% / 31% | 35% / 36% | 16.5 | 14 | 32.1% | n/a (not profitable) | no |
| `SW_don_1d_N15_M15` | 77 / 28 | +25% / +29% | -6.23% / +4.38% | -13.21% / -8.21% | -23.8% / +25.1% | 25.5% / 5.1% | -39.6% / +9.3% | 85% / 39% | 41% / 43% | 22.0 | 16 | 29.9% | n/a (not profitable) | no |
| `SW_don_1d_N15_M7` | 88 / 32 | +25% / +41% | -3.06% / +4.91% | -9.68% / -3.58% | -23.6% / +23.3% | 29.0% / 5.9% | -30.2% / +18.5% | 75% / 27% | 32% / 32% | 15.0 | 14 | 30.2% | n/a (not profitable) | no |
| `SW_don_1d_N20_M10` * | 71 / 25 | +27% / +28% | -3.45% / +5.49% | -8.39% / -4.58% | -23.1% / +9.4% | 25.1% / 9.6% | -34.7% / +16.4% | 73% / 28% | 31% / 30% | 18.5 | 13 | 34.4% | n/a (not profitable) | no |
| `SW_don_1d_N20_M15` | 65 / 24 | +25% / +25% | -6.02% / +5.68% | -10.29% / -7.35% | -23.8% / +6.0% | 23.9% / 11.0% | -44.5% / +13.1% | 79% / 34% | 37% / 34% | 22.0 | 12 | 35.6% | n/a (not profitable) | no |
| `SW_don_1d_N20_M7` | 74 / 27 | +26% / +44% | -2.81% / +6.09% | -8.09% / -3.10% | -22.9% / +17.5% | 23.9% / 7.3% | -29.3% / +23.1% | 64% / 26% | 29% / 26% | 16.0 | 14 | 31.2% | n/a (not profitable) | no |
| `SW_don_1d_N30_M10` | 52 / 21 | +27% / +33% | -3.99% / +5.14% | -11.24% / -7.93% | -20.9% / -5.0% | 23.0% / 10.5% | -30.3% / +9.6% | 57% / 28% | 25% / 24% | 19.0 | 8 | 32.7% | n/a (not profitable) | no |
| `SW_don_1d_N30_M15` | 49 / 20 | +24% / +30% | -7.67% / +5.47% | -13.35% / -9.35% | -24.5% / -6.5% | 24.7% / 10.5% | -42.3% / +9.2% | 67% / 38% | 29% / 27% | 23.0 | 9 | 35.3% | n/a (not profitable) | no |
| `SW_don_1d_N30_M7` | 53 / 23 | +26% / +48% | -2.92% / +5.69% | -11.03% / -2.71% | -20.1% / -1.9% | 22.1% / 7.8% | -26.1% / +14.2% | 61% / 26% | 23% / 21% | 17.5 | 11 | 30.3% | n/a (not profitable) | no |
| `SW_ema_1d_k2` | 44 / 19 | +32% / +37% | +0.44% / +3.20% | -6.71% / -4.86% | +3.3% / +3.2% | 10.4% / 2.7% | -0.5% / +7.8% | 48% / 21% | 9% / 14% | 10.0 | 15 | 25.4% | yes | no |
| `SW_ema_1d_k3` * | 43 / 18 | +21% / +33% | -4.95% / +1.88% | -13.24% / -6.45% | -2.9% / +2.8% | 16.2% / 4.4% | -23.5% / +2.6% | 63% / 33% | 19% / 22% | 19.0 | 13 | 27.2% | n/a (not profitable) | no |
| `SW_ema_1d_k4` | 40 / 18 | +28% / +39% | -9.82% / +7.71% | -19.33% / -9.91% | -22.9% / +18.7% | 23.5% / 2.9% | -44.9% / +15.1% | 73% / 40% | 28% / 34% | 28.0 | 15 | 25.6% | n/a (not profitable) | no |
| `SW_rsi2_1d_X10` * | 78 / 21 | +65% / +57% | +0.53% / -0.04% | +3.07% / +0.52% | +0.9% / -0.1% | 6.3% / 3.4% | +3.5% / -0.7% | 29% / 12% | 7% / 5% | 4.0 | 14 | 11.7% | yes | no |
| `SW_rsi2_1d_X15` | 97 / 33 | +53% / +64% | -0.84% / +1.29% | +0.85% / +3.27% | -6.8% / +2.5% | 12.4% / 2.5% | -14.0% / +6.1% | 38% / 12% | 9% / 7% | 4.0 | 18 | 15.2% | n/a (not profitable) | no |
| `SW_rsi2_1d_X5` | 39 / 10 | +64% / +60% | +1.68% / +3.38% | +2.99% / +0.92% | +6.3% / +3.4% | 2.6% / 1.0% | +12.0% / +4.7% | 14% / 5% | 3% / 2% | 4.0 | 18 | 5.1% | no | no |

### All settings, 4h, cost lo

| variant (* = pre-registered) | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% ret IS / OOS | book max DD IS / OOS | per-token 100% avg ret IS / OOS | median token max DD IS / OOS | exposure IS / OOS | median hold (d) | score /25 | MC p95 DD | lucky | cand |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `SW_don_4h_N15_M10` | 484 / 193 | +34% / +30% | -0.25% / -0.77% | -3.80% / -3.07% | +21.0% / -11.5% | 20.2% / 17.6% | -23.5% / -18.8% | 81% / 42% | 39% / 36% | 3.2 | 13 | 40.8% | n/a (not profitable) | no |
| `SW_don_4h_N15_M15` | 417 / 174 | +34% / +29% | -0.25% / -0.96% | -4.59% / -4.19% | +3.8% / -8.2% | 27.6% / 18.1% | -34.3% / -22.4% | 76% / 49% | 46% / 42% | 4.0 | 13 | 43.0% | n/a (not profitable) | no |
| `SW_don_4h_N15_M7` | 528 / 212 | +34% / +30% | +0.04% / -0.60% | -2.73% / -2.80% | +28.5% / -12.8% | 16.0% / 16.8% | -7.4% / -17.7% | 78% / 40% | 34% / 30% | 2.4 | 13 | 41.7% | n/a (not profitable) | no |
| `SW_don_4h_N20_M10` * | 415 / 166 | +35% / +30% | -0.05% / -0.53% | -3.22% / -2.72% | +7.9% / -14.0% | 25.9% / 14.3% | -10.9% / -14.0% | 78% / 44% | 33% / 32% | 3.2 | 12 | 44.7% | n/a (not profitable) | no |
| `SW_don_4h_N20_M15` | 362 / 148 | +34% / +31% | -0.02% / -0.67% | -4.43% / -3.38% | +0.5% / -8.7% | 25.5% / 15.7% | -20.4% / -17.7% | 65% / 51% | 40% / 38% | 4.0 | 12 | 40.2% | n/a (not profitable) | no |
| `SW_don_4h_N20_M7` | 444 / 184 | +34% / +31% | +0.25% / -0.51% | -2.58% / -2.54% | +15.7% / -13.2% | 24.4% / 14.8% | +9.6% / -16.5% | 73% / 43% | 29% / 26% | 2.5 | 13 | 41.8% | n/a (not profitable) | no |
| `SW_don_4h_N30_M10` | 322 / 140 | +37% / +29% | +0.01% / -0.73% | -3.22% / -3.00% | +10.5% / -8.9% | 15.0% / 12.6% | +7.9% / -17.3% | 71% / 37% | 26% / 27% | 3.2 | 13 | 35.0% | n/a (not profitable) | no |
| `SW_don_4h_N30_M15` | 287 / 126 | +36% / +26% | -0.06% / -0.84% | -4.43% / -4.14% | +4.5% / -8.4% | 20.5% / 16.7% | -10.3% / -20.8% | 58% / 45% | 32% / 32% | 4.0 | 13 | 37.7% | n/a (not profitable) | no |
| `SW_don_4h_N30_M7` | 340 / 152 | +37% / +30% | +0.40% / -0.62% | -2.17% / -2.86% | +11.6% / -8.0% | 16.7% / 12.3% | +26.5% / -17.1% | 60% / 38% | 23% / 22% | 2.5 | 13 | 35.0% | n/a (not profitable) | no |
| `SW_ema_4h_k2` | 264 / 102 | +41% / +30% | +0.28% / -0.57% | -1.97% / -2.34% | +4.6% / -7.6% | 14.1% / 13.6% | +7.8% / -8.1% | 47% / 30% | 12% / 10% | 1.8 | 13 | 27.1% | n/a (not profitable) | no |
| `SW_ema_4h_k3` * | 254 / 99 | +37% / +35% | +0.55% / -0.61% | -3.67% / -4.52% | +8.6% / -6.1% | 19.8% / 11.6% | -3.0% / -5.3% | 62% / 38% | 23% / 19% | 3.2 | 13 | 34.9% | n/a (not profitable) | no |
| `SW_ema_4h_k4` | 247 / 93 | +32% / +37% | -0.26% / -0.18% | -4.94% / -3.90% | -13.4% / -4.1% | 29.7% / 18.0% | -28.8% / -2.6% | 74% / 39% | 34% / 31% | 5.0 | 12 | 47.1% | n/a (not profitable) | no |
| `SW_rsi2_4h_X10` * | 429 / 157 | +55% / +60% | -0.43% / +0.14% | +0.44% / +0.83% | -13.9% / -0.2% | 18.9% / 3.9% | -26.6% / +1.9% | 46% / 19% | 7% / 6% | 0.7 | 14 | 23.8% | n/a (not profitable) | no |
| `SW_rsi2_4h_X15` | 564 / 209 | +54% / +60% | -0.54% / -0.04% | +0.40% / +0.70% | -23.0% / -3.4% | 25.5% / 6.0% | -38.6% / -2.7% | 52% / 18% | 9% / 8% | 0.7 | 13 | 33.5% | n/a (not profitable) | no |
| `SW_rsi2_4h_X5` | 256 / 89 | +57% / +55% | -0.49% / -0.05% | +0.63% / +0.66% | -7.9% / -0.7% | 10.9% / 4.0% | -19.0% / -0.1% | 38% / 14% | 4% / 3% | 0.7 | 15 | 16.1% | n/a (not profitable) | no |

### All settings, 1d, cost lo

| variant (* = pre-registered) | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% ret IS / OOS | book max DD IS / OOS | per-token 100% avg ret IS / OOS | median token max DD IS / OOS | exposure IS / OOS | median hold (d) | score /25 | MC p95 DD | lucky | cand |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `SW_don_1d_N15_M10` | 84 / 30 | +27% / +30% | -3.50% / +4.31% | -10.83% / -5.16% | -24.0% / +21.1% | 29.4% / 5.1% | -30.5% / +14.1% | 84% / 30% | 35% / 36% | 16.5 | 14 | 31.3% | n/a (not profitable) | no |
| `SW_don_1d_N15_M15` | 77 / 28 | +25% / +29% | -5.94% / +4.70% | -12.95% / -7.94% | -23.0% / +25.6% | 25.1% / 5.1% | -37.7% / +10.6% | 85% / 39% | 41% / 43% | 22.0 | 17 | 29.3% | n/a (not profitable) | no |
| `SW_don_1d_N15_M7` | 88 / 32 | +26% / +44% | -2.77% / +5.22% | -9.41% / -3.29% | -22.5% / +23.9% | 28.4% / 5.8% | -27.6% / +20.1% | 74% / 27% | 32% / 32% | 15.0 | 16 | 29.3% | n/a (not profitable) | no |
| `SW_don_1d_N20_M10` * | 71 / 25 | +28% / +28% | -3.16% / +5.81% | -8.12% / -4.30% | -22.2% / +9.9% | 24.3% / 9.4% | -32.6% / +17.6% | 73% / 27% | 31% / 30% | 18.5 | 13 | 33.6% | n/a (not profitable) | no |
| `SW_don_1d_N20_M15` | 65 / 24 | +26% / +25% | -5.74% / +6.00% | -10.02% / -7.07% | -23.0% / +6.4% | 23.3% / 10.7% | -42.9% / +14.2% | 79% / 34% | 37% / 34% | 22.0 | 12 | 34.9% | n/a (not profitable) | no |
| `SW_don_1d_N20_M7` | 74 / 27 | +26% / +48% | -2.51% / +6.40% | -7.81% / -2.81% | -22.0% / +18.0% | 23.3% / 7.1% | -27.0% / +24.4% | 63% / 26% | 29% / 26% | 16.0 | 14 | 30.2% | n/a (not profitable) | no |
| `SW_don_1d_N30_M10` | 52 / 21 | +27% / +33% | -3.70% / +5.46% | -10.97% / -7.66% | -20.2% / -4.6% | 22.3% / 10.3% | -28.6% / +10.6% | 57% / 28% | 25% / 24% | 19.0 | 8 | 32.0% | n/a (not profitable) | no |
| `SW_don_1d_N30_M15` | 49 / 20 | +24% / +30% | -7.39% / +5.79% | -13.09% / -9.08% | -23.8% / -6.1% | 24.1% / 10.3% | -41.1% / +10.1% | 67% / 37% | 29% / 27% | 23.0 | 9 | 34.7% | n/a (not profitable) | no |
| `SW_don_1d_N30_M7` | 53 / 23 | +26% / +48% | -2.63% / +6.01% | -10.76% / -2.41% | -19.3% / -1.5% | 21.4% / 7.6% | -24.3% / +15.3% | 60% / 26% | 23% / 21% | 17.5 | 12 | 29.5% | n/a (not profitable) | no |
| `SW_ema_1d_k2` | 44 / 19 | +32% / +37% | +0.85% / +3.61% | -6.33% / -4.48% | +4.9% / +3.8% | 10.1% / 2.5% | +1.9% / +9.0% | 47% / 21% | 9% / 14% | 10.0 | 15 | 24.5% | yes | no |
| `SW_ema_1d_k3` * | 43 / 18 | +21% / +33% | -4.56% / +2.29% | -12.89% / -6.08% | -2.0% / +3.3% | 15.8% / 4.3% | -21.7% / +3.7% | 62% / 32% | 19% / 22% | 19.0 | 13 | 26.4% | n/a (not profitable) | no |
| `SW_ema_1d_k4` | 40 / 18 | +30% / +39% | -9.46% / +8.11% | -19.01% / -9.55% | -22.3% / +19.1% | 22.9% / 2.8% | -43.7% / +16.2% | 72% / 40% | 28% / 34% | 28.0 | 15 | 25.1% | n/a (not profitable) | no |
| `SW_rsi2_1d_X10` * | 78 / 21 | +68% / +57% | +0.83% / +0.26% | +3.38% / +0.82% | +2.9% / +0.5% | 5.9% / 3.0% | +7.1% / +0.2% | 28% / 12% | 7% / 5% | 4.0 | 16 | 10.8% | yes | no |
| `SW_rsi2_1d_X15` | 97 / 33 | +53% / +64% | -0.54% / +1.59% | +1.16% / +3.58% | -4.5% / +3.5% | 10.8% / 2.4% | -10.6% / +7.7% | 38% / 12% | 9% / 7% | 4.0 | 18 | 13.8% | n/a (not profitable) | no |
| `SW_rsi2_1d_X5` | 39 / 10 | +64% / +60% | +1.99% / +3.69% | +3.30% / +1.22% | +7.5% / +3.7% | 2.6% / 1.0% | +14.1% / +5.2% | 14% / 5% | 3% / 2% | 4.0 | 21 | 4.9% | no | no |

## Return per unit of drawdown, pre-registered rules, held out (hi cost)

| rule | tf | book 10% OOS ret | book DD | ret/DD | per-token 100%: avg ret | median DD | SOL sleeve ret | SOL sleeve DD | SOL hold ret | SOL hold DD | SOL hold ret/DD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SW_don_1d_N20_M10` | 1d | +9.4% | 9.6% | +0.98 | +16.4% | 28% | -9.0% | 21% | -27.5% | 58% | -0.48 |
| `SW_don_4h_N20_M10` | 4h | -16.5% | 16.5% | -1.00 | -19.9% | 46% | -10.5% | 37% | -25.7% | 58% | -0.44 |
| `SW_ema_1d_k3` | 1d | +2.8% | 4.4% | +0.63 | +2.6% | 33% | +22.7% | 19% | -27.5% | 58% | -0.48 |
| `SW_ema_4h_k3` | 4h | -8.7% | 13.0% | -0.67 | -10.4% | 41% | +12.8% | 15% | -25.7% | 58% | -0.44 |
| `SW_rsi2_1d_X10` | 1d | -0.1% | 3.4% | -0.04 | -0.7% | 12% | -1.8% | 7% | -27.5% | 58% | -0.48 |
| `SW_rsi2_4h_X10` | 4h | -4.1% | 5.5% | -0.74 | -4.6% | 21% | -4.2% | 10% | -25.7% | 58% | -0.44 |

## Per token, pre-registered rules, hi cost (fully invested sleeve: return / max DD / trades, IS | OOS)

| rule | SOL | JUP | BONK | WIF | JTO | PYTH | RAY |
|---|---|---|---|---|---|---|---|
| `SW_don_1d_N20_M10` | +11%/42%/10 \| -9%/21%/5 | -67%/86%/12 \| -7%/49%/4 | -53%/65%/11 \| -20%/32%/2 | -54%/73%/9 \| -22%/28%/3 | -69%/74%/8 \| -45%/58%/5 | -79%/84%/10 \| +48%/27%/3 | +70%/54%/11 \| +170%/26%/3 |
| `SW_don_4h_N20_M10` | -26%/54%/59 \| -11%/37%/24 | +26%/64%/58 \| +9%/30%/26 | +90%/57%/50 \| -17%/46%/18 | -27%/80%/57 \| -41%/48%/21 | -88%/92%/65 \| -71%/77%/27 | -81%/86%/61 \| +22%/32%/23 | -66%/90%/65 \| -31%/46%/27 |
| `SW_ema_1d_k3` | -7%/40%/6 \| +23%/19%/2 | -73%/74%/8 \| -0%/33%/3 | -5%/55%/7 \| -36%/36%/3 | -48%/63%/6 \| -26%/28%/2 | -79%/79%/7 \| -5%/46%/2 | -62%/64%/4 \| +17%/34%/3 | +109%/43%/5 \| +47%/30%/3 |
| `SW_ema_4h_k3` | +56%/31%/34 \| +13%/15%/12 | -26%/58%/36 \| -6%/38%/15 | -20%/78%/35 \| -30%/43%/16 | +16%/59%/38 \| -23%/45%/13 | -46%/77%/37 \| -71%/71%/16 | -52%/73%/38 \| +66%/20%/14 | -40%/65%/36 \| -22%/41%/13 |
| `SW_rsi2_1d_X10` | -18%/29%/22 \| -2%/7%/2 | +13%/14%/6 \| -13%/21%/6 | +4%/31%/13 \| +0%/0%/0 | -19%/34%/6 \| -2%/14%/3 | -10%/26%/5 \| +6%/27%/6 | +28%/9%/5 \| +14%/3%/3 | +27%/37%/21 \| -8%/12%/1 |
| `SW_rsi2_4h_X10` | -69%/72%/123 \| -4%/10%/18 | -35%/41%/32 \| -19%/28%/39 | -50%/52%/54 \| +0%/0%/0 | -24%/47%/45 \| -1%/15%/24 | -23%/29%/26 \| -17%/30%/42 | -45%/55%/36 \| -9%/21%/16 | -24%/61%/113 \| +17%/21%/18 |
| hold (1d) | +2%/60% \| -28%/58% | -63%/90% \| +29%/44% | -71%/86% \| -74%/81% | -67%/94% \| -55%/68% | -85%/93% \| -10%/51% | -90%/95% \| -2%/57% | +5%/89% \| +45%/55% |

## Same book at 1/3 per position (fully invested when 3 are open), pre-registered, hi cost

| rule | IS ret | IS DD | OOS ret | OOS DD |
|---|---|---|---|---|
| `SW_don_1d_N20_M10` | -61.3% | 64.4% | +19.6% | 29.6% |
| `SW_don_4h_N20_M10` | -19.6% | 69.6% | -47.6% | 47.6% |
| `SW_ema_1d_k3` | -23.6% | 46.5% | +5.9% | 14.5% |
| `SW_ema_4h_k3` | -11.3% | 60.6% | -29.4% | 38.7% |
| `SW_rsi2_1d_X10` | -1.3% | 20.9% | -0.9% | 11.1% |
| `SW_rsi2_4h_X10` | -61.2% | 63.6% | -14.0% | 17.7% |

## Lottery check (hi cost book): P&L on $100 with and without the single best trade

| variant | trades | net $ | net ex best $ | exits |
|---|---|---|---|---|
| `SW_don_1d_N20_M10` | 54 | -15.88 | -28.92 | {'rule': 95, 'eod': 1} |
| `SW_don_4h_N20_M10` | 332 | -15.95 | -32.28 | {'rule': 580, 'eod': 1} |
| `SW_ema_1d_k2` | 52 | +6.63 | -8.46 | {'stop': 63} |
| `SW_ema_1d_k3` | 38 | -0.24 | -16.15 | {'stop': 61} |
| `SW_ema_4h_k3` | 232 | -6.95 | -19.48 | {'stop': 351, 'eod': 2} |
| `SW_rsi2_1d_X10` | 87 | +0.72 | -1.49 | {'rule': 99} |
| `SW_rsi2_1d_X5` | 47 | +9.89 | +6.88 | {'rule': 49} |
| `SW_rsi2_4h_X10` | 504 | -26.12 | -27.49 | {'rule': 582, 'eod': 4} |

## Long-history view (eval from 2020-08-11, holdout = last 30% from 2024-12-13; SOL from 2020, RAY from 2021, others join as listed) — hi cost

| variant | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% IS / OOS (DD) | SOL sleeve IS / OOS (DD) | SOL hold IS / OOS (DD) | RAY sleeve IS / OOS | RAY hold IS / OOS |
|---|---|---|---|---|---|---|---|---|---|
| `SW_ema_4h_k3` | 227 / 247 | +35% / +32% | +0.94% / -1.44% | -3.69% / -4.87% | +13.4% (22%) / -23.6% (27%) | +7% (72%) / +44% (31%) | +7823% (97%) / -55% (78%) | -77% / -58% | +38% / -66% |
| `SW_don_4h_N20_M10` | 379 / 404 | +37% / +29% | +1.77% / -1.27% | -3.37% / -3.69% | +86.2% (25%) / -35.5% (38%) | +940% (82%) / -35% (67%) | +7823% (97%) / -55% (78%) | -1% / -87% | +38% / -66% |
| `SW_rsi2_4h_X10` | 398 / 388 | +56% / +52% | -0.24% / -0.73% | +0.35% / +0.24% | -8.0% (16%) / -23.0% (23%) | -67% (81%) / -39% (43%) | +7823% (97%) / -55% (78%) | +18% / -41% | +38% / -66% |
| `SW_ema_1d_k3` | 37 / 40 | +38% / +25% | +27.69% / -6.00% | -7.48% / -10.94% | +161.9% (9%) / -13.6% (18%) | +2274% (71%) / +3% (31%) | +7816% (96%) / -55% (76%) | +370% / +13% | +38% / -67% |
| `SW_don_1d_N20_M10` | 64 / 58 | +36% / +26% | +19.84% / -0.77% | -5.28% / -5.45% | +134.6% (16%) / -4.9% (21%) | +5521% (74%) / -16% (35%) | +7816% (96%) / -55% (76%) | +160% / +60% | +38% / -67% |
| `SW_rsi2_1d_X10` | 62 / 63 | +65% / +62% | +1.21% / +0.22% | +2.99% / +2.04% | +5.6% (6%) / +0.1% (4%) | +10% (29%) / -11% (18%) | +7816% (96%) / -55% (76%) | +27% / +17% | +38% / -67% |
| `SW_ema_1d_k2` | 38 / 41 | +34% / +34% | +10.85% / -1.11% | -6.31% / -6.42% | +49.2% (8%) / -7.6% (13%) | +80% (57%) / +2% (22%) | +7816% (96%) / -55% (76%) | +631% / +23% | +38% / -67% |
| `SW_rsi2_1d_X5` | 30 / 32 | +77% / +59% | +2.26% / +2.36% | +2.85% / +1.13% | +6.9% (3%) / +7.4% (1%) | +9% (25%) / +5% (17%) | +7816% (96%) / -55% (76%) | +53% / +55% | +38% / -67% |


## Scorecard notes (METHOD)

- Scores are computed on the 10% book at hi cost. Trades means book trades, which are fewer than signals because of the max-3 and one-per-token limits.
- Best score: `SW_rsi2_1d_X5` at 18/25 on the common window. Its OOS risk, drawdown and edge are strong, but 49 trades earn only 2 points and its holds-OOS result is "insufficient" (n_out=10). The highest-scoring 4h rows are 12-14/25.
- The tables show the Monte Carlo p95 drawdown (1,000 reshuffles, $100, 10% sizing). Trend and breakout books reach a 25-35% p95 DD at 10% sizing because their 25-35% win rates mean long losing streaks.
- Lucky flags:
  - `SW_ema_1d_k2` is lucky: it is profitable, and its neighbour k3 is not.
  - `SW_rsi2_1d_X10` is lucky: it is profitable, and its neighbour X15 is not over the full common window.
  - `SW_rsi2_1d_X5` is not flagged, because its only neighbour, X10, is marginally profitable. It sits at the edge of the sweep, so treat that "no" as weak.
- Multiple testing: this study ran 30 settings x 2 costs, and Lab's variants_tried is now 939. With that many tries, a +3%-per-trade result on 10-32 trades is well within luck.

## WHY THIS COULD FAIL (for the only profitable rows: RSI(2) daily X5/X10, EMA 1d k2, Donchian 1d held out)

- **Survivorship**: the 7 tokens are TODAY's liquid Solana large caps. Tokens that were large caps in 2021-2024 and then died are not in the test, such as SRM, MNGO, STEP, SAMO, COPE, ORCA-era DeFi and many 2024 memes. Dip-buying (c) gains the most from this, because every dip in a survivor eventually recovered. Treat every positive number as an upper bound.
- **Small n**: 4h and daily bars on 7 correlated tokens give few independent trades, and daily OOS n is 10-33. Many trades fall on the same days because crypto moves together, so the effective n is smaller still.
- **Regime**: the holdout is a single bear/range regime, and SOL's 2021 and 2023 bull runs dominate the long-history IS. Trend rules look great or terrible depending on which regime lands in which half.
- **Proxy prices**: Binance USDT candles stand in for Jupiter fills. On-chain prints can differ at the daily open, and the BONK, WIF, JUP, JTO and PYTH Binance listings start after their first big moves.
- **Who is on the other side**:
  - RSI(2) dip buys: short-term sellers into a down day and liquidation cascades. We act like a market maker taking on inventory risk, and the risk is the day the dip keeps going, as with SOL during FTX in Nov 2022. The 200-day filter is the only protection; there is no stop.
  - Trend and breakout: late sellers in a trend, and the many false-breakout days where we buy into someone else's selling.

## Data / reproducibility

- Candles: data/sw_candles/bn_<SYM>_{4h,1d}.csv, fetched by sw_fetch.py from the free public data-api.binance.vision. Full 4h and 1d history was available, so the existing 1h caches were not needed.
- Rerun: `python3 sw_fetch.py && python3 sw_write.py`. sw_write.py also restages out/.sw_rows.json. Then merge under the lock: `flock out/.pipeline.lock python3 merge_extra.py SW out/.sw_rows.json`.
- Leaderboard: 60 SW_* rows (30 settings x lo/hi). This is PAPER research only; nothing here is a trade signal or a proposal for live.
