# Survivor momentum: first read (PAPER ONLY), 2026-10-23 ~23:00 UTC

**Bottom line: this cannot be tested yet. All radar history is 12 signals over about 1 hour (20:07–21:03 UTC) on one night, and exactly one coin (BITCHES) passes any cell of the grid. Every number below is one trade, the coin the rule was built from. That is n=1 hindsight, not evidence.** Nothing here is a candidate; every row's score is 5–13 out of 25.

## Data and universe
- Radar history in full: scan.log and scanned.jsonl start 20:07Z tonight, with ~20 scans so far and **12 signals**, all on **Dublin night 2026-10-23** (none on any other night). No signal was ever rescanned.
- Point-in-time liquidity sources (observation time must be ≤ the check time and ≤ 15 min old, same pair only):
  - radar scan rows
  - Lab DexScreener polls (data/liq_polls.jsonl, which start at 21:09Z)
  - Chunk's live check lines in trades-log.md (Dublin time converted to UTC)
  - Chunk's paper-buys.jsonl
- The check time is the first 5-minute candle open at or after signal+T. That candle's open is both the decision price and the fill (plus slippage).
- **Liquidity coverage:** 0 of 12 signals were excluded for missing liquidity. Every signal without a liquidity observation had already failed on point-in-time candle price: it was down, or the coin was dead with no trades. So the missing early liquidity polls did not change any decision. The `_LIQEST` (sqrt-model) row is labelled ESTIMATE. It is shown only for completeness: a constant-product estimate cannot see LP adds, so it reduces to "price up".
- **Scout avoid list:** I used the oc_avoid snapshot valid at the check time, matching on token, creator, and top holders captured ≤ 15 min after the signal. Before 20:50Z no list existed, so those checks pass as "no list yet". BITCHES was **clear** at every check.
- **Sanity filter** (fixed before running, not tuned): liquidity ≥ $20k and mcap/liq ≤ 20. It never decided anything, because the nosanity ablation gives the same result.
- **Exits:** unchanged `backtest.simulate`. Stop at −25% with gap-through fills, half sold at 2x, 2% fee per side, $0.05 per transaction, slippage of 0.5% + 2×size/liq, max 3 open, flat by 08:00 Dublin. Bet size is $10.

## Results grid: entry T min after signal; buy if liq ≥ +X% vs signal AND price > signal, price ≤ cap
Each cell shows the coin that passed, its return after costs, and the score out of 25. Pass count is out of 12 signals.

| T | X (liq up ≥) | cap none | cap +100% | cap +200% |
|---|---|---|---|---|
| 20m | 0% | BITCHES +29% (stop) · 13/25 | BITCHES +29% (stop) · 13/25 | BITCHES +29% (stop) · 13/25 |
| 20m | 20% | BITCHES +29% (stop) · 13/25 | BITCHES +29% (stop) · 13/25 | BITCHES +29% (stop) · 13/25 |
| 20m | 40% | 0 pass | 0 pass | 0 pass |
| 30m | 0% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 30m | 20% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 30m | 40% | 0 pass | 0 pass | 0 pass |
| 45m | 0% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 45m | 20% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 45m | 40% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 60m | 0% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 60m | 20% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |
| 60m | 40% | BITCHES -30% (stop) · 9/25 | 0 pass | BITCHES -30% (stop) · 9/25 |

Body-only stop (wicks ignored; sensitivity):

| T | X | cap none | cap +100% | cap +200% |
|---|---|---|---|---|
| 20m | 0% | BITCHES +101% (open (marked)) | BITCHES +101% (open (marked)) | BITCHES +101% (open (marked)) |
| 20m | 20% | BITCHES +101% (open (marked)) · 5/25 | BITCHES +101% (open (marked)) | BITCHES +101% (open (marked)) |
| 20m | 40% | 0 pass | 0 pass | 0 pass |
| 30m | 0% | BITCHES +25% (open (marked)) | 0 pass | BITCHES +25% (open (marked)) |
| 30m | 20% | BITCHES +25% (open (marked)) · 5/25 | 0 pass | BITCHES +25% (open (marked)) |
| 30m | 40% | 0 pass | 0 pass | 0 pass |
| 45m | 0% | BITCHES +40% (open (marked)) | 0 pass | BITCHES +40% (open (marked)) |
| 45m | 20% | BITCHES +40% (open (marked)) | 0 pass | BITCHES +40% (open (marked)) |
| 45m | 40% | BITCHES +40% (open (marked)) | 0 pass | BITCHES +40% (open (marked)) |
| 60m | 0% | BITCHES +45% (open (marked)) | 0 pass | BITCHES +45% (open (marked)) |
| 60m | 20% | BITCHES +45% (open (marked)) | 0 pass | BITCHES +45% (open (marked)) |
| 60m | 40% | BITCHES +45% (open (marked)) | 0 pass | BITCHES +45% (open (marked)) |

