# Copy candidates (2026-10-24T15:25:35+00:00, PAPER ONLY, proposals only)

Settings modelled (copyfomo): first buy per coin only, skip leader buys < $50, skip mcap < $100k at buy, TP +100% sells half, SL -25% (central: fill 2.5% below trigger; conservative band below), max chase 15%, delay 3-10 s (1-min GeckoTerminal candles, interpolated: an APPROXIMATION; headline uses 10 s), remainder exits with the leader, 2%/side + $0.015/side, slippage 0.5% + 2.0x stake/$20k assumed pool. Stake $9.40, balance $91.

## Inputs

- trader_swaps.csv (Scout per-swap): 2198 rows, 294 first buys, traders: BtheBezel, ExactTallTakin, _benjitrades, bystevenr, pointfarmcap.
- Scout leader-rank.md: present.
- Copycat leaderboard: leaderboard-2026-10-23.md.
- Copycat leaderboard handles: 34; with a Solana wallet in trader-analysis/wallets.json or Scout trader_wallets.json: 8; with per-swap history (trader_trades.csv): 5.
- 1-min candle coverage: 45/156 simulated trades (rest = approx mode, path unknown).

## Leaderboard -> wallet -> swap-history mapping

Handles are matched by exact name. Wallet pairings come from /workspace/trader-analysis/wallets.json (source not recorded, Scout rates them weak-medium). Leaderboard PnL/trades are copyfomo's own unverified figures; win rate, wallet, account age, typical mcap are not shown by the bot.

