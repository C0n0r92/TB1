# Copy replay, 30 days — OLD vs NEW rules at real self-copy costs (PAPER ONLY)

_Generated 2026-10-24 01:11 UTC by cr_replay.py / cr_report.py. Paper/backtest only; nothing was traded._

## Verdict

- _benjitrades OLD $5: EV +0.13/trade on n=17, CI [-0.79, +1.23], OOS n=2 net +1.15, score 15/25 — CI includes 0, not a demonstrated edge
- _benjitrades OLD $10: EV +0.29/trade on n=17, CI [-1.55, +2.50], OOS n=2 net +2.35, score 14/25 — CI includes 0, not a demonstrated edge
- _benjitrades NEW $5: EV +0.67/trade on n=4, CI [-0.88, +3.35], OOS n=0 net +0.00, score 12/25 — CI includes 0, not a demonstrated edge
- _benjitrades NEW $10: EV +1.36/trade on n=4, CI [-1.74, +6.73], OOS n=0 net +0.00, score 12/25 — CI includes 0, not a demonstrated edge
- bystevenr NEW $5: EV +1.59/trade on n=2, CI [+1.07, +2.11], OOS n=1 net +2.11, score 13/25
- bystevenr NEW $10: EV +3.20/trade on n=2, CI [+2.15, +4.25], OOS n=1 net +4.25, score 13/25
- ExactTallTakin OLD $5: EV +0.68/trade on n=31, CI [-0.75, +3.15], OOS n=4 net -2.76, score 14/25 — CI includes 0, not a demonstrated edge
- ExactTallTakin OLD $10: EV +1.38/trade on n=31, CI [-1.47, +6.33], OOS n=4 net -5.43, score 12/25 — CI includes 0, not a demonstrated edge

## Headline: self-copy, prio 0.0001 SOL (live HARD cap), 5 s delay

