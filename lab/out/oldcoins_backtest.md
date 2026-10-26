# Older-coins breakout backtest: Chunk's live rules (OC_live) + in-sample tuning (2026-10-23T23:43:53+00:00, PAPER ONLY, research only)

Universe: 23 Solana tokens with >= 260 1h bars after exclusions (stables/LSTs/wrapped, tokenized stocks, avoid.csv); 20 were point-in-time eligible (age >= 7 d, mcap $5-200M, liq >= $500k) for at least one hour of the last 60 days; 19 of those also have 15m candles. vol24 >= $1M is applied at the signal bar.

## 1. Live rule (OC_live) backtest

Rules as coded in /workspace/runner-radar/oldcoins.py plus Zero's 23:39 update: stop = breakout-bar low clamped to 2.5%-8% below entry (1h) / 2.5%-6% (15m). Activity filter = the live spec in oldcoins.py (23:40 version; trades-log.md itself states no threshold): $ volume of the last 4 closed candles >= $150k on 1h / >= $40k on 15m, plus the universe thin-activity skip (liq/mcap > 0.4 AND vol24/liq < 0.05). Activity thresholds {0, 75k, 150k, 300k, 600k} (1h) and {0, 20k, 40k, 80k, 160k} (15m) are in the sweep. Entries 21:00-07:30 Dublin at the next bar open, flat 07:45 Dublin (1h: mid of the 07:00 bar; 15m: close of the 07:30 bar). 10% of book per trade, max 3 open, one position per token, 1h and 15m books run separately and combined.

Costs per side: c0.3 / c0.5 = flat bands; real_P0.0001 / real_P0.0005 = pool fee from the Jupiter-quote fit (max(0.25%, (1.85% - 1.78% x log10(liq/$100k))/2); ~0.3%/side at $500k) + 2 x size/liq + (priority + 0.000005 SOL) x SOL price / ticket, ticket = 10% x 0.928 SOL (~$9-11); chunk_1pct = Chunk's own model (1% + 2 x size/liq). The priority fee is the biggest real cost at a ~$10 ticket: 0.0005 SOL is ~0.55%/side. /workspace/selfcopy/quotes.jsonl does not exist, so the quotes are Lab's own 24 read-only Jupiter quotes (data/fs_quotes/quotes.jsonl).

| book | cost | days (IS/OOS) | trades (IS/OOS) | mean ret/trade | median | win | 95% CI mean | book P&L per night IS | per night OOS | total book |
|---|---|---|---|---|---|---|---|---|---|---|
| 1h | c0.3 | 61 (42/19) | 30 (25/5) | -0.08% | +0.12% | 57% | [-1.10%, +0.95%] | +0.023% | -0.063% | -0.23% |
| 1h | c0.5 | 61 (42/19) | 30 (25/5) | -0.48% | -0.28% | 40% | [-1.49%, +0.54%] | -0.001% | -0.074% | -1.43% |
| 1h | real_P0.0001 | 61 (42/19) | 30 (25/5) | -0.20% | -0.01% | 50% | [-1.22%, +0.82%] | +0.016% | -0.067% | -0.61% |
| 1h | real_P0.0005 (main) | 61 (42/19) | 30 (25/5) | -1.06% | -0.86% | 30% | [-2.07%, -0.05%] | -0.036% | -0.089% | -3.18% |
| 1h | chunk_1pct | 61 (42/19) | 30 (25/5) | -1.47% | -1.27% | 30% | [-2.47%, -0.46%] | -0.060% | -0.099% | -4.40% |
| 15m | c0.3 | 42 (29/13) | 39 (33/6) | +0.31% | -3.08% | 36% | [-1.08%, +1.84%] | +0.055% | -0.028% | +1.22% |
| 15m | c0.5 | 42 (29/13) | 39 (33/6) | -0.09% | -3.47% | 36% | [-1.47%, +1.43%] | +0.009% | -0.046% | -0.34% |
| 15m | real_P0.0001 | 42 (29/13) | 39 (33/6) | +0.19% | -3.21% | 36% | [-1.21%, +1.71%] | +0.040% | -0.033% | +0.73% |
| 15m | real_P0.0005 (main) | 42 (29/13) | 39 (33/6) | -0.67% | -4.04% | 31% | [-2.05%, +0.84%] | -0.058% | -0.073% | -2.63% |
| 15m | chunk_1pct | 42 (29/13) | 39 (33/6) | -1.08% | -4.43% | 31% | [-2.46%, +0.42%] | -0.104% | -0.091% | -4.22% |
- 1h live exits: {'eod': 25, 'stop': 5}; tokens traded 7, most-traded [('ANTFUN', 12), ('CARDS', 6), ('BOME', 4)]; best 3 trades +6.8%, +3.1%, +1.6%; without the best trade: total -3.86% of book; median cost/side +0.79%.
  METHOD score 13/25 (oos 1, dd 5, n 3, edge 2, stab 2); MC drawdown p50/p95 3.5% / 4.2% of book; activity filter off changes trades 30 -> 30.