| handle | 30d rank | 7d rank | bot PnL (30d / 7d) | bot trades | avg buy | copiers | Solana wallet | swap history | status |
|---|---|---|---|---|---|---|---|---|---|
| ExactTallTakin | 1 | - | +$747.6k / - | 596 | $2.1k | 487 | AGdtsM...ii9v | 98 | simulated below |
| bystevenr | 2 | - | +$558.0k / - | 2665 | $1.1k | 291 | AH75Bn...mnKx | 63 | simulated below |
| pointfarmcap | - | 2 | - / +$373.1k | 5601 | $657.54 | 686 | Beqv6d...qeit | 16 | simulated below |
| BtheBezel | 6 | 3 | +$336.7k / +$230.0k | 1535 | $2.1k | 21 | HWYpE6...NWKR | 82 | simulated below |
| _benjitrades | 4 | - | +$445.7k / - | 540 | $1.7k | 52 | 9PB1RL...C3sc | 35 | simulated below |
| cosby | - | 1 | - / +$427.7k | 1700 | $4.6k | 25 | HmLwYR...WqnB | - | wallet known, waiting for Scout swap history |
| zelda89 | 18 | 6 | +$226.4k / +$189.8k | 126 | $426.43 | 43 | FG4c1q...QnRb | - | wallet known, waiting for Scout swap history |
| Altcoinist | - | 18 | - / +$119.5k | 171 | $1.4k | 35 | DVFYHV...ad49 | - | wallet known, waiting for Scout swap history |
| 000000 | 3 | 5 | +$474.2k / +$206.4k | 452 | $12.5k | 117 | NOT MAPPED | - | cannot simulate: no wallet |
| memeking888 | - | 4 | - / +$207.8k | 177 | $43.7k | 17 | NOT MAPPED | - | cannot simulate: no wallet |
| DONBAGS | 5 | - | +$339.4k / - | 291 | $2.6k | 90 | NOT MAPPED | - | cannot simulate: no wallet |
| 0xstanczyk | 7 | - | +$333.8k / - | 286 | $3.0k | 72 | NOT MAPPED | - | cannot simulate: no wallet |
| 0xbr9 | 15 | 7 | +$241.4k / +$173.7k | 98 | $4.9k | 2 | NOT MAPPED | - | cannot simulate: no wallet |
| heat | 8 | - | +$326.2k / - | 316 | $2.6k | 112 | NOT MAPPED | - | cannot simulate: no wallet |
| earn168 | - | 8 | - / +$173.5k | 288 | $2.1k | 5 | NOT MAPPED | - | cannot simulate: no wallet |
| JamJam0407 | 9 | 20 | +$299.2k / +$110.2k | 23 | $421.20 | 33 | NOT MAPPED | - | cannot simulate: no wallet |
| kv4rl | - | 9 | - / +$169.3k | 182 | $4.8k | 32 | NOT MAPPED | - | cannot simulate: no wallet |
| end837 | 10 | - | +$289.0k / - | 150 | $8.0k | 178 | NOT MAPPED | - | cannot simulate: no wallet |
| JohnnyBones | 14 | 10 | +$247.7k / +$162.5k | 609 | $951.73 | 20 | NOT MAPPED | - | cannot simulate: no wallet |
| 0xBEC001 | 11 | - | +$268.0k / - | 281 | $2.3k | 25 | NOT MAPPED | - | cannot simulate: no wallet |
| RareDualJay | - | 11 | - / +$143.0k | 702 | $716.84 | 146 | NOT MAPPED | - | cannot simulate: no wallet |
| Hifive_07 | 12 | - | +$251.9k / - | 142 | $510.75 | 51 | NOT MAPPED | - | cannot simulate: no wallet |
| BTCdayu | - | 12 | - / +$133.4k | 321 | $15.9k | 12 | NOT MAPPED | - | cannot simulate: no wallet |
| DonnyDicey | 13 | - | +$248.7k / - | 139 | $797.04 | 72 | NOT MAPPED | - | cannot simulate: no wallet |
| gtsb | - | 13 | - / +$132.4k | 245 | $1.0k | 10 | NOT MAPPED | - | cannot simulate: no wallet |
| PromUnchained | - | 14 | - / +$130.4k | 790 | $1.4k | 8 | NOT MAPPED | - | cannot simulate: no wallet |
| smoothietrades | - | 15 | - / +$129.9k | 1121 | $3.3k | 10 | NOT MAPPED | - | cannot simulate: no wallet |
| UsedMerePike | 16 | - | +$239.8k / - | 20 | not shown | 8 | NOT MAPPED | - | cannot simulate: no wallet |
| RunningClam | - | 16 | - / +$124.5k | 548 | $1.9k | 68 | NOT MAPPED | - | cannot simulate: no wallet |
| vvvvvvvvvv | 17 | - | +$238.1k / - | 469 | $852.32 | 24 | NOT MAPPED | - | cannot simulate: no wallet |
| orangie | - | 17 | - / +$123.2k | 1189 | $2.5k | 80 | NOT MAPPED | - | cannot simulate: no wallet |
| scrollingbeauty | 19 | - | +$211.5k / - | 42 | $151.89 | 8 | NOT MAPPED | - | cannot simulate: no wallet |
| pricedin | - | 19 | - / +$111.6k | 369 | $4.7k | 111 | NOT MAPPED | - | cannot simulate: no wallet |
| escobarpablo | 20 | - | +$198.1k / - | 343 | $522.26 | 21 | NOT MAPPED | - | cannot simulate: no wallet |

## Ranking (score /25 per METHOD.md; candidate needs >= 18, >= 50 trades, holds OOS)

| # | trader | trades | win | mean | net $ | net ex best $ | max DD $ | MC DD p5/p50/p95 (% of $91) | nights +/total | OOS n / mean | score | net $ at 3 s | skipped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pointfarmcap | 8 | 50% | +52% | +39.27 | +11.72 | 7.57 | 3%/4%/8% | 2/3 | 8 / +52% | 19 | +39.27 | open_leader 8 |
| 2 | bystevenr | 27 | 41% | +185% | +469.09 | +159.23 | 8.75 | 11%/16%/27% | 7/13 | 20 / +236% | 17 | +469.09 | skip_mcap 14, open_leader 22 |
| 3 | _benjitrades | 27 | 22% | -5% | -12.40 | -30.15 | 36.54 | 21%/30%/42% | 4/14 | 6 / -7% | 9 | -12.24 | skip_mcap 2, open_leader 6 |
| 4 | ExactTallTakin | 35 | 31% | -3% | -10.03 | -35.30 | 37.46 | 23%/33%/45% | 4/14 | 8 / -17% | 9 | -8.43 | skip_small_buy 16, skip_mcap 30, open_leader 17 |
| 5 | BtheBezel | 59 | 15% | -7% | -40.79 | -78.93 | 64.25 | 55%/78%/110% | 2/15 | 4 / -28% | 8 | -40.79 | skip_mcap 8, skip_small_buy 5, open_leader 10 |

