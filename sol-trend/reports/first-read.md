# SOL trend / breakout study: first read (2026-10-23)
**Paper research only. Nothing was traded, signed in to, connected or posted. Lab reviews this before anything goes to Zero.**

## Verdict
**No candidate in either track.** No config reached the 18/25 bar with ≥50 trades and stable nearby settings.
- **Track A (spot SOL/USDC, long-only):** at best weak or unproven. The top score is 17/25, and those configs depend on exact settings.
- **Track B (1x long/short perps):** no edge. Every B finalist loses over 12 months at the 0.2% slippage tier.
- **Whole grid (864 configs per track):** not one config is profitable in all three periods (PRE, TRAIN, OOS) in either track. The median 12-month P&L is −55% for A and −148% for B, as sums of per-trade % at 0.2% slippage.

## Windows (no lookahead in selection)
| window | dates | SOL buy-and-hold |
|---|---|---|
| PRE (second unseen holdout) | 2024-11-28 → 2025-10-23 | −25.3% |
| TRAIN (selection only) | 2025-10-23 → 2026-05-23 | −53.4% |
| OOS (held out) | 2026-05-23 → 2026-10-23 | **+22.2%** (the "SOL rose" sub-period) |
| 12m | TRAIN + OOS | −42.7% (max drawdown 70.5%) |

Finalists per track: the top 5 by **TRAIN t-stat only** (min 25 train trades), plus 2 defaults fixed in advance. Defaults: default1 is Lab's 1h EMA50/200, N20 close, 2.5 ATR, trail3. default2 is 4h EMA200-rising, N55, trail3. The OOS score is the worse of the OOS and PRE scores, so both unseen periods must hold up. Multiple-testing caveat: 864 configs per track were searched, so treat any single good number as likely luck.

## Leaderboard (0.2% slippage per side, 5-min cycle; P&L = sum of per-trade % net of fees, slippage and carry)
| track | config | role | score | trades 12m | 12m | OOS | PRE | 0.1 / 0.3% slip 12m | cycles 0/5/10/15 12m | neighbours positive | random-entry p (OOS) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 1h_ema200up_pivot_vol_s1.5_rr2 | train#1 | 17 | 71 | +15.7 | +10.3 | **−67.6** | +29.9 / +1.5 | −4.2/+15.7/−3.6/−6.1 | 0.1 | 0.058 |
| A | 1h_ema50_200_pivot_vol_s1.5_rr2 | train#2 | 17 | 63 | +17.2 | +14.3 | **−49.4** | +29.8 / +4.6 | +1.3/+17.2/+6.5/−4.6 | 0.1 | 0.018 |
| A | 1h_ema50_200_n20_close_s2.5_trail3 | default1 (Lab) | 15 | 50 | +8.6 | +27.4 | +20.2 | +18.6 / −1.4 | +8.6/+8.6/+12.0/+3.5 | 0.5 | 0.031 |
| A | 4h_ema200up_n55_close_s2.5_trail3 | default2 | 14 | 11 | +9.7 | +20.8 | +3.3 | +11.9 / +7.5 | −5.9/+9.7/+16.4/+16.7 | 0.89 | 0.175 |
| A | 1h_none_pivot_retest_s1.5_trail3 | train#3 | 13 | 119 | +18.9 | +18.9 | −52.2 | +42.7 / −4.9 | −22/+18.9/+16.6/+17.8 | – | 0.066 |
| B | 1h_ema50_200_n20_close_s2.5_rr3 | train#1 | 11 | 103 | −21.5 | −23.8 | −66.3 | −0.9 / −42.1 | all negative | 0.1 | 0.50 |
| B | 1h_htf_n20_vol_s2.5_rr2 | train#2 | 11 | 94 | −21.9 | −9.5 | −89.1 | −3.1 / −40.7 | all negative | 0.0 | 0.36 |
| B | 4h_ema200up_n55_close_s2.5_trail3 | default2 | 10 | 26 | −1.1 | +17.8 | −17.6 | +4.1 / −6.3 | −19.4/−1.1/+8.2/+13.8 | – | 0.18 |
| B | 1h_ema50_200_n20_close_s2.5_trail3 | default1 | 10 | 129 | −45.7 | +3.6 | −28.7 | −19.9 / −71.5 | all negative | – | 0.10 |

