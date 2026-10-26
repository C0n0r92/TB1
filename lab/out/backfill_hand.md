
## First read: what the numbers say (written 2026-10-23 ~23:40Z, on 186 of 515 sampled pools)

**Status: partial.** The candle fetcher is still running and resumable (bf_candles.py, about 3.75 calls/min under Zero's ≤4/min combined budget, so about 6 h for the other ~330 sampled pools). The migration sampler also keeps running on free public RPC. To refresh everything above: `flock -w 900 out/.pipeline.lock python3 bf_replay.py && python3 bf_report.py && python3 bf_final.py`. The tables above regenerate. This hand-written section does not, so recheck its numbers after a rerun.

1. **The baseline radar rule loses heavily on this universe**, both in-sample and held out.
   - Central imputation: 33 trades, mean −52%/trade, win rate 6%, rug 48%, 2 of 21 nights profitable.
   - Held-out nights: 11 trades, mean −58%, CI95 [−93%, +1%].
   - The low and high imputations look the same. Score 7/25.
2. **About 14 of 33 losers are bot 'staircase' pumps** (see the diagnostic above): steady 1-min up-ticks on flat volume, then a single candle of about −99%. Their 20-min accel/h1 profile scores very well on scan.py's momentum points.
   - They die young. The 45-min age guard, which the live radar has and the partial guard recreates, removes almost all of them.
   - Even without them, the baseline mean is about −19% (n = 17).
3. **The partial guard** (age ≥ 45 min, m5 crash/spike, liq-drop) has 13 trades, mean −41%, rug 15%, 3 OOS trades. Score 7/25. It is better than the baseline but still clearly negative.
   - The guard parts I can't recreate (holders, wash, danger/LP, creator, Scout verdict) might cut more losers. That is untested.
4. **Survivor momentum** (36 cells on the 33 central signals): every cell has ≤ 11 trades and ≤ 5 OOS trades. Scores are 5–14/25, and the 13–14 scores come from 1–2 OOS trades with zero in-sample trades.
   - The pre-registered centre cell T30/X20/cap100 has 5 trades, mean −36% (3 of 5 are staircase rugs). It is not evidence either way.
5. **Nothing comes near 18/25 with 50+ trades.** The largest cell is 39 trades. At the current fetch rate, the full 515-pool sample should give roughly 90–110 central radar signals and about 35–40 guarded ones, so 50+ closed trades is reachable only for the unguarded baseline.

## Who is on the other side

- **The staircase-pump operators.** A bot (or the dev's cluster) buys at a steady pace to print a smooth, accelerating chart. Then it sells a large held supply into the momentum buyers that a score like scan.py's attracts.
  - scan.py rewards exactly what they fake: volume acceleration, positive m5/h1, and a high buy ratio. A smooth staircase *is* 5-min buy pressure.
- **Snipers and bundlers from the bonding curve.** They hold cheap supply at graduation and distribute during the first hour, which is the radar's entry window (age 0.25–6 h, mostly 0.3–0.5 h here).
- **Other momentum bots**, including Telegram alert followers, that see the same DexScreener/Gecko signals. Being first among them isn't an edge when the seller is the operator.

## WHY THIS COULD FAIL (i.e. why these results may not describe the live radar)

1. **Row-level fidelity is about 60%.** With the rate-matched imputation, the replay agrees with live on only about 60% of pass/fail calls (21 agree and 28 disagree among the 49 rows where either side passed). The missing score inputs are a large share of the score: about 12.7 pts median, up to 34. Buyer growth, top10, insiders, copycats and the revoked bonus can all be imputed only as a constant.
2. **Discovery differs.** The live radar only scores what DexScreener boosts/profiles and Gecko trending surface (about 25 health checks per scan). The replay scores every graduation. If discovery itself filters out staircases (e.g. boosted coins are better), the live radar would do better than this. The opposite is possible too: boosts are paid promotion, often by the same operators.
3. **Liquidity is modelled, not observed.** PumpSwap constant product from the graduation reserves gives a median 3.4% error, but live/model ranges 0.95–3.37 (p10–p90). Under-modelled liquidity means slippage and the liq gates are pessimistic for pools where LP was added. The model is wrong for pools whose LP was pulled (live rejects 'LP 0% locked' rows).
4. **Gecko 1-min candles only include minutes with trades**, and m5 from DexScreener disagrees with the candle-based value (corr 0.15). The m5 points and the crash/spike guard are approximations.
5. **Sample is about 3.5% of daily graduations**, so concurrency is understated and max-3-open almost never binds. Day-level P&L variance is understated too.
6. **Small n.** 33 central trades and 11 OOS. Every CI is wide, and the post-hoc staircase split is in-sample by construction.
7. **Holdout reuse.** The holdout nights 10-14…10-22 overlap the period the live radar has been tuned on, so OOS here is "held out from this replay", not "unseen by the team".

## Recreated / approximated / missing: the short list
- **Recreated:** price, mcap, age, accel (corr 0.99), h1 (corr 0.72), liq-drop guard, age guard, m5 crash/spike (approx.).
- **Approximated:** liq (model), m5.
- **Missing (constant imputation only):** buy ratios br5/br1 (not in Gecko OHLCV), copycat penalty, buyer growth, top10/insiders/authorities, holders, mcap/holder, wash ratio, rugcheck danger, LP lock, creator %, creator tokens, Scout launch verdict, discovery source.
- **What would fix most of it:** Helius per-pool swap history (signer and side per tx gives buy/sell counts, unique-buyer growth, wash ratio), plus point-in-time holder snapshots from token-account balance changes. That is Scout's domain, and I could not message Scout (no SendToAgent tool). I did not run Scout's Helius-backed scripts, because they would spend Scout's key and budget.

## Honest sample sizes
- On-chain migration signatures paged: 76k. Real graduations sampled: 515 over 29 UTC days (9–27/day). With candles so far: 170 ok, 16 no-data. Reached the prefilter: 46 pools.
- Radar signals: 16 / 33 / 39 (low/central/high). Partial-guard signals: 7 / 13 / 16. OOS (central): 11 baseline, 3 guarded.
- Variants tried (shared counter): 370 after this run (42 BF_ rows).