| leader | rules | size | trades | EV $/trade | EV % | median $ | total $ | ex-best $ | 95% CI mean $ | win | held-out n / net $ / EV $ | MC DD p95 ($100) | score /25 | exits (stop/trail/tp-half/mirror/flat) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | OLD | $5 | 17 | +0.13 | +2.6% | -1.17 | +2.20 | -3.29 | [-0.79, +1.23] | 29.4% | 2 / +1.15 / +0.58 | 10.3% | 15 | 7/0/2/9/1 |
| _benjitrades | OLD | $10 | 17 | +0.29 | +2.9% | -2.31 | +4.91 | -6.12 | [-1.55, +2.50] | 29.4% | 2 / +2.35 / +1.18 | 20.3% | 14 | 7/0/2/9/1 |
| _benjitrades | OLD | $13 (not allowed live) | 17 | +0.38 | +3.0% | -2.99 | +6.53 | -7.82 | [-2.01, +3.25] | 29.4% | 2 / +3.07 / +1.54 | 26.4% | 14 | 7/0/2/9/1 |
| _benjitrades | NEW | $5 | 4 | +0.67 | +13.3% | -0.48 | +2.66 | -1.83 | [-0.88, +3.35] | 25.0% | 0 / +0.00 / – | 1.8% | 12 | 2/0/0/2/0 |
| _benjitrades | NEW | $10 | 4 | +1.36 | +13.6% | -0.93 | +5.43 | -3.59 | [-1.74, +6.73] | 25.0% | 0 / +0.00 / – | 3.6% | 12 | 2/0/0/2/0 |
| _benjitrades | NEW | $13 (not allowed live) | 4 | +1.77 | +13.6% | -1.20 | +7.08 | -4.64 | [-2.25, +8.76] | 25.0% | 0 / +0.00 / – | 4.6% | 12 | 2/0/0/2/0 |
| bystevenr | OLD | $5 | 4 | -0.56 | -11.2% | -0.96 | -2.23 | -3.30 | [-1.37, +0.46] | 25.0% | 2 / -1.93 / -0.96 | 3.3% | 9 | 2/0/0/0/2 |
| bystevenr | OLD | $10 | 4 | -1.09 | -10.9% | -1.91 | -4.37 | -6.53 | [-2.71, +0.94] | 25.0% | 2 / -3.81 / -1.91 | 6.5% | 9 | 2/0/0/0/2 |
| bystevenr | OLD | $13 (not allowed live) | 4 | -1.41 | -10.9% | -2.47 | -5.66 | -8.46 | [-3.52, +1.23] | 25.0% | 2 / -4.95 / -2.47 | 8.5% | 9 | 2/0/0/0/2 |
| bystevenr | NEW | $5 | 2 | +1.59 | +31.7% | +1.59 | +3.17 | +1.07 | [+1.07, +2.11] | 100.0% | 1 / +2.11 / +2.11 | 0.0% | 13 | 0/1/1/0/1 |
| bystevenr | NEW | $10 | 2 | +3.20 | +32.0% | +3.20 | +6.40 | +2.15 | [+2.15, +4.25] | 100.0% | 1 / +4.25 / +4.25 | 0.0% | 13 | 0/1/1/0/1 |
| bystevenr | NEW | $13 (not allowed live) | 2 | +4.17 | +32.1% | +4.17 | +8.34 | +2.81 | [+2.81, +5.53] | 100.0% | 1 / +5.53 / +5.53 | 0.0% | 13 | 0/1/1/0/1 |
| pointfarmcap | OLD | $5 | 1 | -1.08 | -21.7% | -1.08 | -1.08 | +0.00 | [-1.08, -1.08] | 0.0% | 1 / -1.08 / -1.08 | 1.1% | 9 | 1/0/0/0/0 |
| pointfarmcap | OLD | $10 | 1 | -2.12 | -21.2% | -2.12 | -2.12 | +0.00 | [-2.12, -2.12] | 0.0% | 1 / -2.12 / -2.12 | 2.1% | 9 | 1/0/0/0/0 |
| pointfarmcap | OLD | $13 (not allowed live) | 1 | -2.74 | -21.0% | -2.74 | -2.74 | +0.00 | [-2.74, -2.74] | 0.0% | 1 / -2.74 / -2.74 | 2.7% | 9 | 1/0/0/0/0 |
| pointfarmcap | NEW | $5 | 0 | – | – | – | +0.00 | +0.00 | – | – | 0 / +0.00 / – | – | 5 | 0/0/0/0/0 |
| pointfarmcap | NEW | $10 | 0 | – | – | – | +0.00 | +0.00 | – | – | 0 / +0.00 / – | – | 5 | 0/0/0/0/0 |
| pointfarmcap | NEW | $13 (not allowed live) | 0 | – | – | – | +0.00 | +0.00 | – | – | 0 / +0.00 / – | – | 5 | 0/0/0/0/0 |
| ExactTallTakin | OLD | $5 | 31 | +0.68 | +13.6% | -0.25 | +21.08 | -12.77 | [-0.75, +3.15] | 32.3% | 4 / -2.76 / -0.69 | 15.7% | 14 | 9/0/0/21/1 |
| ExactTallTakin | OLD | $10 | 31 | +1.38 | +13.8% | -0.47 | +42.91 | -24.81 | [-1.47, +6.33] | 32.3% | 4 / -5.43 / -1.36 | 30.7% | 12 | 9/0/0/21/1 |
| ExactTallTakin | OLD | $13 (not allowed live) | 31 | +1.81 | +13.9% | -0.61 | +56.01 | -32.04 | [-1.90, +8.24] | 32.3% | 4 / -7.03 / -1.76 | 39.8% | 12 | 9/0/0/21/1 |
| ExactTallTakin | NEW | $5 | 5 | -0.59 | -11.8% | -0.88 | -2.95 | -2.80 | [-0.88, -0.30] | 0.0% | 0 / +0.00 / – | 3.0% | 9 | 3/0/0/2/0 |
| ExactTallTakin | NEW | $10 | 5 | -1.16 | -11.6% | -1.74 | -5.79 | -5.50 | [-1.74, -0.57] | 0.0% | 0 / +0.00 / – | 5.8% | 9 | 3/0/0/2/0 |
| ExactTallTakin | NEW | $13 (not allowed live) | 5 | -1.50 | -11.5% | -2.25 | -7.48 | -7.13 | [-2.25, -0.74] | 0.0% | 0 / +0.00 / – | 7.5% | 9 | 3/0/0/2/0 |
| ALL | OLD | $5 | 53 | +0.38 | +7.5% | -0.56 | +19.96 | -13.89 | [-0.58, +1.91] | 30.2% | 9 / -4.62 / -0.51 | 22.5% | 13 | 19/0/2/30/4 |
| ALL | OLD | $10 | 53 | +0.78 | +7.8% | -1.11 | +41.33 | -26.40 | [-1.13, +3.85] | 30.2% | 9 / -9.01 / -1.00 | 44.0% | 12 | 19/0/2/30/4 |
| ALL | OLD | $13 (not allowed live) | 53 | +1.02 | +7.9% | -1.43 | +54.14 | -33.90 | [-1.46, +5.02] | 30.2% | 9 / -11.64 / -1.29 | 57.0% | 11 | 19/0/2/30/4 |
| ALL | NEW | $5 | 11 | +0.26 | +5.2% | -0.16 | +2.88 | -1.62 | [-0.59, +1.35] | 27.3% | 1 / +2.11 / +2.11 | 4.6% | 13 | 5/1/1/4/1 |
| ALL | NEW | $10 | 11 | +0.55 | +5.5% | -0.29 | +6.04 | -2.98 | [-1.16, +2.73] | 27.3% | 1 / +4.25 / +4.25 | 9.1% | 13 | 5/1/1/4/1 |
| ALL | NEW | $13 (not allowed live) | 11 | +0.72 | +5.5% | -0.37 | +7.94 | -3.79 | [-1.50, +3.55] | 27.3% | 1 / +5.53 / +5.53 | 11.8% | 12 | 5/1/1/4/1 |

