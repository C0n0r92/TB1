# Exit-signal study (ES_): what precedes the winners' sells? PAPER ONLY

_Generated 2026-10-24 ~14:30Z. Code: es_common.py, es_control.py (tasks 1-2), es_rules.py (task 3), es_cr30.py (extra OOS), es_rows.py (scored rows). Cache only: data/cl/wn 1m GT candles + Scout winners/trades.csv. **Zero API calls.** Batch 1 (benji, bystevenr, neodot, onlyzhynx) = discovery; batch 2 (HMDW, B1uH, 82uF, HJp8) = held out by wallet. Costs as wn_b2: 4.7% if approx mcap < $1M else 2%; stop and signal exits +2 pts slip. variants_tried = 1361 (+38)._

## Plain answer
**No candidate. Best ES rule 10/25.** The "well-timed sells" finding mostly goes away once it's properly controlled.
- **Control.** The winners exit while the price is already falling: at the sell, the b1 median is −24% vs entry and −41% from the peak since entry. On these dying tokens *any* exit triggered by a falling price is followed by more decline.
  - A dumb 15% trail (trail15_arm20) is followed by **−20% (30 m) / −33% (2 h)** on b1. Winners' own exits: −15% / −33%.
- **Matched post-pump baseline.** The winners only beat it clearly on b1, and only against the cross-token match. Against the same token at the same run-up, the difference is ~0 in both batches.
- **Features.** Candle features barely separate sells from held moments. AUC is 0.43-0.57 everywhere, and no single feature replicates across batches.
- **Rules.** None of the 36 pre-registered rules (3 families + neighbours) beats the plain trail15_arm20 or fixed SL25/TP50/2h baselines. All are negative on both batches and both date halves.

