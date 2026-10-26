# Winners batch 2: held-out-wallet replication (WN_B2_), PAPER ONLY

_Generated 2026-10-24T11:20Z. Code: wn_b2.py (stats), wn_b2_rows.py (scored rows). Data: Scout winners/ trades.csv (387 trips, 8 wallets). Batch 1 (benji, bystevenr, neodot, onlyzhynx; 141 trips) = discovery. Batch 2 (HMDW, B1uH, 82uF, HJp8; 246 trips, found independently by Scout, all LOW confidence) = held out by wallet. GT 1m candles for 185/246 batch-2 trips. Real costs: 4.7% if approx mcap < $1M else 2%; stop/trail exits +2 pts slip. OOS date split inside batch 2: entries from 2026-10-18 12:09Z (last 30%, n=63)._

## Plain answer
Both batch-1 findings replicate on wallets that played no part in forming them, so they look real, but neither becomes a tradeable rule. **No candidate** (best 14/25).

1. **Their entries alone have no edge.** The same batch-2 entries with fixed exits lose: SL25/TP50/2h −5.7%/trade, CI [−10%, −1%], n=184; SL20/TP30/30m −6.2%, CI [−9%, −3%]. Batch 1 was −6.4% and −6.3%. The CI is now clearly below zero.
2. **Their sells are well timed, though less so than batch 1.** After a batch-2 exit the price is a median −4.9% at 30 min (n=131, CI of mean [−14%, −2%]) and −10.8% at 2 h (n=122), against −0.3% and −1.7% at random times on the same tokens. Batch 1 was −15% and −34%. The effect is about a third as large.
3. **Their actual results after real costs:** mean +18%/trip, median −11%, win 30%, CI [−3%, +48%]. Like batch 1, it's carried by a few outliers (82uF is negative without its single +28 SOL trade).
4. **A mechanical trailing exit does not reproduce their exit skill.** The exit picked on batch 1 (15% trail armed at +20%) is −5.4% on batch 2, CI [−11%, 0%]. The only batch-2 rows near zero are the "arm at +100%" trails (+0.4% to +0.6%, CIs about [−8%, +10%], OOS n=63 +5% to +9%). Those were the *worst* settings on batch 1 (−5% to −13%), so picking them now would be fitting to the holdout.

## WHY THIS COULD FAIL
- Batch 2 is LOW confidence: wallets were found screening GeckoTerminal trades on older pools and kept for being profitable. That's selection on outcome, and 3 of 4 have negative medians.
- 61/246 trips have no usable candles (mostly dead pools), and those are probably biased toward rugs, so the fixed-exit losses are, if anything, understated.
- Post-exit drift could partly be mean reversion after any big pop, not skill. The random baseline uses the same tokens but not "right after a pump", so it is generous to the winners.
- Approx mcap uses current supply, so the cost bucket can be wrong for a few trips.

## What it means for the main project
The edge in these wallets is discretionary selling plus a few outliers, not entries and not a simple trail. The only route left is an exit-signal study (what precedes their sells: sell-side flow, buyer count rolling over, volume decay), which needs per-swap buy/sell flow from Scout. That's data-pending, and I won't spend Helius credits from Lab.
