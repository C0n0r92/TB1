# Lab backlog (status: todo / data-pending / running / done). Updated 2026-10-24 11:20Z.

## TOP PRIORITY: guarded-radar forward test
| item | status | notes / where |
|---|---|---|
| Forward-test rugguard-guarded radar signals with full costs | running | GUARD_live (rows scanned with guard on, since ~21:13Z). 0 guarded signals so far -> no numbers yet |
| Replay guard on pre-guard rows | done (optimistic) | GUARD_replay / GUARD_replay_pit (guards.py; pit = holder data <= 15 min after scan) |
| (a) "creator funded by known rugger" too strict? | running | GUARD_no_funded_rule vs GUARD_replay; guard_eval.md "launch_funded" row |
| (b) 45-min age gate sweep | running | sweep GUARD_replay@guard_min_age_h 0/0.25/0.5/0.75/1/1.5 + rug-timing table in out/guard_eval.md |
| (c) 24h relabel of survivors (Grok, GTA6 Coin, Speed...) | running | relabel.py in pipeline; first FINAL labels due 2026-10-24 20:07Z onward (data/labels.csv) |
| Scout buy-time flag, point-in-time, cached | running | fetch.py scout_capture -> data/scout/ (<=3 script runs/run, re-uses Scout's 10-min cache) |
| Chunk would-be buys (live/paper-buys.jsonl) | running | CHUNKPAPER_all; candles fetched by pipeline |
| Skip vs half-size on "caution" | running | GUARD_caution_skip/half, CHUNKPAPER_skip_caution/half_caution |

## METHOD upgrades
| item | status | notes |
|---|---|---|
| 1-5 scores x5, total, candidate rule (>=18, >=50 trades, OOS) | done | scoring.py, leaderboard sc_* / score_total / candidate |
| Neighbour sweeps + lucky_number flag | done | [[sweep]] in config.toml |
| 1,000-run Monte Carlo drawdown | done | mc_dd_p5/p50/p95 |
| WHY THIS COULD FAIL + other side | done | report.py |
| Sunday weekly review | done | report.py (out/history snapshots) |
| variants_tried count | done | data/variants_tried.json |

## QUEUE
| item | status | data | notes |
|---|---|---|---|
| Copyfomo trader-swap (top weekly trader, 0.25x, exit with leader, demote after 2 vs 3 losses, vs fixed) | running (preliminary) | /workspace/onchain-intel/trader_trades.csv (Scout; 2 traders so far) | copytrade.py, COPYSWAP_* / COPYFIXED_*; one +32,733% round dominates ExactTallTakin |
| Cluster buys (>=3 early-buyer smart wallets, enter on 3rd buy, gap stops) | running (lookahead backfill + forward wait) | /workspace/onchain-intel/cluster_buys.jsonl (Scout, 84 rows, all detected retro at 22:01Z) | Loader now reads Scout's schema (entry = last_buy_in_window_at, seed runners dropped). CLUSTER3_enter3rd = forward-only rows (detected <= 15 min after buys): 0 so far. CLUSTER3_LOOKAHEAD_backfill = 80 retro rows, wallets were mined from runners so hindsight-biased; candles backfill <= 6 pairs/run after radar. Scout NOTES: clusters are NOT a buy signal, at most a weak veto |
| Laddered exits (1/2 @+100%, 1/4 @+200%, trail 30%, liq -40% exit, 6h time-stop if never +20%) vs -25%/2x | running | radar candles | GUARD_ladder, LADDER_unguarded vs A_live_rule |
| Re-entry after TP (pullback 30-50%, new high on rising volume, stable liq) | data-pending | needs candle VOLUME: only GeckoTerminal fetches from 2026-10-23 22:xx keep volume (radar cache has none) | GUARD_ladder_reentry, GUARD_tp2_reentry, REENTRY_unguarded |
| Ticket vs pool (skip if ticket > 1% of pool; stake 5-10%, never > 15%) | running | radar candles + liq polls | GUARD_ticket1pct_stake10 vs GUARD_stake10_noticketcap (stake_pct asserts <= 15%) |
| Copy lag (our fill vs leader entry; skip if > 15% above) | data-pending | Copycat's new lag log in /workspace/copyfomo (not yet present; loader sources.copy_lag accepts leader_mcap/our_mcap or prices) | COPYSWAP_demote2_lag0/lag15 bracket the effect meanwhile |

## Copyfomo (Zero, 22:06Z)
| item | status | data | notes |
|---|---|---|---|
| Stop slippage ~5 pts on copyfomo (TRUTH stop -29.5% vs -25%; gap -> worse) | done | - | copytrade.py stop/stop_slip; copytests.py (gap: candle open - 5 pts) |
| Chase-cap sweep 10/15/25% (cap already on at 15%) | running / data-pending | 1-min GeckoTerminal candles per leader trade (data/copytest/candles, ~8 calls/run, newest first) + leader's own fill from onchain-intel/data/enh_<trader>_all.json | copytests.py section 1; copyfomo shows only leader mcap, so our fill = chart price at buy + bot lag (10 s assumed) |
| Rugcheck hard rejects at leader buy time (mint/freeze, LP unlocked, top10 >18/>25, creator >5%, danger) | running / data-pending | rugcheck reports (data/copytest/rugcheck, ~8/run) | copytests.py section 2. Only mint/freeze is point-in-time; LP/top10/creator/danger are from reports fetched later = LOOKAHEAD (buy-time holders not reconstructable) |
| Entry delay cost 20/40/60 s (alerts + filtered manual copy) | running / data-pending | same candles | copytests.py section 3; 1-min candle resolution |
| Copyfomo real fills/lag log | data-pending | /workspace/copyfomo has no trade log yet (only night-start.json, x-watch-log.md) | would replace the chart-based fill estimate |

## Radar backfill (Zero, 2026-10-23; now priority #3, ≤4 req/min combined Gecko+DexScreener)
| item | status | data | notes |
|---|---|---|---|
| On-chain graduation universe (pump.fun → PumpSwap migrations, random daily sample) | running | public RPC, data/backfill/migrations.jsonl (515 so far) | bf_migrations.py, no Gecko/DS budget |
| 1-min candles per sampled pool | running (~6 h left at ≤4/min) | data/backfill/candles1m | bf_candles.py, resumable, round-robin by day |
| Replay baseline / partial guard / SM grid, holdout nights 10-14…10-22 | first read done | out/backfill.md, BF_* rows | rerun: flock out/.pipeline.lock python3 bf_replay.py && python3 bf_report.py && python3 bf_final.py |
| Forward candles for signal pools ending before deadline | pending | bf_extend.py | ≤3 calls/pool, run after the fetch queue drains |
| Survivorship probe refresh | pending | bf_alive.py | resumable, 30 mints/call |
| Staircase-pump filter (stair20 ≥ 0.85) | idea, post-hoc | bf_trades.csv stair20 | needs a fresh holdout (forward data) before it counts |
| Missing inputs: buy/sell counts, unique buyers, holders/top10 PIT, creator/bundle | data-pending (Scout/Helius) | Scout's Helius history | no SendToAgent tool here; ask via Zero |

## Team rules
- Read teammates' files freely; never edit them; never instruct any trading bot to change settings (proposals go to Zero only).

## Earlier baseline (done)
- Variants A-N, CHUNK_actual, COPY_* (waiting for Chunk live buys / copyfomo logs), single pipeline + daily report.

- [done 2026-10-23] copy_candidates.py: copyfomo-settings copy simulator for up to 5 traders (first buys, $50/$100k filters, TP +100% half, SL -25% -5pts, crash-candle-close stop fill calibrated on TRUTH, 15% chase, 3/10 s delay), 25-pt score, MC DD, nightly walk-forward, stake/nightly-limit MC; reruns on input change. Waiting: Scout leader-rank.md + swap histories for the 6 leaderboard traders with wallets; 26 leaderboard handles have no wallet.
- [done 2026-10-23] copy_fee_sensitivity.py (Zero ask): copyfomo REF (~5.3% rt + 2.5-pt stop slip) vs self-run Jupiter copier (0.3%/side, priority $0.005/0.02/0.05 per tx, slip 0.5% + 2*$5/liq(mcap) with liq = 0.41*sqrt(70k*mcap), delay drift 2%*d/10 at 2 s/5 s, pessimistic band 0.5%/side + liq/2 + 1% base + 2% drift) + ZERO-cost upper bound, 4 leaders. Result: no leader flips; benji/ETT lose even at zero cost; bystevenr/pointfarmcap were already positive (lottery-carried). Rows FS_* (16) via leaderboard_extra_FS.json; backtest.py merge now SM/FS/MC (backup out/backtest.py.bak-fsmc). Data-pending: real post-delay swap prices (needs historical tx RPC) and point-in-time pool liquidity.
- [done 2026-10-24, NEGATIVE] Mean reversion: single-token long-only z-score/Bollinger dip buys, 5m/15m/1h, 19 top Solana tokens, 288 variants, with and without the SOL 4h regime filter, plus Hurst/VR/ADF/half-life checks and the nightly distribution.
  - Nothing clears the hi cost held out. The regime filter hurts.
  - Files: out/mean_reversion.md, MR_* rows. Cache: data/mr_candles/.
  - Optional follow-up: test the "1h overnight dip, lo cost" lead only on forward data, and check it against plain overnight holding.
- [moved] Pairs mean reversion (long-short and long-laggard): owned by Lab 2. Lab wrote no pairs code.

- [done 2026-10-24, NEGATIVE] Confluence (CL_): 2+/3+ tracked wallets within 10/30/60 min, PIT early-buyers (LEAD/EB_ALL/SMART4 = LOOKAHEAD). EB_PIT n2 76 trades -13% [-23,-4]; worse than all controls; the "cluster" is one sniper operator (9 wallets, median 2 s gap, all on 10-23). out/confluence.md, 54 CL_ rows.
  - Optional: finish EB_ALL candle coverage (cl_fetch.py, LOOKAHEAD only, low priority); re-test PIT confluence on forward nights once more early-buyer sets mature.
- [done 2026-10-24, NEGATIVE] Winners profile + rules (WN_): entries with fixed exits lose ~7%; edge = discretionary exits (price -15%/-34% 30 m/2 h after their exits). R1-R3 on non-winner tokens, held out: best R2 -5..-8% (beats random -10..-13%). out/winners.md, 25 WN_ rows.
  - Next (data-pending): an exit-signal study (what precedes their sells: volume roll-over, sell-side flow, mcap milestones) needs buy/sell flow (Scout/Helius) — the only lead from winners/. Batch-2 rerun DONE 2026-10-24T11:20Z (WN_B2_, held out by wallet + date): entries-have-no-edge and exits-are-timed both replicate (post-exit effect ~1/3 of batch 1); no mechanical trail reproduces it; no candidate. out/wn_b2.md.
  - [done 2026-10-24, NEGATIVE] Exit-signal study (ES_, candle-only, zero API calls): matched post-pump control shows the post-exit drift is mostly 'dying tokens keep falling after any price-down exit' (same-token matched paired diff ~0 in b1 and b2; trail15 exits are followed by the same -20%/-33% on b1). Candle features barely separate sells (AUC 0.43-0.57; only 'deeper below peak' replicates). 36 pre-registered VOL/RED/UW rules all negative on b1, b2, both date halves; best ES_RED_2_10 b1 -6.1% / b2 -3.3% [-8.9,+3.3], 10/25; none beats trail15_arm20. No candidate. out/exit_signal.md, 38 ES_ rows, variants_tried 1361. Reopen only if Scout gets per-swap flow (seller count, top-holder sells).
- [done 2026-10-24, NEGATIVE] Swing 4h/1d on SOL/JUP/BONK/WIF/JTO/PYTH/RAY (SW_): EMA20/50+ATR, Donchian 20/10, and RSI(2)>200d SMA. 4h loses held out. 1d trend rules are "positive" OOS only by being in cash during the SOL bear market (n=18-25, lost IS). RSI(2) 1d X5 is +3.4%/trade OOS on n=10 (long history: 62 trades, +2.3%) and is not a candidate. out/swing.md, 60 SW_ rows.
  - Optional: paper-forward watch of RSI(2) daily X5/X10 signals (about 1-2/month), judged at >= 30 forward trades. Re-test the trend rules if the regime turns into an uptrend.
- [running since 2026-10-24, PAPER ONLY] RSI(2) daily forward watch (X5/X10), forward/rsi2_daily.py, cron at 00:15 UTC. Judge after >= 30 forward trades; review forward/rsi2_daily.jsonl monthly. No live use.
- [done 2026-10-24, NEGATIVE] Benji full-horizon copy replay (CR_BJ_, Zero ask): Scout's winners round trips for _benjitrades 31/32, bystevenr 36/38 and onlyzhynx 30/31. Grid: 4 exits (A mirror, B ladder, C live SL-15/TP+50 half/15% trail, D old SL-25/TP+100 half/mirror) × 08:00 flat on/off × live filters on/off × self $5/$10 / copyfomo $10.
  - Benji, filters off: every rule loses (mirror self $10 -$36 on n=31).
  - Benji, filters on: n=8, all in-sample, 0 held out. Mirror at full horizon is +$30.5, all from SI (+279%); without it +$2.65, and with the 08:00 flat +$2.0.
  - SI is lost under every stop rule and under the 08:00 flat. CRAWL is kept only by mirror and D.
  - Best score 12/25. No candidate.
  - Files: out/benji_full_replay.md and 120 CR_BJ_* rows (merged with the 24 existing CR_ rows, so 144 CR rows). variants_tried is now 1083.
  - Optional: paper-forward log of benji's NEW trips (mirror, no flat; judge at ≥20). DCA-mirror (copy his adds, capped) is untested.