## Copyfomo (≈5.3% round trip + pool impact, $0.015/tx, 5 s) side by side with self-copy

| leader | rules | size | n | self EV $ | copyfomo EV $ | self total $ | copyfomo total $ | self avg cost RT | copyfomo avg cost RT |
|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | OLD | $5 | 17/17 | +0.13 | -0.03 | +2.20 | -0.44 | 2.7% | 7.6% |
| _benjitrades | OLD | $10 | 17/17 | +0.29 | -0.02 | +4.91 | -0.26 | 2.4% | 7.2% |
| _benjitrades | OLD | $13 | 17/17 | +0.38 | -0.01 | +6.53 | -0.15 | 2.3% | 7.1% |
| _benjitrades | NEW | $5 | 4/4 | +0.67 | +0.35 | +2.66 | +1.38 | 1.8% | 6.7% |
| _benjitrades | NEW | $10 | 4/4 | +1.36 | +0.72 | +5.43 | +2.89 | 1.6% | 6.4% |
| _benjitrades | NEW | $13 | 4/4 | +1.77 | +0.95 | +7.08 | +3.79 | 1.5% | 6.4% |
| bystevenr | OLD | $5 | 4/4 | -0.56 | -0.69 | -2.23 | -2.76 | 2.2% | 7.1% |
| bystevenr | OLD | $10 | 4/4 | -1.09 | -1.35 | -4.37 | -5.39 | 2.0% | 6.8% |
| bystevenr | OLD | $13 | 4/4 | -1.41 | -1.74 | -5.66 | -6.97 | 1.9% | 6.8% |
| bystevenr | NEW | $5 | 2/1 | +1.59 | +0.77 | +3.17 | +0.77 | 1.6% | 5.9% |
| bystevenr | NEW | $10 | 2/1 | +3.20 | +1.58 | +6.40 | +1.58 | 1.3% | 5.6% |
| bystevenr | NEW | $13 | 2/1 | +4.17 | +2.06 | +8.34 | +2.06 | 1.3% | 5.5% |
| pointfarmcap | OLD | $5 | 1/1 | -1.08 | -1.17 | -1.08 | -1.17 | 2.9% | 8.2% |
| pointfarmcap | OLD | $10 | 1/1 | -2.12 | -2.26 | -2.12 | -2.26 | 2.4% | 7.4% |
| pointfarmcap | OLD | $13 | 1/1 | -2.74 | -2.92 | -2.74 | -2.92 | 2.3% | 7.2% |
| pointfarmcap | NEW | $5 | 0/0 | – | – | +0.00 | +0.00 | – | – |
| pointfarmcap | NEW | $10 | 0/0 | – | – | +0.00 | +0.00 | – | – |
| pointfarmcap | NEW | $13 | 0/0 | – | – | +0.00 | +0.00 | – | – |
| ExactTallTakin | OLD | $5 | 31/29 | +0.68 | +0.36 | +21.08 | +10.32 | 2.6% | 7.5% |
| ExactTallTakin | OLD | $10 | 31/29 | +1.38 | +0.74 | +42.91 | +21.50 | 2.4% | 7.2% |
| ExactTallTakin | OLD | $13 | 31/29 | +1.81 | +0.97 | +56.01 | +28.21 | 2.3% | 7.2% |
| ExactTallTakin | NEW | $5 | 5/5 | -0.59 | -0.69 | -2.95 | -3.44 | 1.5% | 6.4% |
| ExactTallTakin | NEW | $10 | 5/5 | -1.16 | -1.35 | -5.79 | -6.73 | 1.2% | 6.1% |
| ExactTallTakin | NEW | $13 | 5/5 | -1.50 | -1.74 | -7.48 | -8.70 | 1.2% | 6.0% |
| ALL | OLD | $5 | 53/51 | +0.38 | +0.12 | +19.96 | +5.95 | 2.6% | 7.5% |
| ALL | OLD | $10 | 53/51 | +0.78 | +0.27 | +41.33 | +13.59 | 2.4% | 7.2% |
| ALL | OLD | $13 | 53/51 | +1.02 | +0.36 | +54.14 | +18.17 | 2.3% | 7.1% |
| ALL | NEW | $5 | 11/10 | +0.26 | -0.13 | +2.88 | -1.28 | 1.6% | 6.5% |
| ALL | NEW | $10 | 11/10 | +0.55 | -0.23 | +6.04 | -2.26 | 1.4% | 6.2% |
| ALL | NEW | $13 | 11/10 | +0.72 | -0.29 | +7.94 | -2.85 | 1.3% | 6.1% |

