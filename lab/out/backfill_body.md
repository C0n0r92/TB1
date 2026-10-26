# Backfill replay: radar / partial guard / survivor momentum on ~4 weeks of PumpSwap graduations (PAPER ONLY)

Generated 2026-10-23T23:35:58+00:00 by `bf_replay.py` + `bf_report.py`. Paper only, no trades, no keys. Free public data only.

## Data sources

- **Universe**: every pump.fun to PumpSwap graduation is signed by the pump.fun migration account `39azUYFW…jUJjg`. I paged its full signature history with the free public Solana RPC (`getSignaturesForAddress`, api.mainnet-beta.solana.com; the radar uses this RPC too). Then I fetched a seeded random sample of txs per UTC day (`getTransaction`). I kept only real migrations: success, a `Migrate` instruction, no `already migrated` retry. The mint is the non-WSOL mint; the pool is the owner of the 206.9M-token vault.
  - Signatures paged: 76,182. Successful: 48,158 (about 1,700/day, but many are retries). Txs inspected: 749. Real migrations: 518 (69%), so roughly 1,189 graduations/day.
- **Prices/volumes**: GeckoTerminal 1-min OHLCV (USD, base token), one call per pool from creation (first 1,000 traded minutes). A second forward call is made for signal pools whose data ends before the trade deadline. Gecko and DexScreener calls share one cross-process throttle: 6.5 s spacing (≤9/min) until 23:33Z, then 16 s (≤4/min combined) per Zero's budget request.
- **SOL/USD**: GeckoTerminal hourly SOL/USDC (Raydium `Czfq3…`). Fallback: Scout's daily `data/solusd.json`.
- **Survivorship probe**: DexScreener `tokens/v1` (30 mints per call) shows which sampled mints are still listed today.
- **Not used**: X, Helius (Scout's key; I have no SendToAgent tool to ask Scout), Solscan, pump.fun and GMGN (blocked), Polymarket.

## Universe size by day (Dublin noon-to-noon night of the migration)

Days are UTC migration days. Columns: pools sampled; Gecko ok / 404 / empty; pools passing the radar prefilter at some 10-min scan between 15 min and 6 h; radar signals under the low / central / high imputation; partial-guard signals (central).

| day | sampled | ok | 404 | empty | prefilter | sig low/central/high | guard central |
|---|---|---|---|---|---|---|---|
| 2026-09-25 | 18 | 7 | 0 | 0 | 2 | 1/2/2 | 0 |
| 2026-09-26 | 19 | 7 | 0 | 0 | 0 | 1/1/2 | 1 |
| 2026-09-27 | 23 | 7 | 0 | 0 | 5 | 1/1/2 | 1 |
| 2026-09-28 | 16 | 7 | 0 | 0 | 2 | 0/0/1 | 0 |
| 2026-09-29 | 16 | 7 | 0 | 0 | 3 | 0/1/1 | 0 |
| 2026-09-30 | 27 | 7 | 0 | 0 | 4 | 2/3/4 | 1 |
| 2026-10-01 | 14 | 7 | 0 | 0 | 1 | 1/2/2 | 1 |
| 2026-10-02 | 23 | 7 | 0 | 0 | 2 | 0/1/1 | 0 |
| 2026-10-03 | 24 | 7 | 0 | 0 | 0 | 0/0/0 | 0 |
| 2026-10-04 | 22 | 7 | 0 | 0 | 2 | 1/1/1 | 1 |
| 2026-10-05 | 20 | 7 | 0 | 0 | 2 | 1/3/4 | 1 |
| 2026-10-06 | 20 | 7 | 0 | 0 | 2 | 0/0/0 | 0 |
| 2026-10-07 | 17 | 6 | 0 | 0 | 2 | 0/1/1 | 1 |
| 2026-10-08 | 10 | 6 | 0 | 0 | 0 | 0/0/0 | 0 |
| 2026-10-09 | 21 | 5 | 0 | 1 | 0 | 1/1/1 | 1 |
| 2026-10-10 | 19 | 5 | 0 | 1 | 1 | 0/1/1 | 0 |
| 2026-10-11 | 25 | 6 | 0 | 0 | 2 | 0/1/1 | 0 |
| 2026-10-12 | 21 | 5 | 0 | 1 | 1 | 2/2/2 | 2 |
| 2026-10-13 | 11 | 6 | 0 | 0 | 1 | 1/1/1 | 0 |
| 2026-10-14 | 16 | 5 | 0 | 1 | 1 | 0/0/0 | 0 |
| 2026-10-15 | 18 | 5 | 0 | 1 | 1 | 0/2/2 | 0 |
| 2026-10-16 | 17 | 6 | 0 | 0 | 1 | 0/1/1 | 0 |
| 2026-10-17 | 17 | 5 | 0 | 1 | 3 | 1/3/3 | 0 |
| 2026-10-18 | 12 | 5 | 0 | 1 | 1 | 0/0/0 | 0 |
| 2026-10-19 | 15 | 5 | 0 | 1 | 2 | 1/1/1 | 1 |
| 2026-10-20 | 10 | 5 | 0 | 1 | 0 | 0/0/0 | 0 |
| 2026-10-21 | 17 | 3 | 0 | 3 | 2 | 0/1/2 | 1 |
| 2026-10-22 | 9 | 4 | 0 | 2 | 1 | 2/3/3 | 1 |
| 2026-10-23 | 18 | 4 | 0 | 2 | 2 | 0/0/0 | 0 |
| **total** | 515 | 170 | 0 | 16 | 46 | 16/33/39 | 13 |

329 sampled pools still have no candles (fetcher queue). Sampling/prefilter columns are keyed by UTC migration day; the signal columns by the signal's Dublin night (the IS/OOS key), so a row can show signals with no prefilter pool on the same line.

## Survivorship bias

- **Universe bias: none by construction.** The sample comes from on-chain migration txs, not from a listing. Dead coins are included at their true rate.
- **Data gaps**: 16 of 186 fetched pools (8.6%) have no Gecko candles (404 or empty). They are excluded, and this is the only data-driven survivorship leak. A pool with no Gecko candles mostly never traded after migration, so it could not have reached the radar's $50k mcap / $15k liq prefilter anyway; the leak into the signal set is therefore about zero.
- **How fast graduations die**: median 28 traded minutes in the first 16.7 h. 66% traded in fewer than 60 distinct minutes. 71% ever printed ≥ $50k mcap. 27% passed the radar prefilter at a scan.
- **What a survivor-only universe would have shown.** I checked which sampled mints DexScreener still lists today with ≥ $5k liquidity. Of 33 closed baseline (central) trades, 2 are on such coins. Mean net return: survivors -32.2%, the rest -53.3%, all -52.0%. So building the backfill from coins still listed today would have overstated the mean by **+19.8 pp/trade**. That is the bias this design avoids.
- Share of all sampled graduations still listed with ≥ $5k liquidity today: 4/170 (2.4%).

## Which score inputs could be recreated

I checked the replay against the live radar on tonight's 187 scanned rows (50 pairs). Each row was rebuilt from 1-min Gecko candles at the same timestamp.

| scan.py input | status | live vs replay |
|---|---|---|
| price, mcap (price × 1e9 supply) | **recreated** | price median error 1.3%, mcap 1.8% |
| pair age | **recreated** (on-chain migration time) | exact |
| vol accel v5/(vh1/12) | **recreated** | corr 0.99, median abs error 0.07 |
| m5 / h1 price change | **recreated** (rolling 5 m / 60 m on 1-min closes) | m5 median abs error 2.1 pp (Pearson corr 0.16, dragged down by DexScreener outliers like +2,002%), h1 corr 0.77, median abs error 6.7 pp |
| liquidity | **approximated**: constant-product model 2·√(206.9M·85·p·SOLUSD) × 1.002 (fitted on live) | median error 3.5%; p10–p90 of the live/model ratio 0.95–5.69. **Blind to third-party LP adds or removes** |
| mint/freeze authority | **recreated** (pump.fun mints are always revoked; +8) | – |
| buy ratio 5m / 1h (6+4 pts), sells≫buys reject | **missing** (needs per-tx side counts) | – |
| unique-buyer growth (12 pts) | **missing** | – |
| top10 % (0–12 pts, >35% reject), insiders (−5), rugged | **missing** | – |
| copycat ticker count (−8) | **missing** (needs the live token set at that time) | – |
| discovery: DexScreener boosts/profiles, Gecko trending, top-25-by-accel health budget | **missing**. The replay scans *every* graduation, the live radar only the ones it discovered | – |
| rugguard: holders, mcap/holder, wash ratio, danger, LP lock, creator %, creator tokens, Scout launch verdict | **missing** | – |
| rugguard: age ≥ 45 min, m5 crash/spike, −6 dip, liq drop ≥ 30% vs scan in 90 min | **recreated** (liq drop goes through the model, i.e. a price drop of about 51%) | – |

**Missing mass.** On live rows, live pre-guard score minus the reconstructable part (computed from the live features) gives a median of 12.8 pts (p10 5.1, p90 24.8). It correlates +0.43 with the known part. The known part from candles vs from live features: corr 0.95, median abs error 1.0 pts.

**Imputation** (pre-registered, a constant added to the known part): low = p50 12.8, **central = rate-matched 22.3**, high = p90 24.8. Rate-matched means the smallest constant whose replay pass count equals the live pass count (40 rows) on the calibration rows.
Row-level agreement with central: live pass & replay pass 26, live pass & replay fail 14, live fail & replay pass 14, both fail 133. **So the replay reproduces the pass *rate*, but only about 60% of the individual pass/fail calls.** Treat every result below as a test of a radar-*like* rule, not of the exact live radar.

## Results (costs as harness: 2%/side + $0.05/tx, liquidity-scaled slippage on the model liq, gap-through stops, max 3 open, flat 08:00 Dublin)

Holdout = nights 2026-10-14…2026-10-22 (the last 9 of 28 nights). It was fixed before any result. No rule was tuned on in-sample: the radar rule is scan.py's own, and the SM grid and centre cell (T30/X20/cap100) were pre-registered in survivor_momentum.py. Variants tried after this run: **370**.

| variant | cand | closed | IS n | IS net $ | IS mean | OOS n | OOS net $ | OOS mean | OOS CI95 mean | rug % | score /25 | MC dd p95 | nights +/n | lucky |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BF_A_radar_low | 16 | 16 | 12 | -57.87 | -48.2% | 4 | +0.89 | +2.2% | [-90%,+145%] | 31% | 7 | 0.794 | 1/13 | n/a (<5 trades) |
| BF_G_partialguard_low | 7 | 7 | 7 | -22.65 | -32.4% | 0 |  |  |  | 14% | 7 | 0.227 | 0/6 | n/a (<5 trades) |
| BF_A_radar_central | 33 | 33 | 22 | -107.48 | -48.9% | 11 | -64.14 | -58.3% | [-93%,+1%] | 48% | 7 | 1.94 | 2/21 | n/a (<5 trades) |
| BF_G_partialguard_central | 13 | 13 | 10 | -41.38 | -41.4% | 3 | +2.55 | +8.5% | [-95%,+158%] | 15% | 7 | 0.546 | 1/12 | n/a (<5 trades) |
| BF_A_radar_high | 39 | 39 | 27 | -136.25 | -50.5% | 12 | -74.15 | -61.8% | [-94%,-6%] | 51% | 7 | 2.328 | 1/22 | n/a (<5 trades) |
| BF_G_partialguard_high | 16 | 16 | 13 | -55.57 | -42.7% | 3 | +2.55 | +8.5% | [-95%,+158%] | 19% | 7 | 0.701 | 2/14 | n/a (<5 trades) |
| BF_SM_T60_X20_capnone_LIQMODEL | 33 | 2 | 0 |  |  | 2 | +2.18 | +10.9% | [-96%,+118%] | 50% | 14 | 0.096 | 1/2 | n/a (<5 trades) |
| BF_SM_T45_X20_cap100_LIQMODEL | 33 | 1 | 0 |  |  | 1 | +14.11 | +141.1% | [+141%,+141%] | 0% | 13 | 0.0 | 1/1 | n/a (<5 trades) |
| BF_SM_T60_X20_cap100_LIQMODEL | 33 | 1 | 0 |  |  | 1 | +11.78 | +117.8% | [+118%,+118%] | 0% | 13 | 0.0 | 1/1 | n/a (<5 trades) |
| BF_SM_T60_X20_cap200_LIQMODEL | 33 | 1 | 0 |  |  | 1 | +11.78 | +117.8% | [+118%,+118%] | 0% | 13 | 0.0 | 1/1 | n/a (<5 trades) |
| BF_SM_T45_X0_cap100_LIQMODEL | 33 | 4 | 3 | -13.71 | -45.7% | 1 | +14.11 | +141.1% | [+141%,+141%] | 25% | 10 | 0.137 | 1/4 | n/a (<5 trades) |
| BF_SM_T60_X0_cap100_LIQMODEL | 33 | 3 | 2 | -12.05 | -60.3% | 1 | +11.78 | +117.8% | [+118%,+118%] | 33% | 10 | 0.121 | 1/3 | n/a (<5 trades) |
| BF_SM_T60_X0_cap200_LIQMODEL | 33 | 3 | 2 | -12.05 | -60.3% | 1 | +11.78 | +117.8% | [+118%,+118%] | 33% | 10 | 0.121 | 1/3 | n/a (<5 trades) |
| BF_SM_T60_X0_capnone_LIQMODEL | 33 | 4 | 2 | -12.05 | -60.3% | 2 | +2.18 | +10.9% | [-96%,+118%] | 50% | 9 | 0.216 | 1/4 | n/a (<5 trades) |
| BF_SM_T60_X40_capnone_LIQMODEL | 33 | 1 | 0 |  |  | 1 | -9.59 | -95.9% | [-96%,-96%] | 100% | 9 | 0.096 | 0/1 | n/a (<5 trades) |
| BF_SM_T20_X40_capnone_LIQMODEL | 33 | 2 | 2 | -19.36 | -96.8% | 0 |  |  |  | 100% | 8 | 0.194 | 0/2 | n/a (<5 trades) |
| BF_SM_T20_X40_cap100_LIQMODEL | 33 | 1 | 1 | -10.04 | -100.4% | 0 |  |  |  | 100% | 8 | 0.1 | 0/1 | n/a (<5 trades) |
| BF_SM_T20_X40_cap200_LIQMODEL | 33 | 2 | 2 | -19.36 | -96.8% | 0 |  |  |  | 100% | 8 | 0.194 | 0/2 | n/a (<5 trades) |
| BF_SM_T45_X20_cap200_LIQMODEL | 33 | 4 | 1 | -10.04 | -100.4% | 3 | -5.39 | -18.0% | [-100%,+141%] | 75% | 7 | 0.295 | 1/4 | n/a (<5 trades) |
| BF_SM_T45_X40_cap200_LIQMODEL | 33 | 3 | 1 | -10.04 | -100.4% | 2 | -19.50 | -97.5% | [-100%,-95%] | 100% | 7 | 0.295 | 0/3 | n/a (<5 trades) |
| BF_SM_T20_X0_capnone_LIQMODEL | 33 | 11 | 6 | -32.62 | -54.4% | 5 | -21.27 | -42.5% | [-96%,+59%] | 64% | 6 | 0.725 | 2/11 | n/a (<5 trades) |
| BF_SM_T20_X0_cap100_LIQMODEL | 33 | 10 | 5 | -23.29 | -46.6% | 5 | -21.27 | -42.5% | [-96%,+59%] | 60% | 6 | 0.632 | 2/10 | n/a (<5 trades) |
| BF_SM_T20_X0_cap200_LIQMODEL | 33 | 11 | 6 | -32.62 | -54.4% | 5 | -21.27 | -42.5% | [-96%,+59%] | 64% | 6 | 0.725 | 2/11 | n/a (<5 trades) |
| BF_SM_T30_X0_capnone_LIQMODEL | 33 | 11 | 6 | -41.49 | -69.1% | 5 | -22.89 | -45.8% | [-98%,+53%] | 64% | 6 | 0.796 | 1/11 | n/a (<5 trades) |
| BF_SM_T30_X0_cap100_LIQMODEL | 33 | 7 | 4 | -21.52 | -53.8% | 3 | -3.85 | -12.8% | [-100%,+153%] | 43% | 6 | 0.406 | 1/7 | n/a (<5 trades) |
| BF_SM_T30_X0_cap200_LIQMODEL | 33 | 11 | 6 | -41.49 | -69.1% | 5 | -22.89 | -45.8% | [-98%,+53%] | 64% | 6 | 0.796 | 1/11 | n/a (<5 trades) |
| BF_SM_T30_X20_cap100_LIQMODEL | 33 | 5 | 2 | -14.15 | -70.7% | 3 | -3.85 | -12.8% | [-100%,+153%] | 60% | 6 | 0.332 | 1/5 | n/a (<5 trades) |
| BF_SM_T30_X40_capnone_LIQMODEL | 33 | 4 | 2 | -19.97 | -99.9% | 2 | -19.04 | -95.2% | [-100%,-90%] | 100% | 6 | 0.39 | 0/4 | n/a (<5 trades) |
| BF_SM_T30_X40_cap200_LIQMODEL | 33 | 4 | 2 | -19.97 | -99.9% | 2 | -19.04 | -95.2% | [-100%,-90%] | 100% | 6 | 0.39 | 0/4 | n/a (<5 trades) |
| BF_SM_T45_X0_capnone_LIQMODEL | 33 | 8 | 5 | -30.45 | -60.9% | 3 | -5.39 | -18.0% | [-100%,+141%] | 62% | 6 | 0.5 | 1/8 | n/a (<5 trades) |
| BF_SM_T45_X0_cap200_LIQMODEL | 33 | 7 | 4 | -23.75 | -59.4% | 3 | -5.39 | -18.0% | [-100%,+141%] | 57% | 6 | 0.432 | 1/7 | n/a (<5 trades) |
| BF_SM_T45_X20_capnone_LIQMODEL | 33 | 5 | 2 | -16.74 | -83.7% | 3 | -5.39 | -18.0% | [-100%,+141%] | 80% | 6 | 0.362 | 1/5 | n/a (<5 trades) |
| BF_SM_T45_X40_capnone_LIQMODEL | 33 | 4 | 2 | -16.74 | -83.7% | 2 | -19.50 | -97.5% | [-100%,-95%] | 100% | 6 | 0.362 | 0/4 | n/a (<5 trades) |
| BF_SM_T20_X20_capnone_LIQMODEL | 33 | 7 | 3 | -23.20 | -77.3% | 4 | -37.02 | -92.6% | [-98%,-90%] | 86% | 5 | 0.602 | 0/7 | n/a (<5 trades) |
| BF_SM_T20_X20_cap100_LIQMODEL | 33 | 6 | 2 | -13.87 | -69.4% | 4 | -37.02 | -92.6% | [-98%,-90%] | 83% | 5 | 0.509 | 0/6 | n/a (<5 trades) |
| BF_SM_T20_X20_cap200_LIQMODEL | 33 | 7 | 3 | -23.20 | -77.3% | 4 | -37.02 | -92.6% | [-98%,-90%] | 86% | 5 | 0.602 | 0/7 | n/a (<5 trades) |
| BF_SM_T30_X20_capnone_LIQMODEL | 33 | 9 | 4 | -34.12 | -85.3% | 5 | -22.89 | -45.8% | [-98%,+53%] | 78% | 5 | 0.723 | 1/9 | n/a (<5 trades) |
| BF_SM_T30_X20_cap200_LIQMODEL | 33 | 9 | 4 | -34.12 | -85.3% | 5 | -22.89 | -45.8% | [-98%,+53%] | 78% | 5 | 0.723 | 1/9 | n/a (<5 trades) |
| BF_SM_T30_X40_cap100_LIQMODEL | 33 | 0 | 0 |  |  | 0 |  |  |  |  | 5 |  | 0/0 | n/a (0 trades) |
| BF_SM_T45_X40_cap100_LIQMODEL | 33 | 0 | 0 |  |  | 0 |  |  |  |  | 5 |  | 0/0 | n/a (0 trades) |
| BF_SM_T60_X40_cap100_LIQMODEL | 33 | 0 | 0 |  |  | 0 |  |  |  |  | 5 |  | 0/0 | n/a (0 trades) |
| BF_SM_T60_X40_cap200_LIQMODEL | 33 | 0 | 0 |  |  | 0 |  |  |  |  | 5 |  | 0/0 | n/a (0 trades) |

## Post-hoc diagnostic: bot 'staircase' pumps (NOT a tested rule)

stair20 = the share of up-closing 1-min candles among the 20 before the signal. A staircase pump shows steady up-ticks on flat volume, then one candle of about −99%. It was found by reading the worst trades *after* the results, so any filter built on it is in-sample until a fresh holdout tests it.

| variant | stair20 < 0.7: n / mean / ≤−80% | 0.7–0.85 | ≥ 0.85 |
|---|---|---|---|
| BF_A_radar_low | 10 / -12% / 1 | 2 / -41% / 0 | 4 / -93% / 4 |
| BF_G_partialguard_low | 7 / -32% / 0 | 0 | 0 |
| BF_A_radar_central | 17 / -19% / 2 | 2 / -41% / 0 | 14 / -93% / 14 |
| BF_G_partialguard_central | 11 / -41% / 1 | 1 / -99% / 1 | 1 / +158% / 0 |
| BF_A_radar_high | 19 / -24% / 4 | 4 / -36% / 0 | 16 / -94% / 16 |
| BF_G_partialguard_high | 14 / -42% / 2 | 1 / -99% / 1 | 1 / +158% / 0 |
| BF_SM_T30_X20_cap100_LIQMODEL | 1 / +152% / 0 | 1 / -41% / 0 | 3 / -97% / 3 |

On live calibration rows, 40 of 187 had stair20 ≥ 0.85. The live (guarded) radar passed 5 of them; most were rejected as 'too young' (the 45-min age guard). Their median top10 (13.98%) is no higher than the median of the other rows (13.63%), so the missing top10 input would *not* have removed them.

