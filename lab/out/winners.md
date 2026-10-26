# Learning from winners (WN_), phase 2: PAPER ONLY

_Generated 2026-10-24T01:16Z. Data: Scout winners/ batch 1 (4 wallets, 141 closed trades, partial). Code: wn_fetch.py, wn_profile.py, wn_rules.py, wn_report.py. Pre-registration: notes.md '2026-10-24T00:55Z winners (WN_)'._

## Plain answer

**No rule distilled from the winners clears costs out of sample. No WN_ candidate.** The sample is tiny: 141 trades from 4 wallets, and only 64 of them won after 5% costs. Every pattern below rests on 10–60 trades and was picked on outcome, so treat each one as a hypothesis, not a finding. Turned into mechanical rules and run on ~199 graduated tokens the winners did NOT trade, the best rule (R2: fresh 5m pop, not already up >50% in 1h) loses about 5–8% per trade. That beats random entries (about −10 to −13%) but is still negative at 4.7% costs, and its 95% CI includes zero on the losing side. Excluding the nights the winners traded leaves too few trades (n ≤ 5) to say anything.

## 1. What separates winning from losing entries (inside the 141; outcome-selected, small n)

| feature | winners n | winners median | losers n | losers median |
|---|---|---|---|---|
| age_at_entry_h | 64 | 1.75 | 77 | 1.53 |
| mcap_at_entry_usd_approx | 64 | 37629.0 | 76 | 80132.5 |
| vol_1h_usd | 52 | 41480.5 | 69 | 102582.0 |
| vol_6h_usd | 52 | 61340.5 | 69 | 186567.0 |
| chg_5m_pct | 40 | 27.885 | 59 | 27.19 |
| chg_1h_pct | 25 | 31.2 | 38 | 100.75 |
| n_1m_candles_30m | 64 | 6.0 | 77 | 18.0 |
| up_share_1m_30m | 17 | 0.533 | 37 | 0.533 |
| size_in_usd | 64 | 305.14 | 77 | 1500.0 |
| hold_min | 64 | 26.55 | 77 | 60.1 |
| smart_co_buys_30m | 64 | 0.0 | 77 | 0.0 |
| avoid_co_buys_30m | 64 | 0.0 | 77 | 0.0 |
| n_buys | 64 | 1.0 | 77 | 2.0 |
| n_sells | 64 | 1.0 | 77 | 1.0 |