## Sensitivity (ALL leaders pooled): priority fee × delay

| rules | size | prio SOL | delay | n | EV $ | total $ | CI |
|---|---|---|---|---|---|---|---|
| OLD | $5 | 0.0001 | 2 s | 55 | -0.37 | -20.10 | [-0.71, +0.02] |
| OLD | $5 | 0.0001 | 5 s | 53 | +0.38 | +19.96 | [-0.58, +1.91] |
| OLD | $5 | 0.0005 | 2 s | 55 | -0.47 | -25.62 | [-0.81, -0.08] |
| OLD | $5 | 0.0005 | 5 s | 53 | +0.28 | +14.62 | [-0.68, +1.81] |
| OLD | $10 | 0.0001 | 2 s | 55 | -0.70 | -38.76 | [-1.40, +0.06] |
| OLD | $10 | 0.0001 | 5 s | 53 | +0.78 | +41.33 | [-1.13, +3.85] |
| OLD | $10 | 0.0005 | 2 s | 55 | -0.81 | -44.28 | [-1.50, -0.04] |
| OLD | $10 | 0.0005 | 5 s | 53 | +0.68 | +35.98 | [-1.23, +3.76] |
| OLD | $13 | 0.0001 | 2 s | 55 | -0.91 | -49.95 | [-1.81, +0.09] |
| OLD | $13 | 0.0001 | 5 s | 53 | +1.02 | +54.14 | [-1.46, +5.02] |
| OLD | $13 | 0.0005 | 2 s | 55 | -1.01 | -55.47 | [-1.91, -0.01] |
| OLD | $13 | 0.0005 | 5 s | 53 | +0.92 | +48.80 | [-1.57, +4.92] |
| NEW | $5 | 0.0001 | 2 s | 10 | -0.13 | -1.26 | [-0.65, +0.50] |
| NEW | $5 | 0.0001 | 5 s | 11 | +0.26 | +2.88 | [-0.59, +1.35] |
| NEW | $5 | 0.0005 | 2 s | 10 | -0.22 | -2.22 | [-0.75, +0.40] |
| NEW | $5 | 0.0005 | 5 s | 11 | +0.17 | +1.82 | [-0.69, +1.25] |
| NEW | $10 | 0.0001 | 2 s | 10 | -0.23 | -2.27 | [-1.28, +1.03] |
| NEW | $10 | 0.0001 | 5 s | 11 | +0.55 | +6.04 | [-1.16, +2.73] |
| NEW | $10 | 0.0005 | 2 s | 10 | -0.32 | -3.23 | [-1.38, +0.93] |
| NEW | $10 | 0.0005 | 5 s | 11 | +0.45 | +4.98 | [-1.26, +2.63] |
| NEW | $13 | 0.0001 | 2 s | 10 | -0.29 | -2.87 | [-1.66, +1.35] |
| NEW | $13 | 0.0001 | 5 s | 11 | +0.72 | +7.94 | [-1.50, +3.55] |
| NEW | $13 | 0.0005 | 2 s | 10 | -0.38 | -3.83 | [-1.76, +1.25] |
| NEW | $13 | 0.0005 | 5 s | 11 | +0.62 | +6.87 | [-1.60, +3.45] |