- 15m live exits: {'eod': 18, 'stop': 19, 'trail': 2}; tokens traded 6, most-traded [('CARDS', 14), ('BOME', 8), ('ANTFUN', 6)]; best 3 trades +11.4%, +10.6%, +9.7%; without the best trade: total -3.77% of book; median cost/side +0.79%.
  METHOD score 13/25 (oos 1, dd 5, n 3, edge 2, stab 2); MC drawdown p50/p95 4.2% / 5.8% of book; activity filter off changes trades 39 -> 41.
- Combined 1h+15m live book on the 15m window (42 nights, shared max 3): 40 trades, mean -0.65%/trade, total -2.58% of book.

## 2. Nightly return distribution at 10% per trade (night = 20:00-08:00 Dublin; entries 21:00-07:30, flat 07:45)

Unit = one night of the whole book (sum of 10% x trade return of every trade entered that night; nights with no trade = 0). Block bootstrap: 5,000 resamples of the actual nights in blocks of 3 consecutive nights (a night is resampled whole, so coins that move together on a night stay together). CI = 2.5-97.5% across resamples. 30-night = compounded 30 nights drawn the same way.

| book | cost | nights | trades/night | nights with 0 trades | median night | p10 | p90 | mean night [95% CI] | P(night >= +10%) [CI] | P(night <= -20%) [CI] | worst / best night | 30 nights median (p10, p90) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1h | c0.3 | 61 | 0.49 | 61% | +0.00% | -0.12% | +0.22% | -0.004% [-0.045%, +0.037%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -0.64% / +0.42% | -0.1% (-1.2%, +0.9%) |
| 1h | c0.5 | 61 | 0.49 | 61% | +0.00% | -0.15% | +0.16% | -0.023% [-0.065%, +0.017%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -0.68% / +0.38% | -0.7% (-1.8%, +0.4%) |
| 1h | real_P0.0005 | 61 | 0.49 | 61% | +0.00% | -0.21% | +0.07% | -0.052% [-0.097%, -0.011%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -0.74% / +0.31% | -1.5% (-2.7%, -0.4%) |
| 15m | c0.3 | 42 | 0.93 | 45% | +0.00% | -0.32% | +0.44% | +0.029% [-0.066%, +0.123%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -1.02% / +1.25% | +0.9% (-1.3%, +3.1%) |
| 15m | c0.5 | 42 | 0.93 | 45% | +0.00% | -0.39% | +0.32% | -0.008% [-0.108%, +0.082%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -1.13% / +1.20% | -0.2% (-2.4%, +1.9%) |
| 15m | real_P0.0005 | 42 | 0.93 | 45% | +0.00% | -0.45% | +0.17% | -0.063% [-0.171%, +0.028%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -1.30% / +1.14% | -1.7% (-4.2%, +0.3%) |
| 1h+15m | real_P0.0005 | 42 | 0.95 | 43% | +0.00% | -0.60% | +0.31% | -0.061% [-0.181%, +0.043%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | -1.30% / +1.14% | -1.8% (-4.4%, +0.7%) |

Arithmetic of the cap: with 10% per trade and max 3 open, a +10% night needs the open trades to average about +33% (3 trades) or +100% (1 trade) in one night; a -20% night needs ~-67% on 3 trades at once, which a 2.5-8% stop only allows through a gap/rug past the stop. The 1h rule fires well under once a night on this universe, so most nights are flat.

## 3. In-sample tuning vs the live rule

Tuned on in-sample nights only (first 70% of nights per timeframe), cost real_P0.0005. Grid per timeframe: stop clamp low {1.5, 2.5, 4%} x clamp high (1h {5, 8, 12%}; 15m {4, 6, 9%}) x TP-half {+5, +10, +15, +25%, none} x volume multiple {>0, >1, >1.5, >2, >3 x prior-20 mean} x activity {0, 50, 75, 90%} x entry hours {live window, all hours, 18-24, 00-06, 06-12, 12-18 UTC} = 5,400 configs. Book is still flat at 07:45 Dublin in every config. Selection: max (IS mean book P&L per night - 1 s.e.), >= 30 IS trades (1h) / >= 20 (15m), not a lucky number (every one-step neighbour also IS-profitable with >= 5 trades). Improvement only if the paired OOS night difference (tuned - live) has a block-bootstrap 95% CI above 0.

| tf | config | IS trades | IS per night | OOS trades | OOS per night | OOS mean ret/trade | OOS diff vs live per night [95% CI] | verdict | lucky? | live rule's IS rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 1h | OC_live: 1h_sl2.5-8_tp15_v1_a150k_live | 25 | -0.036% | 5 | -0.089% | -3.37% | - |  | no | 2684/6750 |
| 1h | best tuned: 1h_sl1.5-5_tp25_v1_a0k_06-12UTC | 30 | -0.008% | 3 | -0.076% | -4.82% | +0.013% [-0.094%, +0.116%] | does NOT clearly beat live OOS | no | 1/6750 |
| 15m | OC_live: 15m_sl2.5-6_tp10_v1_a40k_live | 33 | -0.058% | 6 | -0.073% | -1.58% | - |  | no | 4797/6750 |
| 15m | best tuned: 15m_sl4-4_tp25_v2_a40k_live | 23 | +0.169% | 4 | -0.016% | -0.52% | +0.057% [+0.000%, +0.147%] | does NOT clearly beat live OOS | no | 1/6750 |

Multiple testing: 13500 configs were scored in-sample; the best IS number is biased up by selection. Treat the tuned rows as hypotheses for forward paper only.

Neighbour sweep, 1h OC_live (1h_sl2.5-8_tp15_v1_a150k_live), one step per dimension (includes stop clamp low/high and activity threshold):

| changed | value | IS trades | IS per night | OOS trades | OOS per night |
|---|---|---|---|---|---|
| stop_lo | 0.015 | 26 | -0.057% | 5 | -0.089% |
| stop_lo | 0.04 | 25 | -0.040% | 5 | -0.089% |
| stop_hi | 0.05 | 25 | -0.047% | 5 | -0.084% |
| stop_hi | 0.12 | 25 | -0.036% | 5 | -0.089% |
| tp | 0.1 | 25 | -0.030% | 5 | -0.089% |
| tp | 0.25 | 25 | -0.036% | 5 | -0.089% |
| vth | 0.0 | 28 | -0.041% | 5 | -0.089% |
| vth | 1.5 | 21 | -0.047% | 5 | -0.089% |
| act | 75000.0 | 25 | -0.036% | 5 | -0.089% |
| act | 300000.0 | 24 | -0.039% | 4 | -0.081% |
| hours | all | 54 | -0.083% | 12 | -0.259% |

Neighbour sweep, 1h best tuned (1h_sl1.5-5_tp25_v1_a0k_06-12UTC), one step per dimension (includes stop clamp low/high and activity threshold):

| changed | value | IS trades | IS per night | OOS trades | OOS per night |
|---|---|---|---|---|---|
| stop_lo | 0.025 | 30 | -0.011% | 3 | -0.076% |
| stop_hi | 0.08 | 30 | -0.008% | 3 | -0.076% |
| tp | 0.15 | 30 | -0.017% | 3 | -0.076% |
| tp | None | 30 | -0.037% | 3 | -0.076% |
| vth | 0.0 | 32 | -0.017% | 3 | -0.076% |
| vth | 1.5 | 27 | -0.054% | 2 | -0.053% |
| act | 75000.0 | 30 | -0.008% | 3 | -0.076% |
| hours | (0, 6) | 20 | -0.031% | 5 | -0.101% |
| hours | (12, 18) | 24 | -0.072% | 3 | -0.052% |

Neighbour sweep, 15m OC_live (15m_sl2.5-6_tp10_v1_a40k_live), one step per dimension (includes stop clamp low/high and activity threshold):

| changed | value | IS trades | IS per night | OOS trades | OOS per night |
|---|---|---|---|---|---|
| stop_lo | 0.015 | 37 | -0.103% | 6 | -0.062% |
| stop_lo | 0.04 | 30 | +0.014% | 5 | -0.059% |
| stop_hi | 0.04 | 33 | -0.058% | 6 | -0.073% |
| stop_hi | 0.09 | 33 | -0.058% | 6 | -0.073% |
| tp | 0.05 | 34 | -0.108% | 6 | -0.074% |
| tp | 0.15 | 32 | -0.021% | 6 | -0.073% |
| vth | 0.0 | 34 | -0.069% | 6 | -0.073% |
| vth | 1.5 | 28 | +0.006% | 6 | -0.073% |
| act | 20000.0 | 35 | -0.074% | 6 | -0.041% |
| act | 80000.0 | 32 | -0.065% | 6 | -0.133% |
| hours | all | 49 | -0.078% | 11 | -0.145% |

Neighbour sweep, 15m best tuned (15m_sl4-4_tp25_v2_a40k_live), one step per dimension (includes stop clamp low/high and activity threshold):

| changed | value | IS trades | IS per night | OOS trades | OOS per night |
|---|---|---|---|---|---|
| stop_lo | 0.025 | 24 | +0.092% | 5 | -0.038% |
| stop_hi | 0.06 | 23 | +0.169% | 4 | -0.016% |
| tp | 0.15 | 23 | +0.146% | 4 | -0.016% |
| tp | None | 23 | +0.133% | 4 | -0.016% |
| vth | 1.5 | 25 | +0.146% | 5 | -0.059% |
| vth | 3.0 | 19 | +0.157% | 3 | +0.012% |
| act | 20000.0 | 25 | +0.153% | 4 | +0.009% |
| act | 80000.0 | 22 | +0.158% | 4 | -0.055% |
| hours | all | 40 | +0.067% | 6 | -0.017% |

Benchmarks (1h window): SOL buy-and-hold IS +24.45%, OOS -15.14%; equal-weight buy-and-hold of tokens eligible at the window start: IS +20.94%, OOS -5.91% (book uses <= 30% of capital, so compare x0.3).

## WHY THIS COULD FAIL

- Universe is discovered from pools that are big NOW (GeckoTerminal top pools + DexScreener); tokens that were $5-200M earlier and since died are under-represented (survivorship, flatters any long rule).
- Point-in-time mcap = today's supply x past price; point-in-time liquidity = today's liquidity scaled by sqrt(price) (no LP history). Both are approximations.
- Trade counts are small (tens, not hundreds); every CI above is wide and the OOS window is ~2-3 weeks of one market regime.
- Live 1h trades use the most recent bars from a fresh fetch (and size 5%, not 10%); fills are next-bar-open, while live enters at the live price a few minutes after the close.
- GeckoTerminal omits no-trade bars; thin pools give stale highs/lows. 15m history is limited for thin pools (~20 days).
- Costs: priority fee dominates at a ~$10 ticket; failed transactions, MEV sandwiching on a 15% slippage setting, and Banana Gun's own fee (not in Chunk's model) would add more.

Who is on the other side: breakout buyers on 1h/15m charts are the most crowded retail signal in memecoins; the sellers are holders and market-makers distributing into the volume spike, plus bots that fade breakouts on thin books. A rule this public has no structural edge unless the costs are tiny.

## Data notes

- The brief says Chunk trades these rules LIVE at 10% on 1h and 15m. The files say otherwise: oldcoins.py logs 'PAPER scanner output; this script never trades', size_pct = 5% (0.0464 SOL), trades-log.md shows live buys PAUSED (paper only) and the oldcoins book's first scan at 00:36 Dublin with one 15m paper entry (ANTFUN). This backtest uses 10% as asked.
- oldcoins-paper.jsonl has 1 setup + 1 entry so far: too little to compare with the backtest.

