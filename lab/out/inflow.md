# Inflow-spike test (IF_*), PAPER ONLY. First read 2026-10-24 ~15:15Z, for Zero

**Verdict: NO. Don't go live at 0.04 SOL.** On the proxy, all 1,323 settings lose money after costs, and **all of them lose before costs too**. The best gross result is −1.2%/trade. No setting is positive in-sample, so nothing can hold out. Best METHOD score: 9/25.

## What could and could not be tested
- **A real historical test of the brief's signal is impossible from free data.** The spike needs net buy volume and unique buyers per minute. Lab's cache has GeckoTerminal 1-min OHLCV, which only has total USD volume. GT `/pools/{pool}/trades` returns the last 300 trades (≤24 h), and DexScreener txns only give rolling m5/h1 counts. Neither has history. The radar's scanned.jsonl has DexScreener buy_ratio/buyer_growth, but only for 574 rows over a few hours, too few to test.
- **PROXY used, labelled as such:** on 1-min candles, a signal fires when
  - volume over the last W complete minutes per minute ≥ R × the prior 30-min per-minute volume (floor $50/min), and
  - the window is green (close > window-start open), standing in for net buying.
  - Unique buyers are **not** in the proxy.
  - Modelled pool liquidity ≥ $20k, and age since migration ≥ 5 min.
- **Universe:** 1,614 on-chain-sampled pump.fun→PumpSwap graduations, 2026-09-25 → 10-23 (bf_* backfill, no survivor bias; about 4.7% of all graduations). Only about 220 of them ever reach $20k liquidity and spike.
- **Grid:** W 1/3/5 min × R 2/3/5× × delay 5/15/30 s = 27 entry settings. Each was run against 49 exits: Zero's fast grid TP +8/10/15/20 × SL −8/10/15 × hold 5/10/15/30 min (48), plus +20/−15/60 min. That makes 1,323 variants, and variants_tried went from 1,361 to 2,684.
- **Harness:**
  - Entry is interpolated inside the next 1-min bar at T+delay.
  - The stop is checked before the target in each bar. A stop that gaps fills at min(stop, close), or at the open if the bar opened through it. The target fills at its level.
  - Costs per side: 2% fee + 0.5% + 2 × stake/liquidity, with liquidity scaled by √price.
  - Max 3 open, one position per coin, 60-min re-entry cooldown.
  - Holdout: Dublin nights ≥ 2026-10-14, the same split fixed earlier for backfill.md (about 22% of trades).
- **Cost tiers:** "base" = 2%/side + slippage. "@0.04 SOL" = base minus 2 × (0.0001 priority + 0.000005 base fee) / 0.04 SOL, i.e. −0.53 pp. With a 0.0005 priority fee the drag is −2.5 pp. Token-account rent (0.00203 SOL, about 5% of the stake) is assumed reclaimed on close; if it isn't, it's another −5 pp. All in, costs are about 4.8% per round trip at this size.

## Best 5 (picked in-sample, net per trade)
| variant | n (IS/OOS) | win | net @0.04 SOL | net base 2%/side | IS | **held out** | trades/h (sample) |
|---|---|---|---|---|---|---|---|
| IF_w5_r2_d30_tp08_sl15_h05 | 569 (442/127) | 33% | −6.6% | −6.1% | −6.6% | **−6.9%** [CI −8.9, −5.2], win 29% | 0.85 |
| IF_w5_r3_d30_tp08_sl15_h05 | 336 (265/71) | 38% | −7.3% | −6.7% | −6.7% | **−9.2%** | 0.50 |
| IF_w5_r2_d30_tp08_sl15_h10 | 569 (442/127) | 38% | −7.0% | −6.5% | −6.8% | **−7.8%** | 0.85 |
| IF_w5_r2_d30_tp08_sl15_h15 | 569 (442/127) | 40% | −7.1% | −6.6% | −6.9% | **−7.6%** | 0.85 |
| IF_w5_r3_d15_tp10_sl15_h05 | 336 (265/71) | 35% | −7.7% | −7.2% | −7.0% | **−10.3%** | 0.50 |

- **Gross, before any cost,** the best setting is −1.2% mean, +0.2% median. Fees and slippage (about 4.9%) then sink it. **None of the 1,323 settings is gross-positive.**
- **Neighbours agree, all negative:**
  - delay 5/15/30 s: −7.1 / −7.0 / −6.6%
  - R 3×: −7.3%; W 3: −7.5%
  - TP 10%: −7.3%; SL 10%: −7.2%; hold 10 min: −7.0%