Notes on the grid:
- Body-only stop rows are scored 5/25 because the trade is still open (0 closed trades). Only 3 of these cells are on the leaderboard.
- In every cell, **11 of the 12 signals fail on price at every T**: down, or dead. The one exception is **TRUTH at T20 and T30**. It was up 10–19% on price but its liquidity was −8%, so it failed the liquidity leg.
- **The liquidity leg removes nothing that price alone doesn't already remove, except TRUTH.** TRUTH peaked at +117%, so on this night the liquidity rule *cost* a potential 2x.
- **T20 / X40 fails BITCHES by 0.3 points**: its liquidity was +39.7% (Chunk's 21:03Z read).
- **Cap +100% kills every cell from T30 on.** BITCHES was at +164%, +135% and +127% at those checks.
- Hit rate is 100% (6/36 grid cells), 0% (18/36), or no trades (12/36). The bootstrap CI on one trade is a point, e.g. T20 [+0.29, +0.29]. It is meaningless and I'm reporting it only because it was asked for.
- **P&L excluding the best trade is $0 in every cell.**
- The T20 cells' 13/25 is inflated: `sc_edge=5` and `sc_drawdown=5` come trivially from a single winning trade. `sc_trades`, `sc_oos_risk` and `sc_stability` are all 1.

**The stop is a single wick.**
- Under the standard engine, BITCHES at T20 enters at +53% (21:05 open, liq +40%). It sells half at 2x in the 22:15 candle, then the 22:20 candle wicks to **−32% vs signal** (open +204%, close +188%) and stops the rest at the stop level.
- Every later entry (T30–60) is stopped by that same print, for −30%.
- With body-only stops (sensitivity, wicks ignored) BITCHES is still open, marked at the 22:55 candle (+249% vs signal): T20 **+101%**, T30 +25%, T45 +40%, T60 +45%.
- Whether a real stop fills on a 1-candle −90% wick on a pump.fun pool depends on execution, and the radar's own grader also marks BITCHES "stopped". So the sign of the result hinges on how that one print is modelled.

## Broader universe (sensitivity: first non-rejected scan row per coin, score ≥45, 27 coins)
- **T30/X20/cap100 buys KIMCHICITY**: score 49, price +67%, **liq +42%** at check, scan-row liquidity, no Scout list yet. It then **rugs −99.5%** with a gap-through. That is exactly the "liquidity add as bait" failure.
- T20/X20/no-cap buys only BITCHES (+29%). KIMCHICITY's liquidity was +17%, so it missed X20.
- So outside the 12 signals, this rule's first and only fresh pick was a rug.

## Hold-out
- **There is no real hold-out.** It is one night and one hour of signals.
- The pre-registered METHOD split (latest 40% of radar time, ≥ 21:03:28Z) contains only DROOLING and GTA6 Coin. Both fail every cell, so **n_out = 0 everywhere** and every row is `holds_out_of_sample = insufficient`.
- Time halves (pre-registered at the signal-time midpoint, 20:35:16Z):
  - First half: 7 signals, **0 passes** in any cell.
  - Second half: 5 signals, BITCHES only.
- Neither half can confirm anything.

## Neighbour sweep and lucky-number flag
- Families run along T, X and cap around the pre-registered centre T30/X20/cap100. That centre cell itself makes **0 trades**.
- No cell reaches the 5 trades that `lucky_flags` needs, so every flag is "n/a (<5 trades)".
- Read informally, it is the textbook lucky-number pattern:
  - Profit exists only at T20, with X ≤ 39.7% (an X40 neighbour gives 0 trades).
  - T30 is −30% and T30 with cap100 is 0 trades.
- **Treat any positive cell as a lucky number.**

## WHY THIS COULD FAIL
1. **Hindsight from one coin.** The rule (liq up + price up after 20 min, no chase cap) was written after watching BITCHES run, and BITCHES is the only coin that passes. It is fitted to its own training example.
2. **Selection on the single winner.** "All 11 losers had falling liquidity" is true. But price alone already separates them, since all 11 were down or dead at T20. The liquidity condition has no independent evidence for it. Its only independent act tonight was rejecting TRUTH, which then ran to +117%.
3. **Liquidity adds as bait before a pull.** A dev or bundler can add LP to make the pool look healthy and then pull it. KIMCHICITY (liq +42%, then −99.5%) did exactly that in the broader set. DexScreener "liquidity" is also a quoted USD value that rises mechanically with price on one-sided pools. So "liq up and price up" is partly one fact counted twice.
4. **Who is on the other side.** A buyer at +50–160% after 20–60 minutes is exit liquidity for the snipers and bundle wallets that bought at launch. Tonight's avoid list already holds two dev-bundle creators (YMB, CI).
5. **Execution.** Results flip on one 5-minute wick (stop vs no stop). Entry slippage on a pool with ~$100k of liquidity is small at $10, but would not stay small at real size.
6. **Sample.** 1 trade. At least 50 trades are needed for candidate status and ≥ 20 out-of-sample trades for a hold-out. At tonight's rate (1 pass per 12 signals), that is **~600 signals**, or many weeks of radar.

## What was added
- `survivor_momentum.py` is a new module. It does no network calls by default; `--fetch` fetches GeckoTerminal candles for uncovered pairs, at most 8 calls, 12 s apart.
- Outputs:
  - `out/survivor_momentum.json`: per-cell decisions, the reason each coin failed, and the liquidity observation table.
  - `out/sm_trades.csv`
  - `out/leaderboard_extra_SM.json`: **44 SM_* rows**, made of 36 grid + 5 ablations (nosanity, noscout, LIQEST, 2× broad45) + 3 body-stop.
- **variants_tried: 127 → 204**, adding all 77 configs run (the 36 body-stop cells included).
- Changes made under `out/.pipeline.lock`, with backups `out/*.bak-sm`:
  - `backtest.py`'s disabled extra-rows merge now globs **only** `out/leaderboard_extra_SM*.json`. Polymarket rows stay unmerged.
  - `run_pipeline.sh` runs `survivor_momentum.py` (no args, no network) just before backtest.
- backtest and report were re-run OK, and leaderboard.csv now has 106 rows.
- One GeckoTerminal call refreshed BITCHES candles, which are cached.
- Untouched: copy_candidates.py, runner-radar (read-only), and live/.
