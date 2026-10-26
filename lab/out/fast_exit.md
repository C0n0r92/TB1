# Fast exits on recorded copy signals (PAPER, 2026-10-24 11:42Z)

## Plain answer

- **Every one of the 36 fast-exit rules loses money after costs, at every cost level and under both stop-fill models.** Profitable settings: 0 of 216 (36 rules × 3 costs × 2 stop models).
- Best rule (chosen on in-sample only, self $10, stops filled at the bar's low): **TP +20% sell all, stop −8%, max hold 10 min** (`FE_tp20_sl08_h10`). Net per trade **-10.4% at self $10** and **-12.8% at copyfomo** on 154 trades; in-sample -10.8% (n=107) vs held out -9.6% (n=47) at self $10 (copyfomo -13.2% / -11.7%).
- With the gentler METHOD stop fill (trigger −2.5%, or the open on a gap) the same rule is -4.3% at self $10 and -5.8% at copyfomo (IS -3.7% / OOS -5.6%); best-in-sample rule there is `FE_tp20_sl08_h10`.
- **vs the current ladder (same 154 trades): it loses less, not more.** Ladder -17.6%/trade at self $10 (IS -20.2% / OOS -11.8%), -18.6% at copyfomo. Paired difference (fast − ladder) +7.2%/trade, 95% CI [+1.5%, +12.0%]; IS +9.3% (n=107), **held out only +2.2% (n=47, CI [-13.4%, +13.1%]), i.e. not distinguishable from the ladder out of sample**; copyfomo +5.9% (held out +0.8%). With METHOD stop fills: ladder -9.8% vs fast -4.3%; held out +0.2% at self $10 and -0.7% at copyfomo.
- Neighbours agree on the *direction* (short holds and a +20% target are least bad; 36/36 rules beat the ladder on point estimate both in-sample and held out; none significantly held out), but nothing is profitable, so the lucky-number check is n/a: there is no edge to be lucky about. 'Loses less' mostly means 'is in the market for less time': after costs (~3% round trip at self $10) these signals drift down on average, and the shortest hold wins.
- METHOD score: **9/25** at self $10 (sc_oos_risk=1, sc_drawdown=1, sc_trades=5, sc_edge=1, sc_stability=1), 9/25 at copyfomo. Not a candidate (needs ≥18, >0 out of sample). Ladder: 9/25.

**WHY THIS COULD FAIL:** 97 of 154 trades are Scout's hand-picked winners (selection-contaminated) and only 6 are live signals; 1-min GT candles are sparse, so intra-minute stop/target fills are approximations (22 trades' candles end before 45 min).
The held-out edge over the ladder is +2% with a CI spanning ±13%: 'fast loses less' is mostly 'less time exposed to a down-drifting book', not an edge. On the other side: the leader and faster bots who bought before our +5 s fill and sell into our bounce.

## Setup

- Signals pooled (154 with price data): 6 live paper entries from /workspace/selfcopy (benji J9WL4, ypnn-day Bert, CLAUDIA, 9cRCn9, 98kfF7, FARTBOY; Bert/CLAUDIA/FARTBOY are the 3 copylive BUYs missed today), 97 Scout winners round trips (_benjitrades/bystevenr/onlyzhynx, bj_full_replay inputs), 51 CR 30-day first buys with candles (benji/bystevenr/ExactTallTakin/pointfarmcap; (leader, mint) pairs already in Scout dropped). Excluded: bystevenr 5UHeHy (dry-run, forced; no GT trades since 10-22, no price data at entry). No live-wallet trades exist (live copy book has never filled).
- Fresh data: 14 GeckoTerminal calls (7 pool lookups + 7 1-min OHLCV pulls) at 7.5 s spacing for the live mints only (data/fe/). No Helius/Scout credits, no X.
- Entry: signal + 5 s (measured on-chain drift for Scout/CR entries where clean, else leader median; live = our Jupiter-quoted paper entry net of impact). Triggers on mark-to-market value net of exit cost (same convention as CR/BJ tests).
- Costs: self $10 3.0% round trip, self $5 4.7%, copyfomo 5.3% (at $10), each + liquidity-scaled impact (Jupiter quote fit, liq ~ √price) + gas for extra sell legs. Stop checked before target in every bar.
- Stop fill: **low** (primary, per brief) = bar's low; **std** = open if gapped, else trigger × 0.975 (METHOD/TRUTH calibration). Targets fill at the level, or the open if gapped above.
- Max hold: exit at the last 1-min close before entry + hold. Ladder: TP +40%/25%, +100%/25%, rest +500%, breakeven stop after TP1, −20% hard stop, run to the end of the candle data (Scout: full horizon, CR: leader exit/08:00, live: now).
- Holdout: latest 30% of pooled signals by time, from **2026-10-15 15:33 UTC** (IS 107 / OOS 47). Selection uses in-sample only.
- Variants tried counter updated by merge (+222 configs: 37 rules × 3 costs × 2 stop models).