## 1) Control: winner-exit drift vs matched post-pump baseline
Matching: the state at the sell is (log price vs the trip's entry, log price vs the 60-min low of closes). Baseline moments are every 1-m close on the same candle series with |Δ| < 0.15 on both and no winner sell within 15 min. "Same token" = matched moments on that token only. "Pool" = median of matched moments across all tokens in the batch. Paired diff = exit drift − matched drift (per exit). 95% bootstrap CIs.

| batch | horizon | winner exit drift mean [CI] (median) | same-token matched, paired diff mean [CI] / median [CI] (n) | cross-token matched, paired diff mean [CI] / median [CI] (n) | all moments median |
|---|---|---|---|---|---|
| b1 | 30 m | −15.3% [−23, −8] (−12.1%), n=73 | −5.8% [−16, +3.5] / −0.6% [−4.6, +2.7] (43) | −8.9% [−17, −0.6] / −8.5% [−20, +1.1] (73) | −3.8% |
| b1 | 2 h | −32.8% [−43, −22] (−32.3%), n=60 | −28% [−82, +7] / +4.3% [−2.9, +7.5] (32) | −28% [−48, −11] / −19% [−24, −11] (60) | −11.6% |
| b2 | 30 m | −7.5% [−14, −0.9] (−4.0%), n=114 | +2.3% [−3.8, +8.5] / −1.1% [−4.2, +3.5] (88) | −4.8% [−11, +1.2] / −3.5% [−5.5, −0.8] (112) | −0.7% |
| b2 | 2 h | −10.5% [−20, +1.1] (−9.9%), n=108 | −2.8% [−12, +5.2] / −2.7% [−7.1, +1.1] (85) | −4.6% [−14, +6.7] / −7.9% [−11, −2.5] (106) | −4.2% |

**Mechanical exits as a second control.** These are post-exit drift after the rule's own signal exits, on the same trips.

| exit | b1 30 m / 2 h | b2 30 m / 2 h |
|---|---|---|
| winners' actual sells | −15.3% / −32.8% | −7.5% / −10.5% |
| trail15_arm20 (no skill) | −19.9% [−29, −10] / −33.2% [−44, −21] | −5.8% [−15, +3.7] / −6.9% [−24, +13] |
| ES_RED_2_10 | −14.7% / −22.5% | −6.6% / −8.0% |
| ES_VOL_50_10_0 | −14.2% / −23.7% | −5.0% / −8.1% |

**Reading:**
- Same-token matching is the fairer control. It doesn't separate the winners from "a moment on this coin at the same run-up". On b2 the CIs sit on zero, and on b1 they straddle it.
- The cross-token match favours the winners on b1, because their tokens die faster than average.
- A trail with no discretion shows the same or larger post-exit decline.
- **Verdict:** post-exit drift is mostly "these coins keep falling after any price-down exit" (momentum on dying tokens), not timing skill. It's not mean reversion after a pump, because at their sells they're typically underwater, not at a top.
- Caveat: same-token matches exist for only 43/73 (b1) and 88/114 (b2) exits.

## 2) Candle features in the minutes before the sell vs held moments (5 random held moments per trip)
AUC > 0.5 means the feature is higher at sells. Trip-bootstrap 95% CIs.

| feature | b1 sell med / held med, AUC [CI] (n 94 / 375) | b2 sell med / held med, AUC [CI] (n 138 / 516) |
|---|---|---|
| vr3 (3-min vol / peak 3-min vol since entry) | 0.037 / 0.042, 0.50 [0.44, 0.53] | 0.156 / 0.090, **0.57 [0.52, 0.62]** (higher at sells, i.e. NOT roll-over) |
| dd from peak close | −41% / −33%, **0.44 [0.40, 0.48]** | −12% / −8%, **0.43 [0.39, 0.47]** |
| consecutive red candles | 1 / 1, 0.52 [0.48, 0.56] | 1 / 1, 0.55 [0.52, 0.60] |
| upper wick (last / last 3) | 0.49, 0.50 (ns) | 0.53, 0.54 (borderline) |
| run-up from entry | −24% / −13%, 0.45 [0.41, 0.48] | +0.1% / +0.7%, 0.46 [0.42, 0.50] |
| time held | 135 / 100 min, 0.52 (ns) | 98 / 92 min, 0.50 (ns) |
| 1-m vol / 15-m avg | 0.51 (ns) | 0.51 (ns) |
| 5-min return | 0.47 (ns) | 0.40 [0.35, 0.46] |

The only feature that replicates is "sells come deeper below the peak" (AUC ~0.43-0.44, small effect, Cohen's d −0.2 to −0.3). That's what a trailing stop already does. Volume roll-over does **not** precede sells. On b2, volume is *higher* at sells, consistent with selling into activity or alongside other sellers.

## 3) Pre-registered rules on the winners' own entries (families fixed from b1 features, picked on b1, tested on b2 + date split)
- **Families:** VOL (3-min vol < X × peak AND close ≤ peak × (1−y), armed at +z): X 0.15/0.3/0.5, y 0.1/0.2/0.3, z 0/0.2. RED (≥k red candles AND close ≤ peak × (1−y)): k 2/3/4, y 0.1/0.2/0.3. UW (close ≤ entry × (1−u) after h min): u 5/10/15%, h 15/30/60.
- **Common settings:** hard stop −25%, 6 h max, entry at t+10 s close.
- **Date split:** cut 2026-10-19 16:41Z (latest 30% of pooled trips).

| exit | b1 per trip [CI] n=118 | b2 per trip [CI] n=185 | early / late | score |
|---|---|---|---|---|
| winners' ACTUAL | +86% [+19, +192] | +18% [−3, +48] | +52% / +28% | (not a rule) |
| fixed SL25/TP50/2h | −6.4% [−13, +0.7] | −5.7% [−9.9, −1.5] | −7.2 / −3.2 | 9/25 |
| trail15_arm20 | −2.9% [−11, +5.8] | −5.4% [−11, +0.2] | −4.2 / −5.1 | 11/25 |
| **ES_RED_2_10** (best RED on b1) | −6.1% [−14, +2.8] | −3.3% [−8.9, +3.3] | −4.4 / −4.4 | 10/25 |
| **ES_VOL_50_10_0** (best VOL on b1) | −6.0% [−14, +3.5] | −4.2% [−9.9, +2.3] | −4.5 / −5.8 | 10/25 |
| ES_UW_5_30 (best UW on b1) | −17.1% [−26, −6.7] | −9.5% [−17, +0.8] | −11 / −16 | 9/25 |

- **Rule count:** 36 rules + 2 baselines, all negative on b1, b2 and both date halves. Scores are 9-10/25.
- **Neighbours:** all neighbours are also negative, so no rule is a lucky number. It's flat failure.
- **Picked rules (pooled n=303):**
  - ES_RED_2_10: −4.4%, CI [−9%, +1%], MC DD p95 ≈ 100% of $100 at $5 stake, 8/29 nights profitable, net ex best trade −$84.
  - ES_VOL_50_10_0: −4.9%, CI [−10%, 0%].
- **Extra OOS, CR30 copy-replay first buys** (n=28 with ≥ 2 h candles, survivor-biased because the leader held ≥ 2 h):
  - trail15_arm20 +7.7% [−9, +25]
  - RED_2_10 +3.6% [−8, +17]
  - VOL_50_10_0 +0.6% [−17, +17]
  - UW_5_30 −17%

  The ES rules don't beat the trail there either. Scout-cluster entries weren't used because they overlap the b1 wallets. Selfcopy live entries weren't used because the cached bars there carry no volume.

## Does anything meet the candidate bar?
**No.** Every row: score ≤ 11/25, OOS mean < 0, CI includes or sits below 0, in-sample P&L < 0.

## WHY THIS COULD FAIL (this conclusion)
- **1-m OHLCV ≠ order flow.** Real sell-side flow (seller count, a large holder's sell, dev/insider wallet activity) could still precede their sells, and the candles can't see it. The negative here is for *candle-only* signals.
- **Sell times are approximate.** `exit_time` is one timestamp per round trip (the last/main sell). Partial sells (n_sells > 1) are collapsed, so pre-sell features may be measured after an earlier partial sell.
- **Coverage is thin.** Only 73/141 (b1) and 114/246 (b2) exits have ≥ 30 m of post-exit candles; dead pools drop out. Same-token matches exist for only 59-77% of exits.
- **Point-in-time drift.** The drift uses the close of the candle containing the time (≤ 59 s look-ahead), applied identically to exits and baselines.
- **Who's on the other side:** buyers of dying memecoins. Exiting on weakness is just not being them; it isn't an edge you can harvest with mechanical exits on these entries.

## Sample-size honesty
- 303 trips with candles pooled, 29 nights, 8 wallets, mostly 10-09 to 10-23.
- Batch 2 wallets are LOW confidence and selected on profitability.
- AUC differences of ±0.05 are within what 94-138 exits can resolve.

## Next
Close the winners' exit lead for candle data. Reopen it only if Scout gets per-swap flow for the 8 wallets' tokens (seller count, top-holder sells in the 5 min before their exits). Don't spend Lab API budget on it.
