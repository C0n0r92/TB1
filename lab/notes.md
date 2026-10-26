# Lab notes

## 2026-10-23 copy fee sensitivity (FS_*)
- Script: copy_fee_sensitivity.py -> out/copy_fee_sensitivity.md, out/leaderboard_extra_FS.json (merged into leaderboard.csv via merge_extra.py FS under the pipeline lock).
- Cheaper execution adds only ~$0.15-0.35 per $5 copy (fees ~3.4 pts of 5.3 are gone, but delay drift + priority eat part). ZERO-cost bound: benji -0.25, ETT -0.10 mean $/copy, so the losers are the leaders, not the fees.
- Assumptions not measured: delay drift (no free historical swap data: mainnet-beta 429, publicnode null for old tx, GT trades 24 h only), liquidity from pump.fun constant-product formula.
- variants_tried 204 -> 248 (11 models x 4 leaders).

## 2026-10-23T23:35Z TRUTH entry check (from Copycat, read-only)
- copyfomo shows no entry mcap. Trade history: TRUTH $9.40 -> $6.59, -29.9% (USD PnL over $ invested, confirmed).
- Killcam GIF (low-confidence read): "copied @_benjitrades", buy price ~$0.0004160, held 3m45s.
- If TRUTH has the standard pump.fun 1B supply, our buy was ~ $416k mcap vs the leader card's $442.0k. That points to the "~$415k" case: the leader's real entry was earlier/lower, likely from a wallet we don't have mapped, and the card shows a later price. Not the "fill matched the chart at ~$450k" case. Confidence is low (tiny GIF text, supply assumed). Verify supply from the mint once it's known.
- Screens: /workspace/copyfomo/screens/L2_truth_history.png, L3_truth_killcam.webp

## 2026-10-23 ~23:40Z radar backfill (BF_*), first read
- Scripts: bf_common.py (shared Gecko/DexScreener throttle, data/backfill/.gecko_calls.log, 16 s spacing = ≤4/min combined since Zero 23:33Z), bf_sigs.py → bf_migrations.py (public RPC, migration account history → random daily sample) → bf_candles.py (Gecko 1-min, resumable) → bf_replay.py (under out/.pipeline.lock; writes out/backfill.json, out/bf_trades.csv, out/leaderboard_extra_BF.json; merged into leaderboard.csv by backtest.py, merge tuple SM/FS/MC/BF) → bf_report.py + out/backfill_hand.md → bf_final.py → out/backfill.md. bf_extend.py (forward candles for need_more pools) and bf_alive.py (DexScreener survivorship probe) are resumable side jobs.
- Calibration vs 187 live scanned rows: accel corr 0.99, h1 0.72, m5 0.15; liq model median err 3.4%. Missing mass median 12.7 pts. Rate-matched imputation 21.9 matches the live pass rate, but only ~60% of row-level pass/fail calls.
- Result (186/515 pools): baseline radar −52%/trade (n 33, OOS 11 at −58%); partial guard −41% (n 13); SM cells all n ≤ 11. Max score 14/25 on 1–2 trades. Nothing near 18/25 with 50+ trades.
- Post-hoc: 14/33 baseline losers are 'staircase' bot pumps (stair20 ≥ 0.85, all ≤ −80%). The 45-min age guard removes them. Live top10 doesn't separate them (median 14.0% vs 13.6%). Any stair filter is in-sample only.
- Don't restart bf_candles casually: at startup it re-fetches live calibration pairs older than 1 h (wastes budget).
- Scout's Helius scripts not run (they would spend Scout's key). Scout couldn't be messaged (no SendToAgent tool).

## 2026-10-23T23:56:17Z older-coins live setups: URGENT partial (PAPER research)
All three live setups (1h breakout, 15m breakout, C = 15m pullback to EMA20, Lab spec) are clearly negative at 2% round trip on both the old ($5-200M) and wide ($3M-1B) universes, in-sample and held-out. Details: out/oldcoins_setups.md (oc_setups.py), out/oldcoins_backtest.md (tuning/nightly, old universe, earlier data cut). Data: 51/119 tokens fetched so far; the fetcher is still running.

