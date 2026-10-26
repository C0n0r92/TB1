# Mean reversion (Ernest Chan style), long-only z-score dip buys, liquid Solana tokens (2026-10-24T00:45Z, PAPER research only)

Scope: single-token long-only dip buys only (pairs dropped per Zero/parent 00:04Z; Lab 2 owns pairs; no pairs code was written). Script: mr_dip.py + mr_report.py; candles: mr_fetch.py -> data/mr_candles/. Grid: out/mr_grid.csv.

## Headline

- **1h** best IS `MR_dip_1h_L50_z2.5_N16_z4_off`: IS -0.02% [-0.29%, +0.27%] on 440 trades, OOS +0.00% [-0.38%, +0.37%] on 272 (hi cost); lo cost OOS +0.31% [-0.05%, +0.68%]. Score 14/25, candidate no. OOS nightly book mean -0.055%, P(+10%) 0.0%, P(-20%) 0.0%.
- **15m** best IS `MR_dip_15m_L50_z2.0_N32_z4_ema50`: IS -0.27% [-0.46%, -0.06%] on 385 trades, OOS -0.65% [-1.08%, -0.23%] on 133 (hi cost); lo cost OOS -0.34% [-0.77%, +0.08%]. Score 14/25, candidate no. OOS nightly book mean -0.129%, P(+10%) 0.0%, P(-20%) 0.0%.
- **5m** best IS `MR_dip_5m_L50_z2.0_N48_z4_ema50`: IS -0.43% [-0.52%, -0.33%] on 1021 trades, OOS -0.55% [-0.73%, -0.38%] on 356 (hi cost); lo cost OOS -0.24% [-0.44%, -0.07%]. Score 12/25, candidate no. OOS nightly book mean -0.237%, P(+10%) 0.0%, P(-20%) 0.0%.


**Plain reading: negative after costs.** No family clears costs held-out at the realistic (hi, ~0.6-0.7% round trip) cost; 0 of 288 variants are positive both in-sample and held-out at hi cost (night window), and none is a METHOD candidate (best score 14/25, all fail the OOS test). Hurst ~0.48, VR(4) ~0.97, ADF never rejects a random walk: there is very little reversion at 5m-1h to harvest. Gross edge before fees is about 0 to +0.1%/trade (median), smaller than the 0.3-0.6% round trip.
The regime filter (SOL above its 4h EMA50, or EMA50 sloping up) makes things WORSE on 1h and does nothing on 5m/15m.
Only lead (weak, do not trade): 1h z <= -2.5 vs 50-bar mean bought at night and mostly sold at the 08:00 flat (85% of exits are the 08:00 close), at the LOW 0.3% cost, all signals: IS +0.29%/trade [+0.01, +0.58] n=440, OOS +0.31% [-0.05, +0.68] n=272. It vanishes at the hi cost (OOS +0.00%) and as a real max-3 book (OOS -0.14% lo / -0.44% hi), and today's-top-20 survivorship flatters it. If anything, it is an overnight-drift effect in survivors, not reversion to the mean.

## Universe and data

Top Solana-ecosystem tokens by 24h volume from CoinGecko (category solana-ecosystem, fetched 2026-10-24 00:0xZ, data/mr_candles/cg_solana_top.json), dropping stables, wrapped/bridged assets (wSOL, cbBTC, WBTC, ZEC, HYPE...), LSTs (JitoSOL), tokenized stocks and multichain non-SPL tokens (ENA, LINK, AAVE, INJ, STRK, CAKE...), plus Zero's POPCAT.

