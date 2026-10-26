# Polymarket 1h / 4h BTC-ETH Up-or-Down — complete-set accumulation (PAPER SIM ONLY)

Status: **research sim on public data. No account, no wallet, no orders.** Data: Gamma `/events?series_slug=…` (listings and resolution)
plus the public data-api trade tape `data-api.polymarket.com/trades?market=<conditionId>&takerOnly=true`. Everything is cached under `cache/`.
5m and 15m markets are excluded, as asked.

## What was tested
- Universe: the last 7 days of closed markets (Oct 16–23 2026): 167 BTC-1h, 167 ETH-1h, 42 BTC-4h and 42 ETH-4h (418 markets).
  Median taker volume: BTC-1h ≈ $25k, ETH-1h ≈ $3.7k, BTC-4h ≈ $10.7k, ETH-4h ≈ $2.6k.
- Fees: these markets use `crypto_fees_v2` (rate 0.07, **taker-only**). Our orders are passive, so the maker fee is 0. Maker rebates are ignored, which is conservative.
- Strategy (`sim.py`). The bot acts only at check times, every 5, 10 or 15 min, starting 30 min before the candle opens:
  1. Rest a bid at `b` on both Up and Down (a side is skipped if it already trades at or below b+1c).
  2. When one side fills (leg 1), at the **next** check cancel the other b-bid and rest leg 2 on the other side at `min(T−b, last−1c)`.
     If both b-bids fill between checks, that counts as a pair at 2b.
  3. Pair complete → start again (max 3 pairs per market, 10 shares per leg). An unmatched leg 1 is held to resolution.
- Fill realism on the taker tape. An Up bid at L can be hit by a taker SELL of Up at ≤ L or by a taker BUY of Down at ≥ 1−L (mint match). There are three fill models:
  - `touch`: any print at our level fills us (optimistic).
  - `queue50` / `queue200`: prints *at* our level first use up 50 or 200 shares queued ahead of us; a print *through* our level fills us. Live CLOB books showed median resting size ≈ 20–100 shares per level between 0.40 and 0.48 (`data/book_snapshots.jsonl`).
  - `through`: only prints strictly through our level fill us.
- Grid: b ∈ {.40,.42,.44,.46,.48} × T ∈ {.94,.96,.98} × check ∈ {5,10,15} min × 4 fill models × {1h,4h} = **360 variants tried**.
  The leaderboard gets the headline row set only (check 10 min, T .96, queue50, five b values per horizon = 10 rows, `PMUD_*`). The full grid is in `out/grid.json` and `out/scorecard.md`.

## Result: does not work. 0 of 360 variants are profitable.
| headline (c10, T.96, queue50) | markets with fills | pairs | avg pair cost | leftovers | leftover $ | pair $ | net $ | mean ret/market | score |
|---|---|---|---|---|---|---|---|---|---|
| 1h b.44 | 326 | 398 | **0.916** | 141 | −550 | +334 | **−216** | −0.21 [CI −0.25,−0.16] | 9/25 |
| 4h b.44 | 79 | 123 | **0.947** | 38 | −167 | +65 | **−102** | −0.20 [CI −0.28,−0.12] | 8/25 |

- **The claimed "$0.91–0.97 combined" is real for the pairs that complete.** We got an average of 0.90–0.95 per completed pair across the grid.
  But that number is survivorship. It counts only pairs that completed and leaves out the leg 1s that never got matched.
- **Leftovers kill it.** A leg 1 fills because that side is falling. If that side ends up winning, the other side goes to ~0 and leg 2 fills cheaply, so the pair completes.
  A leftover is therefore almost always a **losing** leg: 7 of 141 leftovers won on 1h and 0 of 38 on 4h.
  Each pair earns about $0.06–0.09 per share and each leftover loses about $0.40–0.46 per share, so break-even needs a leftover rate below ~15% of legs. We saw ~40–45% of markets end with a leftover.
- The result barely depends on the fill model: touch, queue and through differ by only about $30–60 over the week. Being optimistic about fills doesn't rescue it.
- Best cell in the whole grid: 4h b.44 T.94 check 15m queue50, net −$67. Every neighbour also loses.
- Rubric (METHOD.md): 8–9/25, not a candidate. OOS: "no" (negative everywhere). The lucky_number flag is `untested` because nothing was profitable.

## WHY THIS COULD FAIL (or why this sim could be wrong)
- **Adverse selection is the whole story.** A passive bid on the "cheap" side fills when informed takers (people watching Binance spot in real time) sell it to you.
  The leg that fills first is the one that is right to be cheap.
- The real accounts that post 0.91–0.97 probably (a) reprice every few seconds rather than every 5–15 min, (b) quote both sides continuously as market makers and earn rebates and liquidity rewards,
  (c) cut leftovers early or hedge on Binance or perps, and/or (d) report only completed pairs. None of that is "slow accumulation checked every 10 min."
- Tape limitations: the data-api gives taker prints only, with the taker's price. The queue ahead is a fixed assumption, not historical book depth. We assume mint matches show up as complementary BUY prints.
  Partial fills are ignored (all-or-nothing at 10 shares). Thin ETH markets mean even a 10-share bid can be a meaningful part of the flow.
- Sample: 7 days, a single volatility regime. BTC trended during part of the week. That is enough for a clear negative result, not for a fine-grained one.
- No hedging or stop-out variant was tested. Completing at the end as a taker costs roughly the same as holding: other side ≈ 0.95+ plus a 7% taker fee on p(1−p).

## Who is on the other side
Fast takers and market makers who watch the Binance BTC/USDT and ETH/USDT candle live (the resolution source is the Binance 1h/4h candle open vs close).
Market makers also collect maker rebates (20% of taker fees) and liquidity rewards. A bot checking every 10 minutes is the slowest participant in the book.

## Files and commands
- `fetch.py`: gets markets and the taker tape (cached) and a live book snapshot. `UD_DAYS=7 python3 fetch.py`
- `sim.py`: the state machine and fill models. `run_ud.py`: the grid, scoring, `out/grid.json`, `out/scorecard.md`, and leaderboard upsert (`PMUD_*`).
  Rows are also saved to `/workspace/lab/out/leaderboard_extra_PMUD.json`, which `backtest.py` now re-merges.
- Not on a loop; this is a one-off historical sim. Re-run with `python3 fetch.py && python3 run_ud.py`.