## All 36 rules + ladder, stop fill = low (mean net per trade; IS / OOS)

| rule | n | self $10 all | self $10 IS / OOS | self $5 | copyfomo all | copyfomo IS / OOS | win | stops/tp/time | vs ladder (self10, paired) | score /25 |
|---|---|---|---|---|---|---|---|---|---|---|
| `FE_tp12_sl15_h10` | 154 | -10.0% | -11.5% / -6.4% | -11.0% | -11.3% | -12.3% / -8.9% | 32% | 76/42/36 | +7.7% | 9 |
| `FE_tp08_sl15_h10` | 154 | -10.0% | -11.3% / -7.0% | -11.5% | -11.9% | -12.9% / -9.8% | 36% | 71/52/31 | +7.6% | 9 |
| `FE_tp12_sl15_h20` | 154 | -10.0% | -11.8% / -6.1% | -11.2% | -11.4% | -12.6% / -8.5% | 32% | 78/46/30 | +7.6% | 9 |
| `FE_tp08_sl15_h20` | 154 | -10.1% | -11.5% / -6.8% | -11.6% | -12.1% | -13.2% / -9.6% | 36% | 73/54/27 | +7.5% | 9 |
| `FE_tp08_sl15_h45` | 154 | -10.1% | -11.4% / -7.0% | -11.4% | -11.9% | -12.9% / -9.7% | 38% | 75/58/21 | +7.5% | 9 |
| `FE_tp12_sl15_h45` | 154 | -10.2% | -11.9% / -6.2% | -11.1% | -11.4% | -12.6% / -8.7% | 32% | 80/49/25 | +7.4% | 9 |
| `FE_tp20_sl15_h10` | 154 | -10.2% | -11.4% / -7.5% | -10.6% | -11.0% | -12.0% / -8.6% | 28% | 82/28/44 | +7.4% | 9 |
| `FE_tp20_sl10_h10` | 154 | -10.3% | -11.1% / -8.4% | -11.9% | -12.4% | -12.5% / -12.1% | 21% | 97/20/37 | +7.3% | 9 |
| `FE_tp20_sl08_h10` **(best IS)** | 154 | -10.4% | -10.8% / -9.6% | -12.2% | -12.8% | -13.2% / -11.7% | 19% | 102/18/34 | +7.2% | 9 |
| `FE_tp20_sl10_h45` | 154 | -10.4% | -11.5% / -8.1% | -12.1% | -12.8% | -13.1% / -12.1% | 19% | 102/25/27 | +7.2% | 9 |
| `FE_tp20_sl15_h20` | 154 | -10.5% | -12.0% / -7.1% | -10.9% | -11.3% | -12.6% / -8.4% | 27% | 85/30/39 | +7.1% | 9 |
| `FE_tp20_sl10_h20` | 154 | -10.6% | -11.7% / -8.2% | -12.2% | -12.7% | -13.0% / -12.1% | 20% | 98/20/36 | +7.0% | 9 |
| `FE_tp20_sl15_h45` | 154 | -10.7% | -12.3% / -7.0% | -11.0% | -11.4% | -12.9% / -8.1% | 26% | 89/35/30 | +6.9% | 9 |
| `FE_tp12_sl10_h10` | 154 | -10.7% | -11.7% / -8.4% | -12.3% | -12.8% | -13.6% / -10.9% | 23% | 93/29/32 | +6.9% | 9 |
| `FE_tp12_sl08_h10` | 154 | -10.7% | -11.4% / -9.2% | -12.5% | -13.1% | -14.0% / -11.0% | 22% | 98/27/29 | +6.9% | 9 |
| `FE_tp12_sl10_h20` | 154 | -10.7% | -11.9% / -8.1% | -12.3% | -12.9% | -13.8% / -10.9% | 23% | 94/32/28 | +6.9% | 9 |
| `FE_tp12_sl10_h45` | 154 | -10.7% | -11.8% / -8.2% | -12.3% | -13.0% | -13.8% / -11.1% | 23% | 96/35/23 | +6.9% | 9 |
| `FE_tp20_sl08_h20` | 154 | -10.8% | -11.4% / -9.6% | -12.5% | -12.9% | -13.4% / -11.7% | 18% | 106/18/30 | +6.8% | 9 |
| `FE_tp20_sl08_h45` | 154 | -10.9% | -11.4% / -9.6% | -12.4% | -12.9% | -13.4% / -11.7% | 16% | 111/22/21 | +6.7% | 9 |
| `FE_tp12_sl08_h20` | 154 | -10.9% | -11.6% / -9.2% | -12.6% | -13.2% | -14.1% / -11.0% | 21% | 102/29/23 | +6.7% | 9 |
| `FE_tp08_sl10_h45` | 154 | -10.9% | -12.0% / -8.6% | -12.3% | -13.1% | -13.7% / -11.7% | 27% | 92/42/20 | +6.7% | 9 |
| `FE_tp12_sl08_h45` | 154 | -11.0% | -11.7% / -9.3% | -12.6% | -13.2% | -14.1% / -11.2% | 21% | 104/31/19 | +6.6% | 9 |
| `FE_tp08_sl10_h10` | 154 | -11.0% | -12.1% / -8.6% | -12.3% | -12.9% | -13.5% / -11.5% | 25% | 90/36/28 | +6.6% | 9 |
| `FE_tp30_sl10_h10` | 154 | -11.0% | -12.0% / -8.9% | -12.8% | -13.3% | -13.8% / -12.3% | 18% | 102/12/40 | +6.6% | 9 |
| `FE_tp08_sl10_h20` | 154 | -11.0% | -12.2% / -8.3% | -12.3% | -13.0% | -13.7% / -11.5% | 25% | 91/38/25 | +6.6% | 9 |
| `FE_tp30_sl10_h45` | 154 | -11.0% | -12.6% / -7.5% | -13.0% | -13.6% | -14.6% / -11.5% | 16% | 108/16/30 | +6.6% | 9 |
| `FE_tp08_sl08_h10` | 154 | -11.1% | -11.9% / -9.2% | -12.7% | -13.3% | -14.1% / -11.5% | 24% | 95/34/25 | +6.6% | 9 |
| `FE_tp08_sl08_h20` | 154 | -11.2% | -12.0% / -9.2% | -12.8% | -13.3% | -14.1% / -11.5% | 23% | 99/35/20 | +6.4% | 9 |
| `FE_tp30_sl15_h10` | 154 | -11.2% | -13.1% / -6.9% | -11.4% | -11.8% | -13.5% / -8.1% | 23% | 89/17/48 | +6.4% | 9 |
| `FE_tp30_sl08_h10` | 154 | -11.2% | -11.6% / -10.3% | -13.0% | -13.5% | -14.2% / -11.9% | 16% | 107/10/37 | +6.4% | 9 |
| `FE_tp08_sl08_h45` | 154 | -11.3% | -12.1% / -9.4% | -12.8% | -13.4% | -14.2% / -11.7% | 24% | 101/37/16 | +6.4% | 9 |
| `FE_tp30_sl10_h20` | 154 | -11.3% | -12.6% / -8.4% | -13.1% | -13.7% | -14.4% / -12.1% | 16% | 104/13/37 | +6.3% | 9 |
| `FE_tp30_sl08_h45` | 154 | -11.6% | -12.5% / -9.6% | -13.1% | -13.5% | -14.6% / -11.1% | 12% | 117/13/24 | +6.0% | 9 |
| `FE_tp30_sl08_h20` | 154 | -11.6% | -12.3% / -10.1% | -13.2% | -13.7% | -14.5% / -11.7% | 14% | 112/11/31 | +6.0% | 9 |
| `FE_tp30_sl15_h20` | 154 | -11.8% | -14.0% / -6.8% | -12.2% | -12.3% | -14.4% / -7.6% | 21% | 93/18/43 | +5.8% | 9 |
| `FE_tp30_sl15_h45` | 154 | -12.6% | -14.7% / -7.8% | -12.2% | -12.4% | -15.0% / -6.5% | 19% | 98/21/35 | +5.0% | 9 |
| `FE_ladder` | 154 | -17.6% | -20.2% / -11.8% | -18.9% | -18.6% | -21.3% / -12.5% | 21% | 135/1/18 | – | 9 |