- **There is no lucky profitable setting, because nothing is profitable.** The ranking spread (−6.6% to −12.6%) is what 1,323 tries on noise should produce.
- **Trades per hour:** 0.85/h in the 4.7% sample. Scaled to every graduation that's very roughly 15-20 signals/h before the 3-open cap. That's plenty of trades, but each one costs about 7%.
- **By dimension (mean of all variants):** delay 5 s −8.4%, 15 s −8.6%, 30 s −8.9%. Short exits (5 min hold, wide −15% stop, small +8% TP) lose least. That's just less time paying for a negative drift, the same finding as FE.

## Zero's original exits (+20% / −15% / 30 or 60 min), entry 15 s
| W/R | 30 min (n, win, @0.04 SOL, OOS) | 60 min |
|---|---|---|
| 1 / 2× | 814, 28%, −8.6%, OOS −8.9% | 806, 33%, −8.9%, OOS −9.2% |
| 3 / 3× (forward runner setting) | 460, 27%, −9.5%, OOS −10.6% | 457, 29%, −10.3%, OOS −10.3% |
| 5 / 5× | 186, 34%, −10.2%, OOS −12.4% | 186, 35%, −10.4%, OOS −13.1% |

## vs the old runner-radar (backfill.md, same pools and period)
- The old radar baseline was −52%/trade (−58% held out, n=33, 7/25).
- The inflow proxy loses far less per trade (−7% to −10%), mostly because of its tight −15% stop and short holds rather than a better entry. It is still negative, and negative before costs.
- Not apples to apples: the radar had different exits and a score filter.

## METHOD score
The best row scores **9/25**:
- OOS risk 1
- drawdown 1 (MC p95 > 50% of $100 equity at $10/trade)
- trades 5
- edge 1
- stability 1 (1 of 29 nights profitable)

**Not a candidate.** 25 rows merged as IF_ (the top 5, 18 radar-exit rows, and delay neighbours); all 1,323 configs are counted.

## WHY THIS COULD FAIL (even live with real flow data)
- **Who is on the other side:** snipers and bundlers who bought minutes earlier and sell into exactly this visible spike. A spike on public data is visible to every bot; at 5-30 s behind block-level bots, we are the exit liquidity.
- **Cost wall:** about 4.8% round trip at 0.04 SOL (more with a higher priority fee or unreclaimed rent). An edge has to beat that on every trade, and the gross edge measured here is below zero.
- **Proxy gap:** the real signal adds unique-buyer counts and net buy/sell, which this test lacks. It could be better than the proxy, but the radar's buy-ratio/buyer-growth score (which had those features) also lost badly. The forward run is the only honest test of the true signal.
- **Small universe:** about 220 spiking pools in 29 days, a 4.7% sample, 1,323 variants tried (2,684 total). Any small positive found here would likely be luck.

## Paper forward (live now)
- `forward/inflow_fwd.py` (stdlib only, no keys, no LLM).
- It uses Lab's shared throttle lock with 8 s spacing, so Lab's total is ≤ 7.5 calls/min.
- **Signal:** the real one from GT trades, W 3 min, R 3× on buy USD and unique buyers, net buy > 0, ≥5 buyers, liquidity ≥ $20k, age ≥ 5 min.
- **Entry:** 15 s delay (actual delay logged), 0.04 SOL.
- **Three exit tracks on each entry:**
  - T30 and T60: +20 / −15 / 30 or 60 min
  - F08_15_5: +8 / −15 / 5 min, the in-sample-best fast combo. It was added as an extra track, not a replacement, because it was not clearly better and is still negative.
- **Files:** log forward/inflow_fwd.jsonl, pidfile forward/inflow.pid, log forward/inflow.log. Run `python3 forward/inflow_fwd.py --summary` for the numbers.
- **Runner changes, 15:11-15:14Z (bak-v1/v2 kept):**
  - Pre-screen loosened from 1.5× to 1.0×.
  - Majors and stables (age > 3 days or liquidity > $2M) are skipped.
  - **Busy-coin fallback:** when the last 300 trades span less than W+2 min, the window comes from the trades and the prior rate from GT pool attributes: (h1−m5 buy count)/55 and h1 unique buyers/60. These are logged as `prior_src: attr`. The fallback needs at least 0.5 min of trades; some coins fit 300 trades into under a minute. Without this, the busiest spiking coins could never fire.