## 2026-10-24T00:10Z confluence (CL_) phase 1: PRE-REGISTERED before any result
- Signal: >=N (2, also 3) tracked wallets' first buys of one mint within W min (30 default; 10/60 swept). Entry = close of the 1-min candle containing (Nth buy + 10 s) (no candle -> next candle open, <=10 min, else no fill).
- DEFAULT exit (fixed now, sweep later): SL -25% (gap: open if opened below, close if closed below), TP +50% all, time stop 2 h, flat 08:00 Dublin, rug (exit <= -80%) recovers <= 10%.
- Costs: 4.7% round trip if entry mcap < $1M (pump.fun/PumpSwap at $5; quotes median 1.25% + 2x0.0005 SOL priority ~2% => 3.3% typical, 4.7% Zero's thin-pool measurement), else 2%. Sensitivity 3.3% / 7%.
- Holdout = latest 40% of each test's signal time. Controls: same token random time (+-4h, excluding +-5 min), same time other fetched tokens, single-wallet (first-buyer) copies.
- Lookahead status: EB_PIT = point-in-time (wallet counts from its runner's peak hour + 1h; runner mints excluded); EB_ALL, SMART4, LEAD = LOOKAHEAD (never candidates).
- Structure seen before results: all 79 EB_PIT n2 events fall on 2026-10-23 08:10-22:14Z (one day); median gap between buys 2 s; the same few wallet pairs (q2z7/q2iQ vanity prefix, 7K8J, 9mQx) recur -> likely ONE operator's bots, not independent confluence; events sit at/just after pump.fun -> PumpSwap migration.
- Data: data/cl/ (cl_events.py, cl_fetch.py <=5 req/min own lock data/cl/calls.log).

## 2026-10-24T00:55Z winners (WN_) phase 2: PRE-REGISTRATION (written after one smoke run of R1, n=3; nothing else seen)
- Data: Scout winners/ batch 1 (4 wallets, 141 trades). The profile uses only those trades. Rules are tested ONLY on the backfill graduation universe (data/backfill/candles1m, read-only, ~199 tokens with candles 09-25..10-23), EXCLUDING every mint a winner traded. A strict variant also drops every Dublin night a winner traded.
- Profile (winners vs their own losers, net5): winners entered at lower mcap (median $38k vs $80k), lower 1h volume ($41k vs $103k), a smaller prior-1h run (+31% vs +101%, n=25/38), and quieter tape (6 vs 18 1-min candles in the prior 30m). They held for less time (27 vs 60 min). smart_co_buys is 0 for both, so there is no clustering signal.
- Rules (first trigger per token, scanned every 5 min, features use only candles before T, entry = close of minute T+10s):
  - R1_quiet_small: age 0.5–6h, mcap $25–60k, ≤10 1m candles in prior 30m, prior-1h change −30%..+50%.
  - R2_fresh_not_chased: age 0.25–6h, mcap ≤ $100k, 5m change ≥ +15%, 1h change ≤ +50%.
  - R3_vol_accel: age 0.25–6h, mcap $10–300k, 15m volume rate ≥ 2× the prior-45m rate, 1h volume ≥ $5k, 5m change ≥ 0, 1h change ≤ +50%.
- Exits: dflt = SL25/TP50/2h (the same as CL). quick = SL20/TP30/30m (the "winners hold short" pattern).
- Costs: 4.7% <$1M, else 2%.
- Holdout: tokens migrating after the 60th-percentile migration time.
- Controls: random entry time in the same age window on every universe token.
- Neighbour sweep on each threshold.

## 2026-10-24 Mean reversion: single-token long-only z-score dip buys (Chan-style) — NEGATIVE
- Scope: pairs mean reversion was dropped by Zero's steering and is now owned by Lab 2. No pairs code was written.
- Scripts: mr_fetch.py (candles), mr_dip.py (grid, Hurst/VR/ADF/half-life, book), mr_report.py. Venv: .venv_mr (adds statsmodels). Rerun: `.venv_mr/bin/python mr_dip.py`.
- Candle cache: data/mr_candles/<src>_<SYM>_<tf>.csv with columns ts (bar open, unix ms UTC), o, h, l, c, vq (quote volume).
  - src bn = Binance spot USDT (data-api.binance.vision; 1h covers 365d, 15m/5m cover 92d).
  - src gt = GeckoTerminal top pool (1h ~6 months, 5m ~65-90 days; 15m is resampled from 5m). Pool metadata is in gt_<SYM>_pool.json. Calls were spaced 16 s apart (≤4/min), logged in .gt_calls.log, and are resumable via .done markers.
- Universe: 19 tokens. Binance: SOL, PUMP, PENGU, TRUMP, BONK, JUP, RENDER, WIF, PYTH, RAY, JTO, W, KMNO, BOME. GeckoTerminal: FARTCOIN, POPCAT, MEW, GRASS (pool only $0.49M), USELESS.
  - Picked from today's CoinGecko Solana top by volume (data/mr_candles/cg_solana_top.json), so there is SURVIVORSHIP bias. Binance prices are a proxy for on-chain fills.
- Grid of 288 variants: tf {5m, 15m, 1h} × L {20, 50} × z-in {-2, -2.5} × N bars × stop {z ≤ -4, -5%} × regime {off, SOL 4h > EMA50, EMA50 slope up}. Entry at the next open.
  - Windows: night (entries 20:00-07:00 Dublin, flat at 08:00) and 24h. Book: 10% per trade, max 3 open.
  - Costs: lo = 0.15%/side. hi = 0.30%/side + 2×$15/liq + 0.1% stop slippage. Holdout is the last 30% of dates.
- Checks: median Hurst ~0.48, VR(4) ~0.93-0.98, ADF stationary in 0 of 19 tokens. Half-life of the 50-bar deviation is ~19-20 bars. Weak hints only in BOME, POPCAT, MEW and FARTCOIN.
- Results: 0 of 288 variants are positive both IS and OOS at hi cost. Best per tf (hi cost, OOS per trade, all signals):
  - 1h: +0.00% [-0.38, +0.37], n=272.
  - 15m: -0.65%.
  - 5m: -0.55%.
  - The regime filter hurts. P(+10% night) = 0 and P(-20% night) = 0 at 10%×3.
  - Weak lead only: 1h L50 z2.5 at lo cost shows OOS +0.31% [-0.05, +0.68]. Most exits are the 08:00 flat, so this looks like overnight drift in survivors. It is NOT a candidate.
- Outputs: out/mean_reversion.md, mr_grid.csv, mr_hurst.csv, mr_trades_best.csv. 6 MR_* leaderboard rows were merged via merge_extra.py under the lock (leaderboard.csv.bak-mr). variants_tried is now 712.
  - backtest.py line 365 now includes "MR" in the re-merge tuple (backup: backtest.py.bak-mr).

## 2026-10-24T00:55Z confluence (CL_) phase 1: RESULT
- Signal = N tracked wallets (4 leaders + Scout wallets) buy same token within W min. PIT set EB_PIT (early_buyer counted from peak_at+1h); LEAD/EB_ALL/SMART4 are LOOKAHEAD (_LOOKAHEAD suffix, forced non-candidate).
- EB_PIT n2 w30, default exit: 76 trades, mean -0.133 [-0.23,-0.04], holdout n=32 -0.116, 8/25. n3: 12 trades, -0.210. Controls (first-buyer -0.103, same-token random time -0.096, same-time other tokens -0.067, single-wallet non-cluster -0.100) all BEAT the cluster signal.
- Structure: all 79 PIT events on 10-23, median 2 s gap 1st->Nth buy, 9 wallets (6 were ogkimchi early buyers) = one sniper operator, median entry mcap ~$22k. Not independent "smart money" agreement.
- Only positive cell: n3 delay 120 s (n=11, +0.079), flagged lucky. NO CANDIDATE. 54 CL_ rows merged; out/confluence.md. backtest.py whitelist now includes CL, WN (backup backtest.py.bak-clwn).

## 2026-10-24T01:20Z winners (WN_) phase 2: RESULT
- 141 trades, 4 wallets (64 W / 77 L net5); GT 1m candles for 118 (data/cl/wn, 141 calls at ≤5/min).
- Their entries with fixed exits: SL25/TP50/2h -0.070 [-0.14,0.00], SL20/TP30/30m -0.069 [-0.12,-0.02]; actual +0.86 mean (median -13%; capped-10x +0.48). The edge is in exit/hold discretion, not entry selection.
- After their exits: price -15% median at 30 m (n=78), -34% at 2 h (n=63) vs random-time drift about -1 to -2% median → well-timed exits (discretionary).
- Pooled 'small/quiet wins' contrast is mostly wallet mix (neodot $7k curve coins); within wallets it is mixed. No clustering (smart_co_buys 0). Liquidity/holders at entry blank; X buzz untestable (first-mentions starts 10-23, 0/141 overlap).
- Rules on 199 non-winner backfill tokens, holdout after 10-15 23:44Z: R2 fresh-not-chased 47 trades -0.051..-0.079 (OOS n=17 -0.06/-0.08), beats random (-0.10..-0.13) but negative; R3 vol_accel -0.18..-0.20; R1 n=3. Strict non-winner nights: n≤5. Sweep: R1 n30≤20 n=5 +0.186 score 19 → lucky flag, n<50; R2 chg5≥0.08 n=59 -0.029 (OOS +0.092, n=18). NO CANDIDATE. 25 WN_ rows; out/winners.md, out/wn_profile.json.
- 01:3x exit test (Zero priority): out/exit_test_filtered.md via cr_exit4.py. benji filtered n=4 (0 held-out) -> too small; no rule beats ladder. Winners-batch fetch (cr_win_fetch.py) still running, neodot dropped (Lab 2).

## 2026-10-24T10:53Z swing (SW_): RESULT
- Request from Zero: simple long-only spot swing rules on SOL, JUP, BONK, WIF, JTO, PYTH and RAY, using 4h and 1d Binance spot USDT candles (data/sw_candles/). Each rule family was tested at its pre-registered setting plus one-step neighbours, 30 settings x lo/hi cost.
  - Eval window: 2024-03-05 to now. Holdout: last 30%, from 2026-01-07/08. Book: 10% per position, max 3 open. Each token was also tested as a fully invested sleeve.
  - Long-history view: from 2020-08 (SOL) and 2021-08 (RAY), with holdout from 2024-12-13.
- Results:
  - (a) EMA20/50 + ATR trail and (b) Donchian lose held out on 4h: book -8.7% and -16.5%, mean trade -1.0% and -0.8%.
  - On 1d they are positive held out (EMA k3 +2.8%, Donchian N20/M10 +9.4%, the latter carried by RAY/PYTH). That is only n=18-25, with 14-30% exposure in a SOL bear market (SOL hold -27.5%, DD 58%), and both lost IS. In the long-history view they are hugely positive IS (2021 bull) and negative OOS, so they are regime/beta, not edge.
  - (c) RSI(2) > 200d SMA: 4h loses after costs. Pre-registered 1d X10 is flat OOS (-0.04%, n=21). The 1d X5 neighbour is +3.4%/trade OOS on n=10, and +2.3%/trade over 62 trades in the long history (CI [+0.3, +4.3]), with only 2-3% exposure. It scores 18/25 but is NOT a candidate (<50 trades, <20 OOS).
- NO CANDIDATE. Only a weak paper-forward watch remains: RSI(2) daily X5/X10.
- Outputs: out/swing.md and out/sw_grid.csv. 60 SW_* rows were merged under the lock (leaderboard.csv.bak-sw). variants_tried is now 939.
  - variants_tried.json was updated by sw_report.py before a backup was taken. I reconstructed the pre-SW state as data/variants_tried.json.bak-sw (879 entries).
  - backtest.py line 365 now includes "SW" in the tuple (backup: backtest.py.bak-sw).

## 2026-10-24 — RSI(2) daily paper-forward watch STARTED (Zero-approved, PAPER ONLY)
- forward/rsi2_daily.py tracks books SW_rsi2_1d_X5 and SW_rsi2_1d_X10 (the sw_backtest rule (c) 1d: close > SMA200 and RSI2 < X, then buy at the next open; exit when RSI2 > 70 or close > SMA5, at the next open). Each book: 10% of realised equity from $1,000, max 3 open, hi cost (0.30%/side + slippage, +0.10% on stop fills).
- Data: data-api.binance.vision 1d klines, 7 requests/run. Signals use closed bars only. Starts FLAT from the 2026-10-23 close (no signal: SOL/WIF/PYTH RSI2 11.7-13.6, above the 200d). Idempotent via state last_bar.
- Parity: `--replay` on the cached candles reproduces sw_backtest book() exactly (X5 47 trades, X10 87 trades, same equity).
- Cron: `15 0 * * *` (UTC). Files: forward/rsi2_state.json, forward/rsi2_daily.jsonl, forward/rsi2.log.
- Judge after >= 30 FORWARD trades per book (expect ~1-2 signals/month, so many months). Not a candidate until then plus METHOD (50+ trades, 18/25).

## 2026-10-24 — Benji full-horizon replay (PAPER ONLY), supersedes the winners section of out/.cr_win_section.md
- bj_full_replay.py uses cr_win_replay helpers (load/path/drift_defaults/filt). Costs are the stated round trips: self $5 4.7%, self $10 3.0%, copyfomo 5.3%, plus fitted liquidity-scaled impact and per-leg gas. Delay 5 s; drift outside 0.75–1.33 is clamped to the leader median. Chase is the 5 s mid vs his fill.
- Change vs cr_win_replay: for non-mirror rules, his sell prints are treated as price ticks for stops and targets (fixes UNCC being marked at +900% with no TP firing).
- bj_fill_candles.py (gentle GT retry via bf_common.gecko) recovered buni and Cardback. PUMPERS, UP×2 and Minibot have no GT data. Backups: data/cr/wcandles/*.bak-bj.
- Key fact: Scout net5 for benji is +550 SOL, but without SI it is -45 SOL. Only 1 of his trips is after 10-15 07Z.
- Backups for this merge: data/variants_tried.json.bak-bj (939), leaderboard.csv.bak-bj and .bak-cr, out/leaderboard_extra_CR.json.bak-bj, out/.cr_rows.json.bak-bj, backlog.md.bak-bj, notes.md.bak-bj. Staging: out/.cr_bj_staging.json.

## 2026-10-24T11:20Z winners batch 2 (WN_B2_): RESULT (held out by WALLET)
- Reran wn_b2.py (first run 02:07Z was never written up) with 185/246 batch-2 trips now covered by cached 1m candles; no new API calls this cycle (bf_candles and cr_win_candles fetchers already running).
- Replicates batch 1: their entries + fixed exits lose (-5.7% [-10,-1] / -6.2% [-9,-3], n=184). Post-exit drift -4.9% median 30m, -10.8% 2h vs random -0.3%/-1.7% (about a third of the batch-1 effect). Actual +18% mean, -11% median, outlier-carried.
- Exit picked on b1 (trail15_arm20) -5.4% on b2. arm100 trails are ~0 on b2 (OOS n=63 +5..+9%) but were the worst on b1, so that's unstable and a lucky pick. 18 WN_B2_ rows, best 14/25, NO CANDIDATE. variants_tried 1101. out/wn_b2.md.
- Checks: pipeline loop PID 95639 alive, last run 11:03Z rc=0; relabel running (provisional survivors, first FINAL labels due 20:07Z). Chunk's oldcoins live still paused, no new oldcoins paper trades since 02:17Z, so nothing new to check against the backtest.

## 2026-10-24 — Fast exit quick test (FE_*), for Zero
- Grid: TP +8/12/20/30% (all) × SL −8/10/15% × hold 10/20/45 min; entry +5 s; GT 1-min candles; stop checked before TP; primary stop fill = bar low. 154 trades (97 Scout, 51 CR30, 6 live paper); holdout = after 2026-10-15 15:33 UTC (107 IS / 47 OOS).
- Result: all 216 settings lose. Best IS rule FE_tp20_sl08_h10: −10.4%/trade self $10 (OOS −9.6%), −12.8% copyfomo (OOS −11.7%). METHOD fill: −4.3% / −5.8%. Score 9/25, not a candidate.
- vs ladder (−17.6% self $10): fast loses ~7%/trade less overall (CI +1.5..+12.0) but held out only +2.2% (CI ±13) → no real edge; it just spends less time in a down-drifting book.
- Files: out/fast_exit.md, fe_backtest.py, fe_report.py, fe_fetch.py, data/fe/. Backups: backtest.py.bak-fe, data/variants_tried.json.bak-fe (1101→1323), leaderboard.csv.bak-fe, notes.md.bak-fe. No new branch.

## 2026-10-24 ~14:30Z: Exit-signal study (ES_), PAPER ONLY, zero API calls
- Cache only: data/cl/wn 1m candles + Scout winners/trades.csv. Code: es_common.py, es_control.py, es_rules.py, es_cr30.py, es_rows.py. Report: out/exit_signal.md. Data: out/es_control.json, out/es_rules.json, out/es_cr30.json.
- **Control.** Winner sells happen underwater: b1 median −24% vs entry and −41% from peak at the sell.
  - Same-token matched (run-up from entry plus run-up from the 60-m low), paired diff of drift: b1 30m −5.8% [−16, +3.5], 2h −28% [−82, +7], median +4%. b2 30m +2.3% [−3.8, +8.5], 2h −2.8% [−12, +5].
  - The cross-token match favours b1 (−9% / −28%) and is weak on b2.
  - trail15_arm20 exits are followed by −20% / −33% on b1, the same as the winners. So the post-exit drift is mostly momentum on dying tokens, not skill.
- **Features.** AUC 0.43-0.57. Only "deeper below the peak at the sell" replicates (AUC 0.44 / 0.43). Volume roll-over is absent; on b2 volume is higher at sells.
- **Rules.** 36 pre-registered rules (VOL/RED/UW, picked on b1) are all negative on b1, b2 and both date halves.
  - Best: ES_RED_2_10, b1 −6.1%, b2 −3.3% [−8.9, +3.3], 10/25.
  - Baselines: trail15_arm20 at 11/25; fixed SL25/TP50/2h at 9/25.
  - CR30 extra (n=28, survivor-biased): ES rules are no better than the trail.
- 38 ES_ rows merged via merge_extra.py under the lock. "ES" was added to the backtest.py extras whitelist (backup backtest.py.bak-es). variants_tried 1323 → 1361. No candidate.
- Backups: leaderboard.csv.bak-es, data/variants_tried.json.bak-es, backlog.md.bak-es, notes.md.bak-es.

## 2026-10-24 ~15:15Z: Inflow-spike test (IF_*), for Zero, PAPER ONLY, zero API calls for the backtest
- A real historical test is impossible (no historical per-trade buyer or side data for free). PROXY on data/backfill/candles1m (1,614 sampled graduations, 09-25 → 10-23): W-min volume ≥ R × prior-30-min rate, green window, modelled liq ≥ $20k, age ≥ 5 min. Grid: W 1/3/5 × R 2/3/5 × delay 5/15/30 × 49 exits (Zero's fast 48 + 20/15/60) = 1,323.
- Result: 0/1,323 positive, in-sample or gross. Best IS IF_w5_r2_d30_tp08_sl15_h05: −6.6%/trade @0.04 SOL (base −6.1%), OOS −6.9% [−8.9, −5.2], n=569 (442/127), win 33%, 9/25. Gross −1.2%. Old radar on the same pools: −52%.
- Forward: forward/inflow_fwd.py live with nohup/setsid (pidfile forward/inflow.pid), real GT-trades signal W3/R3, 15 s delay, 0.04 SOL, tracks T30, T60 and F08_15_5. Shared throttle at 8 s.
- Files: if_backtest.py, if_analyze.py, if_rows.py, out/inflow.md, out/.if_grid.pkl, out/.if_res.pkl, out/.if_rows.json. "IF" added to the backtest.py:365 allow-list. variants_tried 1361 → 2684. Backups: backtest.py.bak-if, data/variants_tried.json.bak-if, notes.md.bak-if, leaderboard.csv.bak-if-pre (+ .bak-if from merge_extra).
