# Track C first read: SOL Up-or-Down on World, via Phantom (2026-10-23)
**Paper and research only. Ireland is RESTRICTED by World, so do not trade it live** (see compliance-and-costs.md and ../../world-execution.md).
**Main caveat:** World market prices could not be read (the API is gated), so every test uses Binance SOLUSDT 1m data as a proxy. At window open the price is assumed to be 0.50. At later entries the market is assumed to sit at model fair value. Cost = 1c half-spread + Phantom fee 0.1·p·(1−p), which means 53.5% break-even at 0.50. In-sample (IS) is Jan–Jun 2026; out-of-sample (OOS) is 1 Jul – 22 Oct 2026.

## 1. Headline: 15m confluence strategy (the main market)
Rule: bet in the trend direction only when **all** of these agree: the 15m trend (close vs EMA50, plus EMA50 slope) and the 1h trend agree; a break of the prior 20 or 48-bar high or low on 15m happened within the last 3 bars, with the close beyond the level and volume > 1.2× or 1.5× its 20-bar average; 3-bar momentum agrees; and ADX14 > 20 or 25 (the chop filter). This reuses the Track A/B building blocks (EMA trend, pivot/level break, volume confirmation), rebuilt on 1m-aligned bars. Script: src/confluence.py. Full grid: confluence_results.csv.

OOS results, hold to settlement, EV per €1 contract:
| Entry | Confluence (8 nearby settings) hit / EV | Coin flip | Follow market favourite |
|---|---|---|---|
| Window open | **45.3–46.1% / −0.075 to −0.082** (n 455–764) | 50.3% / −0.032 | 49.0% / −0.045 |
| +2m | 45.3–46.1% / −0.073 to −0.084 | 50.3% / −0.031 | 62.9% / −0.028 |
| +5m | 45.3–46.1% / −0.064 to −0.073 | 50.3% / −0.030 | 71.1% / −0.014 |
IS is the same story (46.5–48.5% hit, EV −0.04 to −0.07, 0–1 of 6 months positive). OOS: **0 of 4 months positive at every setting.** Worst losing streak is 9–13.
- **With cash-out rules**, OOS: lock at bid ≥ 0.90 makes it worse (EV −0.079 to −0.092). Cutting when fair < 0.20 is about equal to holding (−0.062 to −0.080). Neither fixes it.
- **Interpretation:** confirmed 15m breakouts with trend and momentum **mean-revert inside the next 15m window**. That matches the earlier opening-entry test, where mean reversion was best (52.1% OOS). The confluence rule is therefore *worse than a coin flip*.
- **Fade hypothesis (post-hoc, not proposed):** betting against the signal gives about 53.5% IS (break-even) and 54.5% OOS (≈ +0.9c per contract). That is too thin, it was chosen after seeing the data, and a 1–2c wider spread wipes it out.
- **Bets per day** (setting 20/1.5/ADX20, all of Jan–Oct 2026, 294 days): **6.5 per 24h**, and **about 1.8 per night** from 18:00–02:00 Dublin. By Dublin hour, per night: 18h 0.26, 19h 0.21, 20h 0.17, 21h 0.15, 22h 0.21, 23h 0.32, 00h 0.27, 01h 0.19. The peak is 14–16h Dublin (US open), at about 0.5 per hour. Full table: bets_per_hour_15m.json.

## 2. 1h (second market) and 5m (baseline)
- **1h confluence** (4h trend filter, entries at open, +5m and +10m). ADX>20 variants lose in both IS and OOS. ADX>25 variants are **+0.5 to +0.9c OOS** (54.0–54.4% hit, n 125–153, worst streak 4–5, 2–3 of 4 months positive) but **−4 to −8c IS** (45–48% hit). The sign flips between periods, so this is regime luck, not a stable edge.
- **5m baseline** (opening-entry test, src/spot_backtest.py): the best OOS rule is mean reversion with a 15m lookback, at 51.4% hit, below break-even. Momentum, EMA trend and their combination are all ≤ 50.5%.

