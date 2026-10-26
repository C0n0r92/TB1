Changed since last update: 2026-10-24T00:53Z. New: moved 5 exchange hot wallets with Solscan labels (Bybit Wallet 10, Binance 2, Gate Hot Wallet, Bitget Exchange, KuCoin Hot Wallet) out of the known_ruggers.json funders into custodial_ignore.json, so rugguard no longer rejects creators they funded. Exchange funding is neutral, not a pass. Earlier (2026-10-24T00:45Z): oldcoins.py now uses tiered coverage (new criteria: mcap $3M–$1B, age ≥3 d, liq ≥$300k, vol24h ≥$750k; tiers 1–3 always get a full check, tier 4 gets a light check with full checks rotated across it). It also records untested hypothesis fields that never change the verdict (stair_step definition below). refresh.sh is trimmed to a hard 10k Helius-credit cap (see the 'refresh.sh trim' section). Earlier (00:00Z): watch list for bystevenr/pointfarmcap; finding that 5 known_ruggers.json funders are exchange-like wallets.

# Scout on-chain intel: notes (2026-10-23)

## Files (all in /workspace/onchain-intel)
| file | who | what |
|---|---|---|
| rugcheck_creator.py `<mint>` | Chunk, at buy time | JSON `verdict` block / caution / ok / unknown, with score, reasons and evidence (solscan links). Cached for 10 min in data/rugcheck/; use `--fresh` to bypass. |
| known_ruggers.json | rug flag, Chunk | Creators and profitable launch-slot bundlers of dumped coins or template-launch coins. Each entry has tokens, buy/sell sigs, funding_chain and date_added. |
| known_funders.csv | rug flag | Wallets that SOL-funded known ruggers (1-2 hops), with n_ruggers_funded and strength (strong means it funded 2 or more). |
| smart_wallets.json | radar boost/veto | `smart` and `avoid` maps keyed by address. Each entry has address, date_added, weight and buys[] (mint, sym, ts ISO UTC, sig, sol, slot_offset, entry_mcap_usd). |
| wallets.csv / avoid.csv | humans and back-tests | avoid.csv columns start `address,reason,date_added,mints`. |
| fomo_candidates.md | Zero / Copycat | Proposals only, low confidence. |
| data/backtest_rugflag.txt | everyone | Per-coin verdicts against current outcomes. |
| scripts/refresh.sh | daily | Imports new radar mints, then runs early buyers, analysis, outputs, the rugger lists and rug flags on radar mints. |

## How scan.py could consume this (scan.py NOT modified)
1. **Rug gate, before any buy:**
   `v = json.loads(subprocess.run(["python3","/workspace/onchain-intel/rugcheck_creator.py",mint],capture_output=True,text=True,timeout=40).stdout)`
   - `block`: skip.
   - `caution`: skip, or half size with a tight stop. Same-slot bundlers sold 10-40 min after launch in every bundle coin we traced.
   - `unknown`: use the coin's other signals only.
   - `ok`: proceed.
2. **Wallet boost/veto:** get the buyers from GeckoTerminal `/networks/solana/pools/<pair>/trades` (tx_from_address, kind=buy).
   - Boost = sum of smart weights, capped at +1.
   - Any avoid wallet with weight −1 (creator) means veto. Two or more avoid wallets mean penalise.
   - For back-tests, ignore entries whose date_added is later than the test time.

## Rug flag: what it checks
1. **Same-block bundle:** the wallets that signed buys in the create slot, the % of supply they hold, their SOL, and the create-tx co-signers.
2. **Full-curve dev buy:** the creator buys more than 80 SOL or more than 70% of supply in the create tx.
3. **Known ruggers:** whether the creator or launch-slot buyers are already in known_ruggers.json. Evidence that comes only from the same mint is ignored, so there is no look-ahead.
4. **SOL funding:** the creator is traced 2 hops back, and the top 10 launch-slot buyers 1 hop. These are checked against known ruggers and funders, and for whether several buyers share one funder (one operator).
5. **Fresh creator:** funded less than 1 h before launch with more than 50 SOL.
6. **rugcheck.xyz** summary as a cross-check.

**Key trick:** the create tx is found through the pump.fun bonding-curve PDA (pure-python derivation in scripts/pda.py). Its history is short and starts at the create tx, so the launch is reachable even for coins with more than 700k signatures. Recent mint history is merged in, to catch AMM buys in the create slot when the curve graduates inside the create tx.