The full table is in `leaderboard.csv` (14 finalists, with score components). The grid is in `out/grid.csv`.

**Reading Track A:**
- **The two 17/25 configs fail on PRE.** They lose 50–68% there. Their nearby settings are 90% negative, and their 12-month result flips sign when the bot cycle moves from 5 to 0, 10 or 15 minutes. That is a fragile, fitted result, not an edge.
- **Lab's default1 is the most honest result.** It is positive in PRE and OOS, at every cycle, and beats random entry in OOS (p=0.03). But it lost in TRAIN, its 12-month total is only +8.6%, it goes negative at 0.3% slippage, and only half its neighbours are positive.

**Reading Track B:** shorts do not rescue it, because the trend filters keep flipping. Long/short split over 12 months for B train#1 (Jupiter): long −31.0 / short +9.5. Venue comparison over 12 months (Jupiter borrow assumption vs Drift with Hyperliquid funding as the proxy):

| B config | Jupiter | Drift (proxy) |
|---|---|---|
| train#1 | −21.5 | −7.9 |
| train#2 | −21.9 | −12.7 |
| default1 | −45.7 | −38.1 |
| default2 | −1.1 | +4.9 (only 26 trades) |

Drift with positive funding pays shorts, so it is slightly less bad.

## Lab's question: is it just the EMA200 keeping the bot in cash?
Partly, yes. Trend filter alone (always in the market when the trend is up, 5-min delay, costs per switch), as sums of per-trade %:

| baseline | PRE | TRAIN | OOS | 12m |
|---|---|---|---|---|
| A 4h EMA200 | +3.6 | −33.6 | +22.9 | −18.4 |
| A 4h EMA50/200 | −30.5 | −33.1 | +21.5 | −18.7 |
| A 1h EMA50/200 | −20.8 | −43.2 | +24.7 | −29.2 |
| A 1h EMA200 (whipsaw, 398 switches) | −50.3 | −65.2 | −12.0 | −69.4 |
| B 4h EMA200 Drift / Jupiter | −15.4 / −28.7 | | +9.2 / −0.7 | −26.5 / −41.4 |
| Buy-and-hold | −25.3 | −53.4 | +22.2 | −42.7 |

- **In the 12-month bear market**, the trend filter mostly helps by keeping the bot out: −18% vs −43% for buy-and-hold.
- **In the OOS period, when SOL rose,** the filter alone roughly matches buy-and-hold (+22–25%).
- **The breakout layer adds little.** Lab's default1 makes OOS +27.4% vs buy-and-hold +22.2% and the bare filter +24.7%, with far less exposure. Its 12-month result is +8.6% vs −29.2% for the bare filter. So breakout plus ATR exits cut losses in the bear market but added little upside in the rally.