## Entry funnel (why candidates were not copied; headline cell, $5)

| leader | rules | candidates | copied | skipped by reason |
|---|---|---|---|---|
| _benjitrades | OLD | 33 | 17 | no_pool_price 7, not_first_buy 6, chase 2, no_candles 1 |
| _benjitrades | NEW | 33 | 4 | mcap 14, no_pool_price 7, not_first_buy 6, age_lt_60m 1, liq 1 |
| bystevenr | OLD | 23 | 4 | chase 9, not_first_buy 6, no_pool_price 4 |
| bystevenr | NEW | 23 | 2 | mcap 10, not_first_buy 6, no_pool_price 4, chase 1 |
| pointfarmcap | OLD | 12 | 1 | not_first_buy 7, no_pool_price 3, chase 1 |
| pointfarmcap | NEW | 12 | 0 | not_first_buy 7, no_pool_price 3, liq 1, mcap 1 |
| ExactTallTakin | OLD | 41 | 31 | no_pool_price 7, not_first_buy 2, chase 1 |
| ExactTallTakin | NEW | 41 | 5 | mcap 27, no_pool_price 7, not_first_buy 2 |
| ALL | OLD | 109 | 53 | not_first_buy 21, no_pool_price 21, chase 13, no_candles 1 |
| ALL | NEW | 109 | 11 | mcap 52, not_first_buy 21, no_pool_price 21, liq 2, age_lt_60m 1, chase 1 |

## Data coverage

| leader | swaps in window | from Scout csv | from public RPC | UTC days with swaps | first – last swap (UTC) | first-buy candidates (≥$50, mcap ≥$100k) |
|---|---|---|---|---|---|---|
| _benjitrades | 907 | 727 | 180 | 30 | 09-23 23:05 – 10-23 23:41 | 33 |
| bystevenr | 342 | 328 | 14 | 16 | 10-08 14:36 – 10-23 22:59 | 23 |
| pointfarmcap | 337 | 337 | 0 | 6 | 10-16 00:27 – 10-21 18:14 | 12 |
| ExactTallTakin | 441 | 441 | 0 | 22 | 09-24 16:58 – 10-23 20:19 | 41 |