Notes:
- Winning entries were in smaller (median mcap ≈ $38k vs $80k), quieter tokens: less 1h volume and fewer active 1m candles in the prior 30 min. They had *less* prior-1h run-up (n=25 vs 38 with data). **But the mcap gap is mostly a wallet-mix effect:** neodot trades about $7k curve coins and wins 24/40. Within each wallet the direction is mixed (benji's winners were the *bigger* coins), so a pooled 'small mcap wins' is not a dependable pattern.
- Clustering: smart_co_buys_30m is 0 at the median for both groups. Winners did not need other smart wallets in the token.
- No data for liquidity, holders or holder growth at entry: Scout's fields are BLANK because there are no free historical snapshots. Untested.
- X buzz is untestable: x-intel first-mentions.jsonl starts 10-23 and mentions 0 of the winners' 141 mints.
- Pump.fun-curve entries: 48 trades, 27 wins, median 10.78%. Post-migration: 93 trades, 37 wins, median -15.92%. (Most of the curve entries are neodot's.)

Per wallet (median mcap: winners / losers; median hold min: winners / losers):

- benji: 11W/21L; mcap 1201636.0 / 589884.0; hold 273.3 / 14.6
- bystevenr: 18W/20L; mcap 68544.5 / 80132.5; hold 76.75 / 198.15
- neodot: 24W/16L; mcap 7410.5 / 6285.0; hold 9.65 / 66.4
- onlyzhynx: 11W/19L; mcap 35396.0 / 44795.0; hold 2.4 / 23.4

## 2. Entry timing vs random entries on the same tokens (GT 1m candles)

Trades with usable candles around entry: 118/141. All figures are net of 5%.

- Their actual trades: n=118, mean +0.858, median -0.132, CI [+0.18, +1.91], win 0.415
- Their actual trades, each capped at 10x (to compare with random): n=118, mean +0.475, median -0.132, CI [+0.15, +0.84], win 0.415
- Random time on the same token (±5 min–4 h), same hold: n=502, mean +0.059, median -0.050, CI [+0.01, +0.12], win 0.267
- Their entries with a fixed SL25/TP50/2h exit: n=117, mean -0.070, median -0.300, CI [-0.14, +0.00], win 0.376
- Their entries with a fixed SL20/TP30/30m exit: n=117, mean -0.069, median -0.114, CI [-0.12, -0.02], win 0.427

**Read:** with fixed exits, their entries lose about 7% (the CI sits at or below 0). That is no better than this universe's random entries (−10 to −13%) by any margin worth trading. Their real results come from **exit and hold discretion**: letting a few runners go and cutting or flipping the rest. Entry selection alone does not carry the edge. Random-time windows on the same tokens include the pre-entry run-up, so that baseline is generous to random.

## 3. Exits

- Price 30 min after their exit vs exit price: n=78, mean -0.164, median -0.146, CI [-0.24, -0.08], win 0.308
- 120 min after: n=63, mean -0.328, median -0.341, CI [-0.43, -0.22], win 0.206
- Baseline, random time on the same tokens, 30 min forward: n=496, mean +0.094, median -0.012, CI [+0.05, +0.15], win 0.351; 120 min: n=466, mean +0.466, median -0.019, CI [+0.30, +0.65], win 0.429
- **Read:** after their exits the price keeps falling (median −15% at 30 min, −34% at 2 h; it rises after only 21–31% of exits). Random times on the same tokens give a median of about −1 to −2%. Their exits are well timed. That is a real skill, but it is discretionary: no simple rule here reproduces it. The default/quick fixed exits on their own entries lose.
- By hold time (net5 %, n / wins / median): >=720: 32/11/-23.42; <30: 24/10/-20.8; <120: 25/9/-14.04; <2: 16/12/39.685; <10: 23/12/0.03; <720: 21/10/-6.95
- Holds under 2 min win 75%. That is outcome-driven (fast flips of tokens that popped) and can't be used as a rule.

## 4. Time of day (Dublin, entry) and size

| bucket | n | wins | median net5 % | mean net5 % |
|---|---|---|---|---|
| 00-04 | 37 | 15 | -19.63 | 158.93 |
| 04-08 | 17 | 9 | 7.85 | 63.34 |
| 08-12 | 9 | 4 | -5.98 | 129.81 |
| 12-16 | 2 | 1 | 1.66 | 1.66 |
| 16-20 | 43 | 20 | -6.95 | 37.12 |
| 20-24 | 33 | 15 | -3.51 | 75.06 |

By entry mcap: <10000: n=34 w=19 med=10.78; <100000: n=36 w=16 med=-17.635; <30000: n=19 w=10 med=0.03; <1e+06: n=38 w=12 med=-20.0; >=1e+06: n=13 w=7 med=26.13

By size (USD): <150: n=28 w=17 med=17.12; <500: n=28 w=19 med=22.05; >=2000: n=47 w=11 med=-25.39; <2000: n=38 w=17 med=-17.94

Means are dominated by a few outliers in every bucket. With 2–43 trades per bucket, no time-of-day effect can be distinguished from noise.

## 5. Rules tested on tokens the winners did NOT trade (held out by date)

Universe: Lab backfill PumpSwap graduations with 1m candles (read-only), 199 tokens after removing 126 winner mints. Holdout = tokens migrating after 10-15 23:44Z. Costs 4.7% (<$1M). $5 stake. First trigger per token.

| variant | trades | mean | 95% CI | OOS n / mean | score/25 | lucky | candidate |
|---|---|---|---|---|---|---|---|
| WN_R1_quiet_small_dflt | 3 | +0.039 | [-0.30, +0.45] | 1 / +0.453 | 12 | n/a | no |
| WN_R1_quiet_small_quick | 3 | -0.030 | [-0.22, +0.25] | 1 / +0.253 | 11 | n/a | no |
| WN_R1_quiet_small_dflt_strictnights | 1 | +0.453 | [—, —] | 1 / +0.453 | 12 | n/a | no |
| WN_R2_fresh_not_chased_dflt | 47 | -0.079 | [-0.19, +0.03] | 17 / -0.057 | 9 | n/a | no |
| WN_R2_fresh_not_chased_quick | 47 | -0.051 | [-0.12, +0.02] | 17 / -0.084 | 11 | n/a | no |
| WN_R2_fresh_not_chased_dflt_strictnights | 5 | -0.269 | [-0.70, +0.15] | 5 / -0.269 | 9 | n/a | no |
| WN_R3_vol_accel_dflt | 19 | -0.196 | [-0.35, -0.03] | 7 / -0.241 | 8 | n/a | no |
| WN_R3_vol_accel_quick | 19 | -0.179 | [-0.31, -0.06] | 7 / -0.186 | 9 | n/a | no |
| WN_R3_vol_accel_dflt_strictnights | 2 | +0.236 | [+0.02, +0.45] | 2 / +0.236 | 17 | n/a | no |
| WN_R1_quiet_small__mcap0 | 7 | -0.131 | [-0.24, -0.03] | 1 / +0.007 | 10 | n/a | no |
| WN_R1_quiet_small__mcap2 | 4 | -0.173 | [-0.62, +0.27] | 1 / +0.453 | 9 | n/a | no |
| WN_R1_quiet_small__n30_max0 | 1 | -0.105 | [—, —] | 0 / — | 9 | n/a | no |
| WN_R1_quiet_small__n30_max2 | 5 | +0.186 | [-0.01, +0.38] | 2 / +0.453 | 19 | yes (WN_R1_quiet_small@n30_max) | no |
| WN_R1_quiet_small__chg600 | 3 | +0.039 | [-0.30, +0.45] | 1 / +0.453 | 12 | n/a | no |
| WN_R1_quiet_small__chg602 | 3 | +0.039 | [-0.30, +0.45] | 1 / +0.453 | 12 | n/a | no |
| WN_R2_fresh_not_chased__chg5_min0 | 59 | -0.029 | [-0.12, +0.06] | 18 / +0.092 | 15 | n/a | no |
| WN_R2_fresh_not_chased__chg5_min2 | 29 | -0.166 | [-0.26, -0.05] | 11 / -0.098 | 9 | n/a | no |
| WN_R2_fresh_not_chased__chg600 | 45 | -0.056 | [-0.16, +0.05] | 15 / +0.022 | 11 | n/a | no |
| WN_R2_fresh_not_chased__chg602 | 51 | -0.074 | [-0.17, +0.03] | 19 / -0.030 | 10 | n/a | no |
| WN_R2_fresh_not_chased__mcap0 | 42 | -0.116 | [-0.21, -0.02] | 13 / -0.103 | 8 | n/a | no |
| WN_R2_fresh_not_chased__mcap2 | 54 | -0.078 | [-0.18, +0.03] | 23 / -0.084 | 9 | n/a | no |
| WN_R3_vol_accel__accel0 | 28 | -0.134 | [-0.26, +0.00] | 11 / -0.162 | 9 | n/a | no |
| WN_R3_vol_accel__accel2 | 11 | -0.121 | [-0.37, +0.11] | 5 / -0.035 | 10 | n/a | no |
| WN_R3_vol_accel__chg600 | 15 | -0.121 | [-0.32, +0.09] | 7 / -0.116 | 10 | n/a | no |
| WN_R3_vol_accel__chg602 | 21 | -0.134 | [-0.29, +0.03] | 8 / -0.249 | 9 | n/a | no |

Random entry, same age window, every universe token: R1_quiet_small/dflt: n=275 mean -0.135; R1_quiet_small/quick: n=275 mean -0.111; R2_fresh_not_chased/dflt: n=280 mean -0.134; R2_fresh_not_chased/quick: n=280 mean -0.103; R3_vol_accel/dflt: n=280 mean -0.134; R3_vol_accel/quick: n=280 mean -0.103

## WHY THIS COULD FAIL / who is on the other side

- **Selection on outcome:** winners/ was chosen for being profitable. Their edge is a few huge outliers: 3 of 4 have a negative median trade. A rule can copy their entry *conditions* but not their discretion: which coin, and when to hold the 10× runner.
- **Small n:** 141 trades; feature contrasts rest on 25–77 trades each, and some fields cover <50%.
- **Universe mismatch:** the backfill universe is post-migration PumpSwap pools only (first ~1000 traded minutes). neodot's curve-phase entries at ~$6.6k can't be replicated there. Post-migration mcap is bimodal (most tokens collapse to about $3k within 2 h).
- **Other side:** for small post-migration pools, the counterparty is the bundlers and early holders unloading into any 5m pop. That's why 'momentum, not chased' still loses after 4.7%.
- **Data:** mcap_at_entry is an approximation (current supply). Liquidity and holders at entry are unavailable. Fills on 1m closes are optimistic.

variants_tried (global) = 783.

Out of scope here (another Lab job): copy-exit and neodot copy replay.