## Back-test (in-sample, 20 coins, outcome = current mcap; dumped means under $10k)
- **block (7):** MrBeast, FOMO, NVIDIA and Weazel dumped. Kimchi ($9.5M), YMB-DJT ($936k) and MOON ($49k) are alive.
- **caution (9):** CI, GRINDCORE and SPIKE dumped. ODIE ($2.7M), McNugget, McRib, BITCHES, MCRIBUNKS and TRUTH are alive (the last three are less than 1 h old).
- **ok (4):** YMB dumped (dev bought 5 SOL and sold within 46 s; the flag misses this). ARCTIS, YAGI and DacityCoin are alive.
- **unknown (1):** NAMI (not a pump.fun mint).
- **Summary:** 7 of the 8 dumped coins got block or caution. 4 of the 8 got block, and 4 of the 7 block verdicts dumped.
  - Full-curve dev buy (~86 SOL in the create tx): 4 of 5 dumped. Kimchi is the exception.
  - Multi-wallet same-slot bundle: 1 of 5 dumped (CI).
  - The sample is tiny. The funder lists were built from these same coins, so these numbers are optimistic.

## Launch recipes found (on-chain)
- **A. Full-curve dev buy.**
  - The creator buys ~793M tokens for 86.08 SOL in the create tx, so the coin graduates at once. It then sprays tokens to many wallets (fake holders).
  - One wallet buys 150-200 SOL in slot 0 and exits +40 to +178 SOL within 11-55 min.
  - The creators were funded with 168-761 SOL from wallets that had themselves been funded 1-3 min earlier (layered fresh wallets).
- **B. Multi-wallet same-slot bundle.**
  - 13-24 wallets buy 81-94% of supply in the create slot, and the create tx is co-signed by 3-4 buyers.
  - Dev buys ~0.057 SOL. CI, ODIE, BITCHES and MCRIBUNKS have near-identical create-tx amounts.
  - In each coin, all bundle wallets were funded by ONE hub wallet:
    - ODIE: B6atrmW8… (24 wallets)
    - CI: Dv8nB7tB… (22), whose own funder was 86Zmo5PF…
    - BITCHES: 4UWn9Tmw… (22), funded by HJM6zHjo… with 1189 SOL
    - McNugget: iGdFcQoy… (8 traced)
  - No hub was shared across coins in 2 hops, so these are probably separate operators or the trace stops at exchanges.

## Job 0: operator watch (scripts/operator_watch.py, merge_operator.py)
- 42 operator wallets went into avoid.csv and known_ruggers.json: 11 creators behind 11 coins, in 7 SOL-funding components. No single link was proven within 16 hops. Successor wallets under watch: AKEQ5hwS…, GvCcBUHH…, EJdSQJYg…, A4GyQWak…. 12 radar signals were tagged in signal_verdicts.jsonl.

## Job 1: early-buyer mining (scripts/early_buyer_miner.py)
- Runners are pump.fun mints with peak mcap at least $250k and at least 100x from the pump curve launch price. FDVs above $50M are skipped as likely manipulated. Peaks come from GeckoTerminal hourly closes.
- From each runner I take the first 20 non-creator buyers, then drop bots and known ruggers, and keep only wallets active in the last 30 days.
- Result: 20 runners, 357 early buyers, 187 kept (91 bots and 79 ruggers dropped). They are in smart_wallets.json under "early_buyer". No wallet was early in two runners.
- cluster_buys.jsonl has 84 clusters (3 or more of these wallets buying one mint within 30 min); 80 of them are not seed runners. The top examples (VIBE, INCOGNITO, ELON, ALPENPEPE, PUMPCITY, JEW) are all dead now at about $2-12k. **Do not use clusters as a buy signal.** At most they are a weak veto/context.
- Caveats: profiles stop at 300 token-in txs, so busy wallets only show recent days. All runners are recent (Oct 11-23).

## Job 2: trader histories
- trader_trades.csv has one row per round trip. legs() uses accountData net balance deltas, which fixes the double counting on multi-hop routes. ETT: 134 rounds, 108 closed, median -0.3%. _benjitrades: 42 rounds, 32 closed, median -14.5%.
- **trader_swaps.csv** has one row per swap: trader, wallet, timestamp (ISO UTC), mint, side, sol_size, usd_size, mcap_at_fill, signature. ETT 441 swaps and benji 727 run 09-24 → 10-23; BtheBezel 355 runs 09-25 → 10-22. bystevenr (from 10-08) and pointfarmcap (from 10-16) are cut short by the 10-page fetch cap (LR_MAXPAGES).