## Validation

- Gecko→on-chain level factor k (our entry mid / Gecko close of the entry minute), copied trades: n=64, p10 0.898, median 1.007, p90 1.128. k≈1 means Gecko candles and on-chain fills agree.
- Measured 5 s buy drift (pool fill after delay / leader fill): n=67, median 1.0248, p90 1.3362. Candidates without a measurement use the median (1.0248).
- Measured 5 s sell drift: n=53, median 1.0000.
- Token-age source for the NEW 60-min filter: {'rpc': 2, 'none': 92, 'gecko_pool_created_at': 15} (rpc = pool account history; gecko = GeckoTerminal pool_created_at of the top pool; none = unknown → filtered as age_unknown).

## Method

- **Signals:** every leader swap in the 30-day window (Scout's trader_swaps.csv + my public-RPC extension). Candidate = leader's first swap in a mint is a buy ≥ $50 at mcap ≥ $100k, and the on-chain pre-balance is 0 (live's first_buy rule).
- **Entry price:** the pool fill price (|Δquote vault| / |Δbase vault|) of the last trade in the leader's pool within slot+12 (5 s) or slot+5 (2 s), from getBlock; plus our own cost per side. Chase = our fill / leader fill − 1 (live definition).
- **Costs:** self-copy = Jupiter-quote fit from data/fs_quotes/quotes.jsonl (round trip = 1.85% − 1.78%·log10(liq/$100k), floor 0.5%) + (prio + 5000 lamports) × SOL per tx. Copyfomo = 5.3% round trip + pool impact above the $1M-liq level + $0.015/tx.
- **Path:** GeckoTerminal 1-min OHLCV of the token's pool, rescaled to the on-chain entry level (k). Stops gap through: fill at trigger × 0.975 or the candle open if it opened through. Stop is checked before TP within a candle; trailing stop uses the prior peak.
- **Exits:** OLD = SL −25%, TP +100% sells half; NEW = SL −15%, TP +50% sells half, then 15% trail from peak on the rest. Both mirror the leader's sells (assumption: a leader sell ≥ 95% of their balance = full exit, otherwise we sell the same fraction) at the leader's sell time + delay. Everything is flat at the next 08:00 Dublin (live close_hour); no entries 07:45–08:00; ≤3 open per leader; a night halts at −$20.
- **Held-out split:** fixed before any result: trades at/after 2026-10-15 07:00 UTC (last 9 of 30 Dublin nights ≈ 30%).
- **METHOD score:** scoring.score (OOS risk, MC p95 drawdown on $100, trade count, edge, night stability), 5 each, /25. Candidate needs ≥18, ≥50 trades, and holding out of sample.

## Caveats

- **Small samples.** Trade counts per leader are tiny; most CIs straddle zero, and no held-out cell reaches 20 trades. Treat any sign as anecdotal.
- **Missing benji wallet.** benji's TRUTH buy came from a wallet we don't have; the mapped wallet may not be his main one (mapping confidence: benji low, bystevenr low, pointfarmcap medium-low, ExactTallTakin medium).
- **Partial history.** Scout's csv is capped; my RPC extension finished for benji only (bystevenr partial, pointfarmcap/ExactTallTakin csv only) because free mainnet-beta RPC is ~0.4 calls/s.
- **1-minute candles** hide intra-minute wicks; stop fills use a 2.5% slip or the gap open, which may be kind on fast rugs.
- **Drift** is measured from the pool's next trades where a block was fetched, else the median; real Jupiter routing may differ.
- **$13 is not allowed live** (live.py HARD cap max_usd=10); shown for comparison only.
- **Selfcopy is LIVE with real money for benji** — this paper result says nothing to justify sizing up.