## Validation
- **Rolling walk-forward** (train 6 months, pick by t-stat, trade the next 2 months, 9 folds): A sum −28.6% (2 of 9 folds positive). B sum −71.7% (2 of 9 positive). In the +59% buy-and-hold fold (Jul–Sep 2026), A made only +6.5%.
- **Perturbation:** stability is measured as the share of neighbours (level, stop ±, exit ±, tf ±, confirm) that stay positive. It is ≥0.75 only for A default2, which has 11 trades.
- **Bot cycles 0/5/10/15 min:** large differences between cycles (e.g. train#1 swings from −6% to +16%). This is a sign of noise-fitting. 5m and 15m timeframes are heavily negative across the grid (median 12m −302% and −112% for A), because costs dominate.
- **Random entry:** same holding-time distribution, 1,000 draws. Only A train#2 and A default1 have p<0.05 in OOS. That is not meaningful after searching 864 configs.

## Lookahead review
- **Lab's `run.py`** was never run, and I did not run it as-is. I reviewed it together with `engine.py`:
  - Levels use `shift(1)`.
  - Pivots are only usable k=3 bars after they form.
  - The volume SMA is shifted.
  - Retest uses data only up to the current bar.
  - Signals fire on closed bars, and fills happen at the next 5m open after TF close + cycle.
  - The stop is checked before the target inside a 5m bar (conservative).
  - Indicator warm-up is excluded.
- **Truncation test** (`scripts/lookahead_test.py`): signals were recomputed on data cut at 35/60/85% of the history for 324 signal sets. There were **0 mismatches** vs signals computed on the full data.

## Data and proxies (all free and public)
- **Candles:** Binance SOLUSDT 5m/15m/1h/4h from binance.vision (2024-10-23 → now, no gaps). The higher timeframes are resampled from 5m inside the engine. *Proxy for SOL/USDC on Jupiter.* Coinbase SOL-USD 1h vs Binance: median absolute basis 0.05%, 99th percentile 0.17%, 1h return correlation 0.9996.
- **Funding:**
  - **Primary proxy for Drift:** Hyperliquid SOL hourly funding (api.hyperliquid.xyz, 2024-10-18 → now, 17.6k rows, last 12 months ≈ +0.8%/yr).
  - **Cross-check:** Kraken Futures PF_SOLUSD (2025-10 → now, ≈ +0.4%/yr).
  - **OKX:** labelled proxy, only from 2026-07-20 (+3.3%/yr; Hyperliquid in the same window: +6.8%/yr).
  - **Unavailable:** Binance fapi returns 451 (geo-block), Bybit returns 403, and the Drift data API is unreachable. None of these blocks were circumvented.
- **Jupiter borrow:** no free history exists. Assumed 0.003%/h on both sides (a labelled assumption).
- **Fees (venue docs read 2026-10-23):**
  - Jupiter Ultra swap: 2 bps per side.
  - Jupiter Perps: 6 bps open and 6 bps close, plus price impact (up to 0.44%, assumed to be inside the slippage tier) and borrow.
  - Drift SOL-PERP taker: 6 bps (docs show 4–6; I used 6).
  - Slippage tiers: 0.1, 0.2 and 0.3% per side, all reported.

## WHY THIS COULD FAIL (applies to every config here, and is the reason none is proposed)
- **Who is on the other side:**
  - Breakouts on SOL 1h are crowded. Market makers and Solana MEV/arbitrage bots sell into obvious N-bar highs and buy back after the false breakout. Our signals are public-level, slow (1h close + 5 min) and paid as taker.
  - On perps, funding and borrow are paid to the side that is already crowded. Jupiter's JLP pool is the counterparty on every Jupiter Perps trade, and it is structurally paid by the fees and borrow we cross.
- **Regime dependence:** 12 of the last 17 months were a SOL bear market. The only positive Track A results come from staying out of it or from one rally (Jul–Sep 2026). Another chop phase like PRE would lose (the train#1/#2 configs lost 50–68% there).
- **Costs:** results swing ±14% over 12 months per 0.1% of slippage. Real on-chain fills during fast breakouts are at or worse than the 0.3% tier.
- **Selection bias:** the best of 864 configs is expected to look good by chance. The walk-forward selection, which captures this honestly, was negative in both tracks.
- **Proxy risk:** Binance USDT prices and Hyperliquid funding stand in for SOL/USDC on Jupiter and for Drift funding. Real Drift funding and Jupiter borrow could differ materially.

## Live paper forward test (monitoring only, not candidates)
- **Process:** `scripts/start_forward.sh` → `scripts/supervisor.sh` (nohup, restarts on death after 30 s) → `scripts/forward.py`.
- **Each 5-minute cycle (runs 20 s after each 5-minute boundary):**
  - Appends closed 5m bars from data-api.binance.vision.
  - Refreshes Hyperliquid funding hourly.
  - Re-runs the same engine and writes only trades entered after the forward start (2026-10-23T22:40Z) to `ledger.jsonl`, as open/close events.
- **Configs:** A train#1, A train#2, A default1, B train#1, B train#2, B default2 (Jupiter costs, 0.2% slippage).
- **Files:** PIDs in `logs/supervisor.pid` and `logs/forward.pid`. Logs in `logs/forward.log` and `logs/supervisor.log`. Heartbeat in `logs/forward.heartbeat`. Health check: `.venv/bin/python scripts/status.py`.
- **Stop it:** `kill $(cat logs/supervisor.pid) $(cat logs/forward.pid)`.