| token | source | 1h bars | 15m bars | 5m bars | assumed pool liq (hi-cost slippage) |
|---|---|---|---|---|---|
| BOME | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| BONK | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| FARTCOIN | GeckoTerminal top pool | 4995 (2026-03-29..2026-10-23) | 8472 (2026-07-23..2026-10-24) | 20965 (2026-07-23..2026-10-24) | $7.2M |
| GRASS | GeckoTerminal top pool | 4994 (2026-03-29..2026-10-23) | 8939 (2026-07-18..2026-10-24) | 21961 (2026-07-18..2026-10-24) | $0.5M |
| JTO | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| JUP | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| KMNO | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| MEW | GeckoTerminal top pool | 4993 (2026-03-29..2026-10-23) | 8598 (2026-07-18..2026-10-24) | 18971 (2026-07-18..2026-10-24) | $9.3M |
| PENGU | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| POPCAT | GeckoTerminal top pool | 4995 (2026-03-29..2026-10-23) | 8590 (2026-07-18..2026-10-23) | 18971 (2026-07-18..2026-10-23) | $3.5M |
| PUMP | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| PYTH | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| RAY | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| RENDER | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| SOL | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $30.0M |
| TRUMP | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| USELESS | GeckoTerminal top pool | 4995 (2026-03-29..2026-10-23) | 9071 (2026-07-20..2026-10-24) | 24953 (2026-07-20..2026-10-24) | $4.1M |
| W | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |
| WIF | Binance spot USDT (proxy) | 8759 (2025-10-24..2026-10-23) | 8831 (2026-07-24..2026-10-23) | 26495 (2026-07-24..2026-10-24) | $2.0M |

- **Survivorship**: the list is TODAY's top 20 by volume. Tokens that were liquid 6-12 months ago and then died (and would have produced the worst 'dips') are not in it, and today's winners are. That biases dip-buying UP (dips in survivors recovered by construction). Treat any positive result as an upper bound.
- **Proxy**: Binance prices are a proxy for Jupiter fills; on-chain prices lag/lead CEX by seconds and the CEX dip may be shallower on-chain. GeckoTerminal tokens use one pool's OHLCV (15m resampled from 5m).
- Costs: 'lo' = 0.15%/side (0.3% round trip); 'hi' = 0.30%/side + 2 x $15 / pool liquidity per side + 0.1% extra on % stops (about 0.6-0.7% round trip). At $10-15 tickets size slippage is <0.01% on these pools, so fees dominate.

## Does mean reversion exist? (in-sample only)

Hurst on log price (H < 0.5 = mean reverting, 0.5 = random walk), variance ratio of returns VR(q) (< 1 = reverting), ADF p-value on log price (< 0.05 = stationary), half-life of the price level (bars), and half-life of the deviation from the 50-bar mean (what the strategy actually trades).

| tf | tokens | median H | tokens H<0.45 | median VR(2) | median VR(4) | median VR(16) | tokens VR(4)<0.9 | ADF p<0.05 | median price half-life (days) | median dev50 half-life (bars) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1h | 19 | 0.476 | 0 | 0.987 | 0.975 | 0.903 | 4 | 0/19 | 28 | 20.1 |
| 15m | 19 | 0.487 | 2 | 1.004 | 0.928 | 0.864 | 6 | 0/19 | 12 | 20.1 |
| 5m | 19 | 0.480 | 4 | 0.995 | 0.972 | 0.902 | 6 | 0/19 | 14 | 19.0 |

Per token (1h): BOME H=0.45 VR4=0.83, BONK H=0.49 VR4=0.98, FARTCOIN H=0.46 VR4=0.89, GRASS H=0.51 VR4=0.96, JTO H=0.47 VR4=1.00, JUP H=0.49 VR4=1.00, KMNO H=0.48 VR4=1.03, MEW H=0.48 VR4=0.89, PENGU H=0.48 VR4=0.98, POPCAT H=0.46 VR4=0.87, PUMP H=0.46 VR4=0.94, PYTH H=0.48 VR4=0.99, RAY H=0.48 VR4=0.99, RENDER H=0.51 VR4=0.97, SOL H=0.48 VR4=1.02, TRUMP H=0.50 VR4=1.08, USELESS H=0.45 VR4=0.95, W H=0.45 VR4=0.92, WIF H=0.47 VR4=0.95

## Whole grid (288 variants: tf x L 20/50 x z 2/2.5 x N(4) x stop z<=-4 / -5% x regime off / SOL>4h EMA50 / 4h EMA50 slope up), all signals, night window 20:00-08:00 Dublin