## All 36 rules + ladder, stop fill = std (mean net per trade; IS / OOS)

| rule | n | self $10 all | self $10 IS / OOS | self $5 | copyfomo all | copyfomo IS / OOS | win | stops/tp/time | vs ladder (self10, paired) | score /25 |
|---|---|---|---|---|---|---|---|---|---|---|
| `FE_tp20_sl08_h10` **(best IS)** | 154 | -4.3% | -3.7% / -5.6% | -5.5% | -5.8% | -5.4% / -6.9% | 19% | 102/18/34 | +5.5% | 10 |
| `FE_tp12_sl08_h10` | 154 | -4.6% | -4.3% / -5.3% | -5.8% | -6.2% | -6.2% / -6.3% | 22% | 98/27/29 | +5.2% | 10 |
| `FE_tp20_sl08_h45` | 154 | -4.7% | -4.3% / -5.5% | -5.6% | -5.9% | -5.6% / -6.6% | 16% | 111/22/21 | +5.1% | 10 |
| `FE_tp20_sl08_h20` | 154 | -4.7% | -4.3% / -5.6% | -5.7% | -6.0% | -5.6% / -6.9% | 18% | 106/18/30 | +5.1% | 10 |
| `FE_tp12_sl08_h20` | 154 | -4.8% | -4.6% / -5.3% | -5.9% | -6.2% | -6.2% / -6.3% | 21% | 102/29/23 | +5.0% | 10 |
| `FE_tp30_sl08_h10` | 154 | -4.8% | -4.1% / -6.4% | -6.0% | -6.3% | -6.0% / -7.1% | 16% | 107/10/37 | +5.0% | 10 |
| `FE_tp12_sl08_h45` | 154 | -4.8% | -4.6% / -5.2% | -5.8% | -6.2% | -6.2% / -6.2% | 21% | 104/31/19 | +5.0% | 10 |
| `FE_tp08_sl08_h10` | 154 | -5.0% | -4.8% / -5.5% | -6.1% | -6.4% | -6.3% / -6.8% | 24% | 95/34/25 | +4.8% | 10 |
| `FE_tp20_sl10_h10` | 154 | -5.1% | -5.0% / -5.2% | -6.1% | -6.3% | -5.5% / -8.2% | 21% | 97/20/37 | +4.8% | 9 |
| `FE_tp08_sl08_h20` | 154 | -5.1% | -4.9% / -5.5% | -6.1% | -6.4% | -6.3% / -6.8% | 23% | 99/35/20 | +4.7% | 9 |
| `FE_tp20_sl10_h45` | 154 | -5.1% | -5.3% / -4.6% | -6.3% | -6.7% | -6.1% / -8.0% | 19% | 102/25/27 | +4.7% | 9 |
| `FE_tp08_sl08_h45` | 154 | -5.1% | -5.0% / -5.5% | -6.1% | -6.4% | -6.3% / -6.7% | 24% | 101/37/16 | +4.7% | 9 |
| `FE_tp30_sl08_h45` | 154 | -5.2% | -5.0% / -5.5% | -6.0% | -6.2% | -6.3% / -6.0% | 12% | 117/13/24 | +4.6% | 9 |
| `FE_tp30_sl08_h20` | 154 | -5.2% | -4.8% / -6.2% | -6.2% | -6.4% | -6.2% / -6.9% | 14% | 112/11/31 | +4.6% | 9 |
| `FE_tp20_sl10_h20` | 154 | -5.3% | -5.5% / -4.9% | -6.4% | -6.7% | -6.0% / -8.2% | 20% | 98/20/36 | +4.5% | 9 |
| `FE_tp12_sl10_h45` | 154 | -5.4% | -5.7% / -4.8% | -6.5% | -6.9% | -6.9% / -7.1% | 23% | 96/35/23 | +4.4% | 9 |
| `FE_tp12_sl10_h10` | 154 | -5.4% | -5.5% / -5.1% | -6.5% | -6.7% | -6.6% / -7.0% | 23% | 93/29/32 | +4.4% | 9 |
| `FE_tp20_sl15_h10` | 154 | -5.5% | -5.7% / -5.0% | -6.2% | -6.6% | -6.6% / -6.4% | 28% | 82/28/44 | +4.4% | 9 |
| `FE_tp12_sl10_h20` | 154 | -5.5% | -5.7% / -4.8% | -6.5% | -6.9% | -6.8% / -7.1% | 23% | 94/32/28 | +4.3% | 9 |
| `FE_tp30_sl10_h45` | 154 | -5.5% | -6.1% / -4.1% | -6.9% | -7.3% | -7.2% / -7.4% | 16% | 108/16/30 | +4.3% | 9 |
| `FE_tp30_sl10_h10` | 154 | -5.5% | -5.5% / -5.6% | -6.8% | -7.0% | -6.4% / -8.4% | 18% | 102/12/40 | +4.3% | 9 |
| `FE_tp12_sl15_h10` | 154 | -5.5% | -5.9% / -4.6% | -6.7% | -7.0% | -7.1% / -6.5% | 32% | 76/42/36 | +4.3% | 9 |
| `FE_tp12_sl15_h20` | 154 | -5.6% | -6.1% / -4.3% | -6.8% | -7.1% | -7.4% / -6.2% | 32% | 78/46/30 | +4.2% | 9 |
| `FE_tp08_sl10_h45` | 154 | -5.7% | -5.8% / -5.3% | -6.6% | -7.0% | -6.7% / -7.6% | 27% | 92/42/20 | +4.1% | 9 |
| `FE_tp12_sl15_h45` | 154 | -5.7% | -6.3% / -4.4% | -6.7% | -7.0% | -7.4% / -6.3% | 32% | 80/49/25 | +4.1% | 9 |
| `FE_tp20_sl15_h20` | 154 | -5.7% | -6.3% / -4.6% | -6.5% | -6.9% | -7.3% / -6.1% | 27% | 85/30/39 | +4.1% | 9 |
| `FE_tp20_sl15_h45` | 154 | -5.8% | -6.4% / -4.4% | -6.4% | -6.8% | -7.3% / -5.8% | 26% | 89/35/30 | +4.0% | 9 |
| `FE_tp30_sl10_h20` | 154 | -5.8% | -6.1% / -5.2% | -7.1% | -7.4% | -7.0% / -8.3% | 16% | 104/13/37 | +4.0% | 9 |
| `FE_tp08_sl10_h10` | 154 | -5.8% | -5.9% / -5.5% | -6.5% | -6.8% | -6.5% / -7.6% | 25% | 90/36/28 | +4.0% | 9 |
| `FE_tp08_sl10_h20` | 154 | -5.8% | -6.1% / -5.3% | -6.5% | -7.0% | -6.7% / -7.6% | 25% | 91/38/25 | +4.0% | 9 |
| `FE_tp08_sl15_h10` | 154 | -5.8% | -6.1% / -5.3% | -7.2% | -7.6% | -7.7% / -7.5% | 36% | 71/52/31 | +4.0% | 9 |
| `FE_tp08_sl15_h20` | 154 | -5.9% | -6.2% / -5.1% | -7.3% | -7.8% | -8.0% / -7.2% | 36% | 73/54/27 | +3.9% | 9 |
| `FE_tp08_sl15_h45` | 154 | -5.9% | -6.2% / -5.2% | -7.1% | -7.6% | -7.7% / -7.3% | 38% | 75/58/21 | +3.9% | 9 |
| `FE_tp30_sl15_h10` | 154 | -6.3% | -7.2% / -4.3% | -6.8% | -7.2% | -7.8% / -5.8% | 23% | 89/17/48 | +3.5% | 9 |
| `FE_tp30_sl15_h20` | 154 | -6.8% | -7.9% / -4.3% | -7.4% | -7.6% | -8.6% / -5.4% | 21% | 93/18/43 | +3.0% | 9 |
| `FE_tp30_sl15_h45` | 154 | -6.9% | -8.5% / -3.5% | -7.4% | -7.5% | -9.0% / -4.1% | 19% | 98/21/35 | +2.9% | 9 |
| `FE_ladder` | 154 | -9.8% | -11.6% / -5.8% | -11.0% | -11.0% | -13.1% / -6.2% | 22% | 135/1/18 | – | 9 |

## Best rule by source (stop fill = low, self $10)

| source | n | fast net $ | ladder net $ |
|---|---|---|---|
| live | 6 | -0.84 | -0.28 |
| scout | 97 | -94.11 | -157.61 |
| cr30 | 51 | -65.73 | -113.30 |

## Today's live signals (stop fill = std, self $10, per-trade return)

| signal | fast best | ladder |
|---|---|---|
| J9WL4z (_benjitrades) | -10.3% (stop) | +7.9% (stop_be) |
| Bert (ypnn-day) | -3.2% (time) | -3.1% (horizon) |
| CLAUDIA (ypnn-day) | +11.8% (time) | +4.4% (horizon) |
| 9cRCn9 (ypnn-day) | -1.4% (time) | -0.9% (horizon) |
| 98kfF7 (ypnn-day) | -2.3% (time) | -3.6% (horizon) |
| FARTBOY (ypnn-day) | -2.9% (time) | -2.7% (horizon) |
