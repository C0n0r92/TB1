# HANDOFF — Polymarket weather paper track (from Lab to Oracle), 2026-10-23 ~22:30Z

STRICTLY PAPER / READ-ONLY. No account, wallet, keys, orders or posting. Only free public APIs, gently rate-limited and cached.

## Running processes (left running on purpose)
- **Loop PID 148786** (`./loop.sh`): runs `run_cycle.sh` (logger.py → paper.py → score_weather.py), then sleeps 1800 s.
  The PID is also saved in `loop.pid`. Logs go to `logs/cycle.log`.
  Stop it with `kill $(cat loop.pid)`. A lock file (`/tmp/pmw_cycle.lock`) prevents overlapping cycles.
- **Backfill PID 144880** (`python3 backfill.py`, log `logs/backfill.log`). It was still fetching CLOB prices-history when work stopped, and its output `data/backfill/brackets.jsonl` hasn't been written yet.
  It has already written `data/calib.json` (per-station bias/rmse through 2026-10-22), which the live model uses. Once it finishes, run `python3 score_weather.py` to score the PMW_bf_* variants.

## What's built
| file | purpose |
|---|---|
| pmw_common.py | HTTP with per-host gaps and sha1 cache (`cache/`), bracket parsing, half-up rounding, fees, METAR parsing, station info |
| logger.py | Point-in-time snapshot of every open `daily-temperature` event: Gamma listing, CLOB `POST /books` (bid/ask/depth), METAR obs so far, Open-Meteo ensemble (ECMWF IFS 0.25 + GFS 0.25, 81 members), model p per bracket → `data/snapshots/YYYY-MM-DD.jsonl`. New events → `data/events.jsonl`. Resolutions via Gamma → `data/resolutions.jsonl` |
| model.py | Probability per bracket = METAR extreme so far ⊕ member extremes over the remaining local-day hours + station bias + noise, then unit conversion and half-up rounding. v2 sigma fix (see below) |
| paper.py | Live forward paper trader. Walks the logged ask depth for a $5 stake and buys when p − avg_fill − fee/share > margin. Margins {.03,.05,.08,.12,.15} × fee mode {market schedule, conservative 5%}. Requires a calibrated station and 1–48 h to the end of the local day → `data/paper_trades.jsonl` |
| backfill.py | BACKFILL (OPTIMISTIC). Sep 8–Oct 2 is warm-up for calibration; Oct 3–22 is the trade window. Uses Open-Meteo previous-runs day-2 forecasts and an expanding-window station bias/sd. Price = CLOB prices-history at local-day-start −24 h, with assumed ask = price + 0.02 and no depth |
| score_weather.py | METHOD.md rubric via pm_score.py (holdout = last 40%, 1000-run MC drawdown, neighbour/lucky flag), Brier score and reliability for model vs market → `out/scorecard.md`, `out/score.json`, leaderboard rows `PMW_live_*` / `PMW_bf_*` |
| pm_score.py | Rubric and leaderboard upsert. Keeps the header and also writes `/workspace/lab/out/leaderboard_extra_PMW.json` |
| config.json | stake, margins, filters, model params, `model_version` |

`/workspace/lab/backtest.py` was patched to re-merge `out/leaderboard_extra_*.json` rows so the PMW_/PMUD_ rows survive its full rewrite. The pre-patch copy is at `/workspace/lab/out/backtest.py.bak_pre_pm_merge`.

## Data so far
- Snapshots: 2 cycles (22:11Z and 22:21Z Oct 23), ~3,400 rows each, 313–314 events, 48 METAR stations. No resolutions yet; the first will come after Oct 24.
- `data/paper_trades.jsonl` is EMPTY by design. Two batches were discarded before any outcome was known:
  - v0 (22:11Z): bad end-of-day entries.
  - v1 (22:21Z): sigma collapsed to its 0.3 °C floor, so the model was overconfident. That batch is kept in `data/discarded/`.
  - The model is now **v2**, and the forward test effectively starts at the next cycle (~22:51Z).
- Market facts (Oct 23 snapshot): ~94 events per day (a high and a low for ~48 cities), ~11 brackets each, negRisk.
  For live brackets (mid 0.05–0.95): median spread 0.04, median liquidity ≈ $795 per bracket and ≈ $11.6k per event (range $196–$59.5k).
  Fees: 3,412 markets are `zero_fees`; 48 are `weather_fees` (rate 0.05, taker-only, fee = rate·p·(1−p)).
- Hong Kong uses a non-METAR source and isn't supported.

## Open questions / known issues
1. **Rule change.** Events up to about Oct 22 resolved on NOAA `weather.gov/wrh/timeseries?site=ICAO` in whole degrees. Newer events resolve on aviationweather METAR (routine only, no SPECI), using the tenths T-group, with half-up rounding.
   The backfill calibration therefore comes from the old rule, so its transfer to the new rule is unverified.
2. The model often disagrees sharply with the market (e.g. model 0.5 vs ask 0.08). Most likely this is model error, not edge. Watch calibration vs market Brier before trusting any PnL.
   Ideas: a market-blend variant, or capping the edge.
3. Calibration bias was learned on a deterministic day-2 mean (ECMWF + GFS seamless) but is applied to ensemble members. That's an approximation.
4. The backfill fetches prices only where p ≥ 0.05, so the market-Brier comparison is on a subset. Its fills are optimistic (no depth or queue).
5. Sample: the live forward test has 0 settled trades. It needs weeks to reach 50+ trades and an OOS holdout. Rubric results are meaningless until then.

## WHY THIS COULD FAIL / who is on the other side
- Pros on the other side: forecasting bots with MOS and nowcast models, METAR-watching bots that react within seconds to intraday observations, and market makers farming liquidity rewards.
- Our only possible edge is careful station and rounding matching. Edge-like signals on tails are probably our own model error.
- Also: thin books, rule and source changes, data outages (no data → the lowest bracket wins), and late corrections.

## Ireland — verdict: NOT permitted to trade (no VPN workaround; VPN use itself violates the ToS)
- Polymarket Help Center, "Geographic restrictions": https://help.polymarket.com/en/articles/13364163-geographic-restrictions
  - "The following 39 countries are completely restricted from accessing Polymarket:" — the list includes "IE | Ireland".
  - "Polymarket strictly prohibits the use of VPNs or similar tools to bypass geographic restrictions. Such actions are considered violations of the platform's Terms of Service (Section 2.1.4)."
- Developer docs, geoblock: https://docs.polymarket.com/developers/CLOB/geoblock lists Ireland (IE) under "Regulatory-Restricted Jurisdictions (Close-Only on Frontend)": "Close-only means users can close existing positions but cannot open new ones."
  The docs also say "the API itself is not restricted", but that is not permission; the ToS still forbids trading from a restricted jurisdiction.
- ToS attestation (https://polymarket.com/tos, client-rendered; the full text wasn't readable): "attest that you are not ... located in the United States, France or other restricted jurisdiction; and ... using a VPN or other measures to circumvent".
- Context (secondary press, not verified): Ireland was geoblocked around July 21, 2026, after GRAI action under the Gambling Regulation Act 2024.

## Commands
`./run_cycle.sh` runs one cycle. `python3 score_weather.py` re-scores. `nohup ./loop.sh > logs/loop.out 2>&1 & echo $! > loop.pid` starts the loop.