## Job 3: copyfomo leader re-rank (scripts/leader_rank.py, leader-rank.md; weekly on Sunday via refresh.sh, or FORCE_LEADER_RANK=1)
- Copy filter: first round per mint, entry mcap at least $100k, $50 per copy. Ranking: not cut, then at least 30 trades, then positive-week share, then win rate, then worst drawdown.
- Only **_benjitrades** passes every filter, and it is weak: 31 copies, 29% win, 2 of 5 positive weeks, +$11, worst drawdown $187, 42% of coins now under $10k. Probation.
- **ExactTallTakin** (current leader) is cut and I recommend dropping or pausing it as a copy leader.
  - All of its 30-day copy profit is one $SI round in W39. The four weeks since were negative: -65, -101, -113, -131, so -$411 without the best week.
  - 72 of 116 closed rounds were held under 60 s, which copiers cannot match.
  - 12 first entries came less than 60 s after the pair was created. 60% of its coins dumped.
  - Lab's -$140 over 108 copies is confirmed in direction. Over ETT's 108 closed rounds in trader_trades.csv (buys from Oct 1), a $50 copy comes to **-$104.65** before slippage and fees, so Lab's -$140 is plausible. The only reason our 30-day number is positive (+$915 on filtered copies) is the SI round on 09-25 → 09-30.
- bystevenr: +$2.5k copy PnL, but only 25 trades (history truncated), 7 launch-snipe entries, low mapping confidence, and earlier notes put copier slippage at +72%. Watch.
- pointfarmcap: lowest drawdown ($59), median entry mcap $1.1M, but only 13 trades in the fetched window. Watch.
- BtheBezel: 16% win, -$224, 8 snipe entries. Drop.
- zelda89, cosby and Altcoinist: the mapped wallets have almost no Solana swaps, so the mapping is likely wrong or the trading is on EVM.

## Leaderboard handle → wallet mapping (data/leader_mappings.json)
- None of these mappings comes from the trader's own post; every source is a third-party X post or the unrecorded trader-analysis/wallets.json.
- Medium: ExactTallTakin AGdtsMm…. A third-party post lists the wallet, and on-chain trades match posted ones (full $SI exit on 09-30, SI and Dacity rebuys at around $10M MC).
- Medium-low: pointfarmcap Beqv6dzT…. Several third-party posts give the same SOL and EVM pair.
- Low: _benjitrades, BtheBezel, bystevenr, cosby, Altcoinist, zelda89.
- **No wallet found** for the other 26 handles; the list is in leader-rank.md.

## Old-coins intel (scripts/oldcoins.py -> oldcoins-intel.json), meant to run hourly
- **Universe (since 2026-10-24):** Solana tokens at least 3 d old, mcap (or FDV) $3M–$1B, summed liquidity ≥ $300k, 24h volume ≥ $750k. There is no top-N cut.
  - Exclusions are unchanged: stables, wrappers, LSTs, tokenized stocks, JLP.
  - Candidates come from GeckoTerminal (volume pages 1–10, trending pages 1–2), DexScreener, Jupiter lite-api, Chunk's oldcoins-universe.json (tokens/core/wide) and the seed file.
  - **Measured:** ~385 candidates gave a universe of only **19**. The filters bind (most old Solana coins are below $750k/day or $300k liquidity), not the sources.
  - Priority mints (tiers 1–3) are checked even when they fail the filters. These carry `in_universe:false` and `universe_reject`.
- **Tiers** (doc field `tier` / `tier_name`):
  1. Chunk holds it: live/oldcoins-live.jsonl net open, or paper positions.
  2. A Chunk setup in the last hour: any event in oldcoins-paper.jsonl or oldcoins-live.jsonl within 3600 s, including would_short.
  3. copycat_held: selfcopy/state.json open positions, selfcopy/live-trades.jsonl net open, the latest x-watch-log.md status with "CA <mint>", or the TEAM-BOARD Copycat line. The TEAM-BOARD line has no CA, so it is noted rather than resolved.
  4. The rest, by 24h volume.
- **Depth** (`check_depth`):
  - Full checks run for tiers 1–3, plus `rotate_n=8` tier-4 tokens per run. Rotation picks the oldest `_rotation` timestamps and runs only while runtime is under 60% and budget allows (`rotation_full_check:true`).
  - Light checks keep rugcheck (3 h cache), DexScreener and LP change, and skip the tx scans. They use a balance-delta caution instead.
  - `doc.coverage` holds universe_size, by_depth, by_tier, tier4_rotation_full, notes and setups.