### pointfarmcap

- Scores: OOS risk 5, drawdown 5, trades 1, edge 4, stability 4 = **19/25** (not a candidate).
- Walk-forward by night (Dublin): 10-15 +7.7, 10-18 -4.7, 10-19 +36.3
- WHY THIS COULD FAIL: Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by their own followers. Only 8 trades. Crowding: 686 copyfomo copiers race the same buys.
- Who is on the other side: The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us.

### bystevenr

- Scores: OOS risk 4, drawdown 3, trades 3, edge 4, stability 3 = **17/25** (not a candidate).
- Walk-forward by night (Dublin): 10-08 +28.2, 10-09 -2.1, 10-10 +23.7, 10-11 -3.8, 10-12 +309.2, 10-13 +1.6, 10-14 +58.2, 10-15 -5.3, 10-16 -0.9, 10-18 +7.0, 10-20 -3.7, 10-21 +59.9, 10-22 -2.9
- WHY THIS COULD FAIL: Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by their own followers. Only 27 trades. Crowding: 291 copyfomo copiers race the same buys.
- Who is on the other side: The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us.

### _benjitrades

- Scores: OOS risk 1, drawdown 2, trades 3, edge 2, stability 1 = **9/25** (not a candidate).
- Walk-forward by night (Dublin): 09-25 +5.8, 09-27 -4.8, 09-28 -2.9, 10-01 -8.6, 10-03 +5.2, 10-04 +2.8, 10-06 -2.9, 10-07 -2.9, 10-09 -2.9, 10-10 -2.9, 10-11 -2.2, 10-12 -2.6, 10-15 -2.9, 10-22 +9.2
- WHY THIS COULD FAIL: Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by their own followers. Only 27 trades. Crowding: 52 copyfomo copiers race the same buys.
- Who is on the other side: The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us.

### ExactTallTakin

- Scores: OOS risk 1, drawdown 2, trades 3, edge 2, stability 1 = **9/25** (not a candidate).
- Walk-forward by night (Dublin): 09-24 +25.2, 09-25 -0.9, 10-01 +2.4, 10-02 +0.8, 10-03 -2.9, 10-04 -8.6, 10-06 -2.0, 10-07 -3.0, 10-08 -8.6, 10-13 -4.1, 10-17 -3.1, 10-19 -0.2, 10-20 +1.5, 10-21 -6.5
- WHY THIS COULD FAIL: Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by their own followers. Only 35 trades. Crowding: 487 copyfomo copiers race the same buys.
- Who is on the other side: The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us.

### BtheBezel

- Scores: OOS risk 1, drawdown 1, trades 4, edge 1, stability 1 = **8/25** (not a candidate).
- Walk-forward by night (Dublin): 09-24 -1.8, 09-25 -3.4, 09-26 -5.0, 09-28 -10.6, 10-01 -10.0, 10-02 +32.5, 10-03 -5.7, 10-04 -8.3, 10-05 -6.1, 10-06 -13.5, 10-07 +9.9, 10-08 -8.3, 10-13 -2.0, 10-14 -2.9, 10-15 -5.7
- WHY THIS COULD FAIL: Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by their own followers. Crowding: 21 copyfomo copiers race the same buys.
- Who is on the other side: The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us.

## Stake-size test

Balance $91, nightly loss limit 20% = $18.20, per-trade cap 15% = $13.65. Traders available: 5 of the approved 5 (pointfarmcap, bystevenr, _benjitrades, ExactTallTakin, BtheBezel). Copies = simulated trades above (10 s delay, all filters).