## 3. Rubric (5 points each: OOS, worst streak, trade count, profit after costs, consistency)
| Idea | OOS | Streak | Trades | Profit | Consistency | Total |
|---|---|---|---|---|---|---|
| 15m confluence (best setting) | 0 | 3 | 5 | 0 | 0 | **8** |
| 15m confluence + cash-out | 0 | 3 | 5 | 0 | 0 | 8 |
| 1h confluence, ADX>25 | 1 (IS negative) | 4 | 4 | 1 | 1 | **11** |
| Opening-entry mean reversion (15m, 30m lookback) | 1 | 3 | 5 | 0 | 0 | 9 |
| Fair-value gap trading | n/a, no market prices | | | | | untestable |
**No idea reaches 18/25. Nothing is proposed.** Each finalist would need 18+, 50+ trades and stability at nearby settings; none qualifies.

### WHY THIS COULD FAIL (even if a version looked positive)
- **The other side is a professional RFQ maker**: JanusFI (World's own) and BisonFI. They quote off Chainlink Data Streams and faster CEX feeds and widen spreads when flow becomes predictable. A retail Phantom tap, with 1–3s latency and whole contracts, gets picked off.
- Settlement uses a **Chainlink TWAP**, not the Binance last price. Every proxy outcome here can differ near the target.
- The interface fee plus spread (≈ 3.5c at p=0.5) is larger than every edge found.

## 4. Fair-value model and checkpoints
P(Up) = Φ(ln(spot/target)/(σ₁ₘ√minutes_left)), with σ from a 60m rolling stdev. OOS calibration (fairvalue_calibration.csv) beats the coin flip's Brier score of 0.25 at every checkpoint:
| Window | Checkpoint | Brier | Favourite accuracy vs predicted |
|---|---|---|---|
| 15m | 10m left | 0.190 | 71.2% vs 69.6% |
| 15m | 5m | 0.126 | 82.1% vs 79.6% |
| 15m | 3m | 0.096 | 86.8% vs 84.1% |
| 15m | 2m | 0.077 | 89.7% vs 87.0% |
| 15m | 1m | 0.055 | 92.8% vs 90.7% |
| 1h | 10m / 1m | 0.086 / 0.026 | 88.0% / 96.6% |
| 5m | 3m / 1m | 0.182 / 0.102 | 72.6% / 86.2% |
The model is slightly underconfident (by 1.5–2.7pp). **The 30s checkpoint was not testable**, because only 1m bars are available. Market-vs-fair gaps **could not be measured** without World prices. The follow-market baseline above assumes an efficient market, so it is the "zero skill" line.
- **Screenshot sanity check** (3:16 left, 0.16% below target, Up at 26%): fair Up is 6.5% at median vol and 20.9% at p90 vol. So 26% is only fair in a high-vol regime, or the TWAP is already partly fixed. At 24s left and 0.56% below target, fair Up is ≈0. An Up price of 2c is rich; Down at 0.98 has about 1.8c edge before TWAP risk and fees.
- **Effective fee from payouts:** 3.8x at 26% and 1.4x at 74% imply prices of 0.263 and 0.714, which sum to 0.977 on the payout side. Together with the ~2.16% overround Chainstack decoded, the all-in cost is about 1–3c per contract.

## 5. Cash-out (exit rules, 15m and 5m, mean-reversion entry, 60s re-checks)
OOS hold EV is −0.022 (1c half-spread) and −0.032 (2c). (a) bid > fair+0 is about equal to holding; +2c and +5c never fire, because the proxy bid is fair minus the spread. (b) Lock at 85–90% is worse: −0.025 to −0.053. (c) Cut is about equal to holding. 0 of 4 OOS months are positive. 10–15s re-checks were not testable with 1m data.

## 6. Caveats
Binance is a proxy for the Chainlink TWAP. Ties (close = open) count as Down. Rechecks are every 60s. No real depth data: a 1c half-spread is assumed, and real cash-out depth may be zero. The ledger holds only proxy trades (ledger.jsonl, 2,424 rows plus a META record).

## Files
reports/compliance-and-costs.md · reports/first-read.md · reports/confluence_results.csv · reports/bets_per_hour_15m.json · reports/fairvalue_calibration.csv · reports/opening_entry.csv · reports/cashout_sim.csv · ledger.jsonl · src/confluence.py · src/spot_backtest.py · src/cashout_sim.py · data/support_articles.md · ../world-execution.md