- **Alerts:** strong_support, new_avoid_on_held, and new_avoid_on_copycat_held.
- **Results:**
  - **Run 2026-10-24T00:04Z:** 20 checked (19 universe + Moustache priority-only). 14 full, 6 light. Tier 2 = 5 (RAY, ANTFUN, ANSEM, JUP, BP), tier 3 = 1 (Moustache), tier 4 = 14 (8 rotated). 24 Helius credits, 157 s.
  - **Run 00:17Z (with hypothesis fields):** same counts, 0 Helius credits, 539 public RPC calls, 253 s. All 20 neutral, 0 alerts.
- **Top-10 share, smart money, large sells, LP change, verdict rules:** unchanged from before.
  - Top holders come from rugcheck topHolders (20 accounts), with pools, programs and burn addresses excluded and a custodial (>20k SOL) variant.
  - The LP change is price-adjusted as liq_ratio/sqrt(price_ratio) − 1. A drop of 20% or more counts as an LP pull.
  - Verdict rules are listed in the JSON (verdict_rules).
- **Credits:** Helius is a fallback only. Each call is logged as "oldcoins-rpc 1" in data/rpc_calls.log. The run cap is min(1500, 30000 − today's total). Measured runs used 0–94 credits.

### Hypothesis fields (UNTESTED; `hypothesis_fields`, every field has `affects_verdict:false`)
These are recorded only. They never change a verdict or an alert. Lookups use public RPC only (0 Helius credits) with a cap of `hyp_public_call_cap=700` public calls per run. When the cap is hit, the field is null and the reason is noted.
- **max_single_holder_pct:** the largest holder that is not a pool, program or burn address (wallet or unknown class). It also has an `_ex_custodial` variant. **Flag** is `max_single_holder_flag = ex-custodial value > 5%`. Computed for all tiers, at no cost (from rugcheck data).
- **top_holders_linked_pct:** full checks only. Covers the top 10–20 non-pool holders from rugcheck. A holder counts as linked if it shares a funder with another holder, or if its first acquisition of the token is in the same slot as another holder's.
  - The funder is the source of the wallet's first incoming system transfer, or the first tx's fee payer if there is none, found within `hyp_sig_pages=2` signature pages.
  - The field is the % of supply held by linked holders.
  - Exchange-like funders are ignored as links: anything in data/custodial_funders.json, or any funder holding over 20k SOL.
  - Caches: wallet profiles in cache/wp_<owner>.json and first-acquisition slots in cache/fa_<acct>.json (no expiry, since history is immutable). Per-mint results go in cache/hyp_<mint>.json for 6 h, keyed by the holder set.
- **fresh_holder_pct_top50:** full checks only. The % of supply held by holders whose wallet's first signature is under 7 days old.
  - If the 2-page cap is hit before the first signature is reached, the wallet is treated as older than the pages seen, so it counts as not fresh.
  - Rugcheck only returns 20 holders, so this is really computed over the top ≤20. The JSON notes this.
- **vol24h_mcap:** DexScreener 24h volume ÷ mcap (or FDV).
- **stair_step** (GeckoTerminal `/ohlcv/minute?aggregate=1` on the top pool): uses the last 60 one-minute candles and needs at least 40. TRUE only if **all** of the following hold:
  1. Up-candles (close > open) are at least 60% of candles.
  2. The net change from the first open to the last close is at least +2%.
  3. No single candle moves more than 1% (|close/open − 1| ≤ 1%).
  4. Maximum drawdown of closes from their running peak is at most 1.5%.
  5. Volume coefficient of variation (stdev/mean) is at most 0.6.
  6. Second-half volume ÷ first-half volume is between 0.67 and 1.5.
  - Each sub-metric is stored alongside the flag. If there are fewer than 40 candles, or the fetch fails, the value is null.
- **Sample (00:17Z):** Dacity linked 5.7% / fresh 12.8%; STONK linked 10.8% / fresh 10.0%; MEW fresh 39.2% and max single holder 37.9%; Kimchi max single holder 75.3%; Moustache vol24h/mcap 2.82. No stair_step was TRUE. None of these are validated as rug signals yet.

### Custodial-funder finding (resolved 2026-10-24T00:53Z, Zero approved)
- Zero's rule: a funder moves to custodial_ignore.json only if a public label confirms it's an exchange or custodial hot wallet. Unlabelled funders stay in known_ruggers.json. Exchange funding is neutral, not a pass.
- Moved 5 funders, each labelled on its Solscan account page (label plus `exchange_wallet` tag, fetched 2026-10-24T00:53Z; source URL is in the file):
  - iGdFcQoy… = Bybit Wallet 10
  - 5tzFkiKs… = Binance 2
  - u6PJ8DtQ… = Gate Hot Wallet (u6PJ8)
  - A77HErqt… = Bitget Exchange
  - BmFdpraQ… = KuCoin Hot Wallet (BmFdp)
- Removed them from known_ruggers.json "funders" (66 → 61; wallets unchanged at 137) and from known_funders.csv (5 rows). Backups are at data/known_ruggers.json.bak-20261024T005312Z and data/known_funders.csv.bak-20261024T005312Z.
- To stop them coming back: scripts/apply_custodial_ignore.py runs in refresh.sh after build_known_ruggers and after merge_operator, and rugcheck_creator.py also drops custodial_ignore addresses from FUN when it loads. rugguard.py and scan.py were not edited.
- Original context: all 5 hold over 20k SOL (392k / 1.49M / 328k / 104k / 31.8k) and are also in data/custodial_funders.json, which oldcoins ignores.

## refresh.sh trim (2026-10-24; backup data/refresh.sh.bak)
- **Goal:** about 10k Helius credits per 18:00 run, as a hard cap. The shared budget file data/refresh_budget.json is set to REFRESH_HELIUS_LIMIT=10000.
  - sol.py `budget_take()` (fcntl-locked) books 1 credit per RPC call, 100 per enhanced page and 10 per gtfa page.
  - Once the budget is spent, calls are denied and the step degrades to public RPC or stops early.
  - Every refresh step runs with `SCOUT_PUBLIC_FIRST=1`: 6 public RPC tries before Helius.
- **Logging:** per-step credits used and denied go to data/refresh_budget.log.
- **What was cut:**

  | Step | Before | After | Notes |
  |---|---|---|---|
  | early_buyers mint signature pages (EARLY_MINT_PAGES) | 400 | 60 | Mints that hit the cap go to data/early_deferred.txt and are not cached, so they are retried later instead of being saved half-done. |
  | early_buyers bonding-curve pages (EARLY_BC_PAGES) | 60 | 40 | |
  | trader history enhanced pages (TT_MAXPAGES) | 20 | 3 | 100 credits each; cached histories are reused. |
  | leader re-rank pages (LR_MAXPAGES) | 10 | 4 | Sunday only |
  | leader watch-list pages (LR_WATCH_MAXPAGES) | 25 | 8 | |
  | rugcheck_creator | all radar mints | radar mints from the last 2 days only | Via scripts/recent_radar_mints.py (8 mints at the time of writing). |

- **Unchanged:** defaults when the env vars are unset, so rugguard and the other live callers behave as before. rugguard.py, scan.py and rugcheck_creator.py were not edited.
- **Status:** `sh -n` passes; not yet run for real. Check refresh_budget.log after the next 18:00 run.

## Data sources
- **Helius RPC (key present, never printed):** faster and deeper. Mint history goes past 700k signatures, where publicnode caps at 400k. Calls are throttled to 7.5 rps per process and counted in data/rpc_calls.log (count only). ~8.3k calls were used today, all 1-credit RPC. Enhanced/DAS APIs were not needed. DAS getAsset gives supply and price but not the creator for pump.fun coins.
- **Free sources:** publicnode and mainnet-beta RPC (fallback), DexScreener, GeckoTerminal (~30/min, shared with the radar), rugcheck.xyz.
- **Blocked (Cloudflare/403):** Solscan, pump.fun, GMGN.
- **Birdeye:** not available.

## Limitations (honest)
- 20 coins is a small sample, and wallet PnL only covers each wallet's own token-account history for these coins (up to 400 txs).
- There are only 4 "smart" wallets, all early-trading bots or flippers in bundle coins. The best one, 7FPqg7Mp…, has weight 0.6, 10 coins, 8/10 wins and +0.93 SOL in total. That is small edge and not copyable alpha.
- A funding trace stops at exchanges or hubs. "Weak" funders (1 rugger funded) may be exchanges.
- FOMO handles cannot be mapped to wallets with our data.