Historical nights (all available traders together):

| stake | nights | max open at once | worst-night exposure $ | worst-night realised $ | worst intra-night running loss $ | nights hitting limit |
|---|---|---|---|---|---|---|
| $9.40 | 27 | 7 | 65.80 | -18.36 | -34.10 | 3 |
| $8.00 | 27 | 7 | 56.00 | -15.63 | -29.02 | 1 |
| $7.00 | 27 | 7 | 49.00 | -13.67 | -25.39 | 1 |
| $6.00 | 27 | 7 | 42.00 | -11.72 | -21.76 | 1 |
| $5.00 | 27 | 7 | 35.00 | -9.77 | -18.14 | 0 |
| $4.00 | 27 | 7 | 28.00 | -7.81 | -14.51 | 0 |

Monte Carlo over nights (10,000 draws): A = random historical night with whichever traders traded; B = all 5 fire the same night (5 trader-nights drawn from the available traders' active nights, aligned by time of day; assumes the 3 missing traders behave like these and are independent).

| stake | A: P(hit $18.20 limit) | A: p95 night loss $ | B: P(hit limit) | B: p95 night loss $ | B: median max open | B: p95 max open | B: p95 exposure $ |
|---|---|---|---|---|---|---|---|
| $9.40 | 11.1% | 20.39 | 30.9% | 33.79 | 4 | 9 | 84.60 |
| $8.00 | 4.0% | 17.36 | 21.9% | 28.30 | 4 | 9 | 72.00 |
| $7.00 | 4.0% | 15.19 | 16.3% | 24.84 | 4 | 9 | 63.00 |
| $6.00 | 3.5% | 13.02 | 10.5% | 21.68 | 4 | 9 | 54.00 |
| $5.00 | 0.0% | 10.85 | 4.5% | 17.79 | 4 | 9 | 45.00 |
| $4.00 | 0.0% | 8.68 | 1.1% | 14.22 | 4 | 9 | 36.00 |

**Stake recommendation (proposal): $5.00** = the largest tested stake whose probability of hitting the $18.20 nightly limit is <= 5% when all 5 traders fire (B: 4.5%; A, these 2 traders only: see table). All tested stakes are under the $13.65 per-trade cap. Hitting the limit is counted on the running realised loss within the night (stop-outs land before winners close).

## Model band (one real fill, so a conservative band is kept)

CENTRAL (headline above) = fit to the real TRUTH copy: stop fills 2.5% below the -25% trigger, copyfomo 2%/side, $0.03 gas per round trip. CONSERVATIVE = stop fills 5% below the trigger and never better than a crash candle's close (the previous model).

| trader | central net $ | conservative net $ | central ex-best $ | conservative ex-best $ | central score | conservative score |
|---|---|---|---|---|---|---|
| pointfarmcap | +39.27 | +38.93 | +11.72 | +11.39 | 19 | 19 |
| bystevenr | +469.09 | +467.91 | +159.23 | +158.06 | 17 | 17 |
| _benjitrades | -12.40 | -16.97 | -30.15 | -34.72 | 9 | 8 |
| ExactTallTakin | -10.03 | -15.90 | -35.30 | -41.17 | 9 | 8 |
| BtheBezel | -40.79 | -45.33 | -78.93 | -83.47 | 8 | 8 |

## Versus the ~5% round-trip cost drag (record only; Zero: no new copy leaders for now)

Leader mean = the leader's own return on the coins we would copy (before our costs). Copy mean = our simulated return per copy after all costs (central / conservative). To beat the drag, copy mean must be > 0 with the 95% lower bound > 0.

| trader | status | mapping conf. | swap coverage (UTC) | copies | leader mean | copy mean central / cons. | copy median | 95% low (central) | net $ central / cons. | beats drag? |
|---|---|---|---|---|---|---|---|---|---|---|
| pointfarmcap | record only | medium (identity) / low (as live-activity source) | 10-16 to 10-21 PARTIAL | 8 | +89% | +52% / +52% | +14% | -23% | +39.27 / +38.93 | no (too few copies) |
| bystevenr | record only | low | 10-08 to 10-23 PARTIAL | 27 | +390% | +185% / +184% | -9% | -60% | +469.09 / +467.91 | no (too few copies) |
| _benjitrades | live copy, $6 probation | low | 09-25 to 10-23 | 27 | +46% | -5% / -7% | -27% | -24% | -12.40 / -16.97 | no (too few copies) |
| ExactTallTakin | ended (Zero) | medium (identity) / low (as live-activity source) | 09-24 to 10-23 | 35 | -4% | -3% / -5% | -10% | -21% | -10.03 / -15.90 | no |
| BtheBezel | record only | low | 09-25 to 10-22 | 59 | -3% | -7% / -8% | -30% | -27% | -40.79 / -45.33 | no |

Excluded: cosby, zelda89, Altcoinist (Scout: the mappings look wrong). PARTIAL = Scout's fetch cap: bystevenr from Oct 8, pointfarmcap from Oct 16. Means are carried by 1-3 lottery coins (e.g. bystevenr's best copy is +3,300% from a +7,007% leader round, unverified); the median copy loses money for everyone except pointfarmcap (8 copies, 6 days). Leader return uses Scout's USD sizes, so a coin still partly held reads as a loss and any token received off-swap inflates the sell side. Every mapping except ExactTallTakin (medium) and pointfarmcap (medium-low) is LOW confidence: the history may not be the leader's.

