# Lab METHOD (adopted 2026-10-23, Zero). Every scheduled run and every new idea follows these rules.

## Hard rules
- PAPER ONLY. Never trade, move funds, touch wallets/keys, or edit other bots' files. Everything outside /workspace/lab is read-only
  (runner-radar: never edit scan.py, signals.jsonl, live/). No X reads, no posting.
- Rate limits: DexScreener/GeckoTerminal ~30/min shared with the radar -> Lab stays <= ~9/min (6.5 s spacing), caps calls per run, caches everything.
  Scout's rugcheck_creator.py: <= 3 runs per pipeline run, sequential, re-use Scout's 10-min cache.
- Costs always on: 2% fee per side + $0.05/tx, slippage 0.5% + 2 x size/pool liquidity (liquidity decays ~sqrt(price) between polls),
  stops that gap through fill at the candle CLOSE, stop checked before target in the same candle, rugs recover <= 10%, max 3 open, flat by 08:00 Dublin.
- Strictly point-in-time: a decision at t uses only data stamped <= t (intel snapshots, liquidity polls, Scout verdicts captured <= 15 min after the signal).
  Anything that is not point-in-time is labelled OPTIMISTIC (e.g. GUARD_replay on pre-guard rows).
- Time-based holdout: latest 40% of candidate time is out-of-sample (fixed holdout_start once ~3 nights exist). Tune only in-sample.

- Team rule: Lab may read teammates' files freely but never edits them and never instructs any trading bot to change settings.
- Copy-trading tests: copyfomo stop -25% fills ~5 pts worse (gap -> candle open - 5 pts); chase cap is swept (10/15/25%), not on/off.

## Scoring (1-5 each, total /25) -> leaderboard columns sc_*, score_total
| criterion | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| sc_oos_risk: OOS mean/stdev per trade | <=0 or < 2 OOS trades | <0.1 | <0.2 | <0.35 | >=0.35 |
| sc_drawdown: Monte-Carlo p95 max DD (% of $100 equity) | >50% | <=50% | <=30% | <=20% | <=10% |
| sc_trades: closed trades | <10 | 10-24 | 25-49 | 50-99 | >=100 |
| sc_edge: after-cost mean return | <=-5% | >-5% | >0 | >+5% | bootstrap 95% CI low > 0 |
| sc_stability: share of profitable nights (walk-forward by Dublin night; needs >= 3 nights else 1) | <30% | >=30% | >=50% | >=60% | >=80% |

**Candidate** = score_total >= 18 AND >= 50 trades AND holds_out_of_sample = "yes" (>= 20 OOS trades, in-sample P&L > 0, OOS mean > 0 and OOS CI low > 0).

## Robustness
1. Neighbour sweeps for every promising rule ([[sweep]] in config.toml: survival wait 15/20/30/45 min, stop -15/-25/-35%, age gate 0-90 min,
   score 50-65, guard rules on/off). `lucky_number = yes` when a profitable setting has an unprofitable neighbour -> do not adopt.
2. Monte Carlo: 1,000 reshuffles of trade order -> mc_dd_p5/p50/p95 (drawdown as fraction of equity).
3. `net_ex_best_trade`: P&L without the single best trade. If that flips the sign the "edge" is one lottery ticket.
4. Every candidate (and every profitable non-candidate in the report) gets **WHY THIS COULD FAIL** + **who is on the other side**.
5. Prefer boring, robust rules (few parameters, wide plateaus) over the top of the table.
6. Multiple testing: `variants_tried` (data/variants_tried.json, distinct variant configs ever run) is printed in every leaderboard/report.
   The more variants tried, the more the best one is expected to look good by luck.

## Reporting
- Daily report reports/lab-YYYY-MM-DD.md (Dublin date), guarded-radar section first, guard evaluation (out/guard_eval.md), leaderboard, candidates.
- Sundays: weekly review: what survived OOS, paper (Chunk paper-buys) vs backtest (GUARD_live), what decayed vs last week's snapshot
  (out/history), one to double down on, one to drop.
- Labels: relabel.py gives every scanned token a FINAL label 24 h after its first scan (RUG / dead / survivor / runner); before that
  labels are PROVISIONAL and must be called so.
- Never promote anything to live; proposals only. Chunk live buys stay paused until a candidate exists.

## Copy candidates (copy_candidates.py)
- Simulate copyfomo exactly: first buy per coin, skip leader buys < $50 and mcap < $100k, TP +100% sell half, SL -25% filled 5 pts worse, or the stop candle's close if it closes below the stop (TRUTH calibration: real stop $0.000293 = 20:46 UTC 1-min close), chase cap 15%, 3-10 s delay on 1-min candles (approximation), remainder with leader, 2%/side + slippage.
- Without 1-min candles a trade is 'approx' (round-trip only) and flagged. Telegram bot times are UTC-4.
- Stake test: concurrency + running intra-night realised loss vs 20% nightly limit; MC over nights (historical, and 5-traders-fire extrapolation). Recommend the largest stake with P(limit) <= 5%.
- 2026-10-23 recalibration (TRUTH, n=1): central stop = 2.5% below the -25% trigger, copyfomo 2%/side inside P&L, $0.03 gas/round trip (gives -30.5% vs real -29.9%). Conservative band = 5% below trigger + never better than the crash candle close (gives -38 to -40%). Report both.