| tf | cost | variants | median IS mean/trade | median OOS mean/trade | variants OOS>0 | variants IS>0 & OOS>0 | best OOS (any, look-ahead pick!) | median 24h OOS mean |
|---|---|---|---|---|---|---|---|---|
| 1h | lo | 96 | -0.09% | -0.20% | 30 | 17 | +0.31% | -0.13% |
| 1h | hi | 96 | -0.39% | -0.51% | 2 | 0 | +0.00% | -0.44% |
| 15m | lo | 96 | -0.13% | -0.32% | 6 | 2 | +0.28% | -0.38% |
| 15m | hi | 96 | -0.43% | -0.63% | 0 | 0 | -0.02% | -0.69% |
| 5m | lo | 96 | -0.23% | -0.25% | 0 | 0 | -0.13% | -0.28% |
| 5m | hi | 96 | -0.54% | -0.55% | 0 | 0 | -0.43% | -0.59% |

Regime filter effect (median over variants, hi cost, night window):

| tf | regime | median IS | median OOS | median IS trades |
|---|---|---|---|---|
| 1h | off | -0.28% | -0.17% | 700 |
| 1h | ema50 | -0.60% | -0.57% | 162 |
| 1h | slope | -0.51% | -0.57% | 215 |
| 15m | off | -0.40% | -0.50% | 592 |
| 15m | ema50 | -0.41% | -0.66% | 370 |
| 15m | slope | -0.46% | -0.66% | 389 |
| 5m | off | -0.53% | -0.55% | 1473 |
| 5m | ema50 | -0.53% | -0.56% | 974 |
| 5m | slope | -0.55% | -0.55% | 984 |

Gross (before any fee) median OOS mean per trade ~ lo-cost median + 0.30 pts: 1h +0.10%, 15m -0.02%, 5m +0.05%.

## Best variant per family (selected on IN-SAMPLE hi-cost mean per trade, night window, >= 50 IS trades), then held out

### 1h: `MR_dip_1h_L50_z2.5_N16_z4_off`

Entry z <= -2.5 vs 50-bar mean (next open); exit at z >= 0 or after 16 bars (next open), stop z <= -4; regime off. Neighbours (one parameter away, IS hi-cost mean): -0.25%, -0.21%, -0.14%, -0.02%, -0.27%, -0.38% -> lucky_number = n/a (not profitable IS).

| cost | sample | IS trades | IS mean [95% CI] | OOS trades | OOS mean [95% CI] | OOS win | 24h all-signals IS / OOS mean |
|---|---|---|---|---|---|---|---|
| lo | all signals (night) | 440 | +0.29% [+0.01%, +0.58%] | 272 | +0.31% [-0.05%, +0.68%] | +58% | -0.01% / +0.02% |
| lo | book max 3, 10% | 219 | +0.13% [-0.27%, +0.51%] | 136 | -0.14% [-0.74%, +0.36%] | +57% | |
| hi | all signals (night) | 440 | -0.02% [-0.29%, +0.27%] | 272 | +0.00% [-0.38%, +0.37%] | +52% | -0.31% / -0.28% |
| hi | book max 3, 10% | 219 | -0.17% [-0.57%, +0.22%] | 136 | -0.44% [-1.00%, +0.08%] | +50% | |

Nightly book return (10%/trade, max 3 open, % of wallet), hi cost:

| window | period | nights/days | mean | p5 | median | p95 | best | worst | share > 0 | nights with trades (share > 0 of those) | P(>= +10%) | P(<= -20%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| night 20-08 | IS | 257 | -0.014% | -0.49% | +0.00% | +0.46% | +1.71% | -2.71% | 17% | 99 (43%) | 0.0% | 0.0% |
| night 20-08 | OOS | 110 | -0.055% | -0.85% | +0.00% | +0.46% | +1.47% | -2.68% | 27% | 58 (52%) | 0.0% | 0.0% |
| 24h | IS | 256 | -0.062% | -1.32% | +0.00% | +0.98% | +2.06% | -3.65% | 27% | 141 (48%) | 0.0% | 0.0% |
| 24h | OOS | 111 | -0.076% | -1.43% | +0.00% | +0.77% | +1.30% | -2.79% | 32% | 66 (53%) | 0.0% | 0.0% |

Score (hi cost, night book): 14/25 (oos_risk 1, drawdown 4, trades 5, edge 2, stability 2); MC p95 DD +14.6% of wallet; holds OOS: no; candidate: no. Net ex best trade -10.55% of wallet.

Exit mix (all signals, hi): {'eod': 606, 'mean': 65, 'zstop': 41}.

### 15m: `MR_dip_15m_L50_z2.0_N32_z4_ema50`

Entry z <= -2.0 vs 50-bar mean (next open); exit at z >= 0 or after 32 bars (next open), stop z <= -4; regime ema50. Neighbours (one parameter away, IS hi-cost mean): -0.33%, -0.32%, -0.34%, -0.30%, -0.28%, -0.36% -> lucky_number = n/a (not profitable IS).

| cost | sample | IS trades | IS mean [95% CI] | OOS trades | OOS mean [95% CI] | OOS win | 24h all-signals IS / OOS mean |
|---|---|---|---|---|---|---|---|
| lo | all signals (night) | 385 | +0.04% [-0.16%, +0.24%] | 133 | -0.34% [-0.77%, +0.08%] | +47% | +0.06% / -0.24% |
| lo | book max 3, 10% | 180 | -0.07% [-0.39%, +0.25%] | 47 | -0.50% [-1.19%, +0.16%] | +47% | |
| hi | all signals (night) | 385 | -0.27% [-0.46%, -0.06%] | 133 | -0.65% [-1.08%, -0.23%] | +42% | -0.25% / -0.55% |
| hi | book max 3, 10% | 180 | -0.37% [-0.69%, -0.05%] | 47 | -0.80% [-1.53%, -0.14%] | +40% | |

Nightly book return (10%/trade, max 3 open, % of wallet), hi cost:

| window | period | nights/days | mean | p5 | median | p95 | best | worst | share > 0 | nights with trades (share > 0 of those) | P(>= +10%) | P(<= -20%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| night 20-08 | IS | 68 | -0.099% | -0.87% | +0.00% | +0.72% | +1.31% | -1.82% | 25% | 48 (35%) | 0.0% | 0.0% |
| night 20-08 | OOS | 29 | -0.129% | -1.12% | +0.00% | +0.36% | +0.58% | -1.28% | 21% | 12 (50%) | 0.0% | 0.0% |
| 24h | IS | 69 | -0.103% | -1.10% | +0.00% | +0.73% | +2.68% | -1.64% | 35% | 52 (46%) | 0.0% | 0.0% |
| 24h | OOS | 29 | -0.108% | -1.12% | +0.00% | +0.76% | +0.92% | -2.49% | 21% | 14 (43%) | 0.0% | 0.0% |

Score (hi cost, night book): 14/25 (oos_risk 1, drawdown 4, trades 5, edge 2, stability 2); MC p95 DD +12.4% of wallet; holds OOS: no; candidate: no. Net ex best trade -11.44% of wallet.

Exit mix (all signals, hi): {'eod': 206, 'mean': 193, 'time': 93, 'zstop': 26}.

### 5m: `MR_dip_5m_L50_z2.0_N48_z4_ema50`

Entry z <= -2.0 vs 50-bar mean (next open); exit at z >= 0 or after 48 bars (next open), stop z <= -4; regime ema50. Neighbours (one parameter away, IS hi-cost mean): -0.47%, -0.45%, -0.48%, -0.49%, -0.43%, -0.47% -> lucky_number = n/a (not profitable IS).

| cost | sample | IS trades | IS mean [95% CI] | OOS trades | OOS mean [95% CI] | OOS win | 24h all-signals IS / OOS mean |
|---|---|---|---|---|---|---|---|
| lo | all signals (night) | 1021 | -0.13% [-0.22%, -0.03%] | 356 | -0.24% [-0.44%, -0.07%] | +59% | -0.00% / -0.24% |
| lo | book max 3, 10% | 411 | -0.01% [-0.16%, +0.14%] | 115 | -0.30% [-0.58%, -0.02%] | +51% | |
| hi | all signals (night) | 1021 | -0.43% [-0.52%, -0.33%] | 356 | -0.55% [-0.73%, -0.38%] | +46% | -0.30% / -0.55% |
| hi | book max 3, 10% | 411 | -0.32% [-0.46%, -0.17%] | 115 | -0.60% [-0.88%, -0.32%] | +35% | |

Nightly book return (10%/trade, max 3 open, % of wallet), hi cost:

| window | period | nights/days | mean | p5 | median | p95 | best | worst | share > 0 | nights with trades (share > 0 of those) | P(>= +10%) | P(<= -20%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| night 20-08 | IS | 69 | -0.189% | -1.04% | -0.03% | +0.51% | +1.68% | -2.03% | 19% | 51 (25%) | 0.0% | 0.0% |
| night 20-08 | OOS | 29 | -0.237% | -1.13% | +0.00% | +0.04% | +0.33% | -2.06% | 7% | 13 (15%) | 0.0% | 0.0% |
| 24h | IS | 69 | -0.332% | -1.52% | -0.19% | +0.95% | +2.33% | -3.24% | 26% | 56 (32%) | 0.0% | 0.0% |
| 24h | OOS | 29 | -0.404% | -1.72% | +0.00% | +0.02% | +0.29% | -1.78% | 7% | 15 (13%) | 0.0% | 0.0% |

Score (hi cost, night book): 12/25 (oos_risk 1, drawdown 3, trades 5, edge 2, stability 1); MC p95 DD +21.0% of wallet; holds OOS: no; candidate: no. Net ex best trade -20.43% of wallet.

Exit mix (all signals, hi): {'mean': 1004, 'time': 181, 'eod': 129, 'zstop': 63}.

## Benchmark: buy-and-hold SOL

| window | SOL B&H | SOL 20:00-08:00 only (100% exposure), mean/night | same at 30% exposure (3 x 10%), P(+10%) / P(-20%) |
|---|---|---|---|
| 1h window IS (2025-10-24..2026-07-06) | -58.2% | +0.008% | 0.0% / 0.0% |
| 1h window OOS (2026-07-06..2026-10-23) | +27.9% | +0.118% | 0.0% / 0.0% |
| 15m window IS (2026-07-24..2026-09-26) | +58.2% | +0.239% | 0.0% / 0.0% |
| 15m window OOS (2026-09-26..2026-10-23) | -14.3% | +0.071% | 0.0% / 0.0% |
| 5m window IS (2026-07-24..2026-09-26) | +58.2% | +0.239% | 0.0% / 0.0% |
| 5m window OOS (2026-09-26..2026-10-23) | -14.3% | +0.071% | 0.0% / 0.0% |

## WHY THIS COULD FAIL / who is on the other side

- The other side of a dip buy on SOL/JUP/WIF 5m-1h bars is CEX market makers and perp-funded momentum/liquidation flow: dips in these tokens are mostly information (BTC/SOL beta moves, unlocks, news) or forced liquidations that keep going. MMs already harvest the sub-minute bounce; what is left at 5m+ is closer to a random walk (H ~ 0.5, VR ~ 1) and fees eat it.
- Survivorship (today's top 20) inflates every dip-buy number. Binance prices are a proxy for on-chain fills (Jupiter routes on thinner pools for GT tokens; MEW/USELESS/GRASS/POPCAT depth is a few $M).
- Multiple testing: 288 configs in this study (plus every variant ever tried in the Lab registry); the IS winner is expected to look good by luck. Held-out results are the only ones that count.
- Regime shifts: a 2-month OOS that was a SOL down/up-trend changes everything; long-only dip buying is short volatility and loses big in trending sell-offs (stop exits cluster on the same nights across tokens since they all carry SOL beta, so 3 open positions are not 3 independent bets).

## Not done / data-pending
- Pairs (WIF/BONK, JUP/RAY, SOL/JTO, Kalman/rolling OLS, long-short and long-laggard): dropped from this task, Lab 2 owns it. No pairs code exists in /workspace/lab.
- 5m/15m history is ~3 months (OOS ~4 weeks); 1h is 12 months (6 for GT tokens). On-chain fill check vs Binance not done.