P(hit the nightly limit) when all 5 fire, conservative model: $9.40 34.8%, $8.00 26.0%, $7.00 19.6%, $6.00 12.9%, $5.00 6.8%, $4.00 1.7%. Largest stake <= 5%: $4.00.

## Calibration: TRUTH (_benjitrades, real copyfomo copy)

Real (Copycat): buy $9.40 (no fill price shown); stop message 'all @ $0.000293, pnl $-2.78 (-29.5%)'; /copies realised -$2.81 (-29.9%). Bot times UTC-4: notice 20:42 UTC, stop 20:47 UTC. The bot's % = USD P&L / dollars in.

| delay | our chart fill | chase vs leader | central model | conservative model |
|---|---|---|---|---|
| 3s | $0.000449 ($449k) | +1.6% | exit $0.000330, -30.5% | exit $0.000292, -38.5% |
| 10s | $0.000459 ($459k) | +3.8% | exit $0.000337, -30.5% | exit $0.000292, -39.8% |
| 30s | $0.000486 ($486k) | +9.8% | exit $0.000357, -30.5% | exit $0.000292, -43.1% |

Reconciliation (Zero's question 1):
- If all $9.40 bought tokens and $0.000293 was the fill, -29.9% implies entry $0.000418 ($418k mcap), or $0.000400 if copyfomo's 2%/side is inside the P&L. The 20:42 UTC 1-min candle never traded below $0.000445 (open $0.000445, low $0.000445), and a 3-10 s copy lands at $0.000449-0.000459. So that reading needs an entry 6-13% below every chart print that minute.
- SOL/USD 20:42 -> 20:47 UTC: $103.76 -> $103.54 (-0.2%). Too small, and SOL falling would make a USD loss worse, not better.
- '$9.40 includes fees/priority before the token' goes the wrong way too: fewer tokens means a bigger loss at the same exit price.
- Most likely: entry matched the chart (~$0.000449-0.000459), the stop filled near its trigger (~$0.00033, 2-3% below the -25% line, partway down the 20:46 crash), and copyfomo's published 2%/side is inside the -$2.78. Math: 0.75 x 0.975 x 0.98 x 0.98 = -29.9%. The '@ $0.000293' would then be a reference price: it equals the 20:46 close / 20:47 open, i.e. the price when the message was built. That fits the docs: /portfolio prices are 'what each token would fetch if you sold it right now'. The extra $0.03 in /copies = gas billed back (per DefiLlama's adapter: '2% service fee plus the gas copyfomo fronts, billed back as one stablecoin transfer').
- Uncertainty: n=1, and no fill price was shown. The alternative (the leader actually bought in the 20:41 candle, which ranged $0.000239-0.000578, and our copy filled ~$0.000415 in a dip) can't be excluded. Benji's mapped wallet 9PB1...C3sc has no transaction after 19:44:58 UTC (public RPC), so we can't see the leader's own TRUTH swap. That also means this buy came from a wallet Scout doesn't have. Fastest check: /portfolio -> trade history shows 'the market cap you entered and exited at'. Entry ~$450k = most likely; ~$415k = the alternative.
- So no: the real stop cost was about -30% all-in, not -38 to -40%. The old model double-counted: 5 pts of stop slip PLUS 2%/side PLUS the crash-close rule. Central is now about -30.5% at 10 s (real -29.9%). The old rule is kept as the conservative band.

## copyfomo all-in cost per round trip (Zero's question 3)

Sources: copyfomo's docs give no fee number. Third-party fee page (degenbench) and DefiLlama's copyfomo adapter: 2% service fee on every buy and every sell (1.8% with a referral), plus the gas copyfomo fronts, billed back in stablecoin. Rent for token accounts is paid by copyfomo's fee payer and netted when the account closes. The '$0.95 minimum' on copyfomo.io is FOMO's own swap fee per an unverified review, and our real copy shows no such charge.
Assumptions: PumpSwap pool fee ~0.30%/side, possibly up to ~1.25% on low-mcap tiers; it's inside the fill price, so it shows up as slippage vs the chart. USDC->SOL hop ~0.05%/side. Impact = 2 x stake / $20k pool. Fixed: $0.03/round trip observed (TRUTH: -$2.81 vs -$2.78). Pessimistic: $0.25 (busy-launch priority/tips, or ~0.002 SOL ATA rent ~= $0.21 at $104/SOL if ever not refunded).

| stake | service 2x2% | pool+route (0.35-1.3%/side) | impact | fixed (obs. $0.03) | fixed as % of stake (obs. / pess. $0.25) | all-in round trip (central / pessimistic) |
|---|---|---|---|---|---|---|
| $4.00 | 4.0% | 0.7-2.6% | 0.08% | $0.03 | 0.75% / 6.25% | 5.5% / 12.9% |
| $6.00 | 4.0% | 0.7-2.6% | 0.12% | $0.03 | 0.50% / 4.17% | 5.3% / 10.9% |
| $9.40 | 4.0% | 0.7-2.6% | 0.19% | $0.03 | 0.32% / 2.66% | 5.2% / 9.4% |

Verdict: costs are mostly percentage-based, about 4.7% + impact per round trip. The fixed part is 0.75% of a $4 ticket vs 0.32% of $9.40 (pessimistic: 6.3% vs 2.7%). On cost alone, small tickets are still fine: $4 costs ~0.4 pt more than $9.40 at the observed $0.03. The real hurdle is the ~5% round-trip drag vs the leaders' simulated mean return per copy (see ranking). Ticket size doesn't fix that.
Settings note (copyfomo backup in skips-log.csv): 'leader sells at a loss: sell with them'. Exits otherwise mirror the leader, with SL -25% kept after TP. That matches this model.

## Missing inputs

- Per-swap history (Scout) for leaderboard traders with a known wallet: zelda89, cosby, Altcoinist.
- No wallet mapping at all (cannot simulate until someone pairs handle -> wallet): 000000, DONBAGS, 0xstanczyk, heat, JamJam0407, end837, 0xBEC001, Hifive_07, DonnyDicey, JohnnyBones, 0xbr9, UsedMerePike, vvvvvvvvvv, scrollingbeauty, escobarpablo, memeking888, earn168, kv4rl, RareDualJay, BTCdayu, gtsb, PromUnchained, smoothietrades, RunningClam, orangie, pricedin.
- 1-min candles for most leader trades (copytests.py fetches ~8 per pipeline run, newest first).
