# winners/: "learn from winners" dataset (batches 1+2, partial)
Batch 1 built 2026-10-24 ~00:45 UTC; batch 2 appended ~01:45 UTC by scout. Read-only on-chain analysis: no trading, no keys, nothing posted.

## Status
- **Wallets:** 8 of the 15–30 target. **Closed trades:** 387 of the 500+ target (batch 1: 141, batch 2: 246). Still partial.
- Batch 1 (4 wallets, 141 trades):
  - 9PB1RLFs… (_benjitrades): older_midcap, medium-low.
  - AH75Bn6Q… (bystevenr): fresh_launch, medium-low (only a 15-day window).
  - 5o3kAZLw… (neodot, Pulse/X): fresh_launch, medium.
  - zhYnXqK3… (onlyzhynx, Pulse/X): fresh_launch, low. Profitable only through outliers.
- Batch 2 (4 wallets, 246 trades; all confidence LOW, source gt-older-pools-screen = traders found in GeckoTerminal trades on older pools, then pulled via Helius gTFA):
  - HMDWTfG7… : swing, 45 trades, full 30d. Net5 +4.46 SOL, +0.79 SOL without best trade, median hold 169 min.
  - B1uHHQsB… : fresh_launch, 66 trades, full 30d. Net5 +4.55 SOL, +0.83 without best trade, median hold 9.1 min, small size (~0.18 SOL).
  - 82uFrGF6… : older_midcap, 41 trades, only 15.3 days. Net5 +25.1 SOL but −2.9 without its single +28 SOL trade. Copyfomo-relayed wallet (co-signer AgmLJB).
  - HJp8gAkS… : older_midcap, 94 trades, full 30d. Net5 +1.49 SOL (net3 +3.66), −1.45 without best trade.
- Batch-2 screen: 34 wallets checked (data/batch2_list.txt, stats in data/stats_wg_batch2*.json). Excluded: AHiBR6p8 (~breakeven, +0.28 SOL over 91 trades), TtHZJhWD (median hold 0.5 min), 30 others unprofitable or <30 closed trades. KOL/Copyfomo wallets were too spammy (fee/airdrop deposits) for a cheap screen. No positive-median trader was found in batch 2.
- All 8 pass these checks:
  - ≥30 closed trades, median hold >2 min, positive summed PnL after 3% and 5% costs.
  - Not in avoid.csv, known_funders.csv or known_ruggers.json.
  - 0 trades in coins they created (wallet_is_creator = 0 on every row with a known creator).
  - No buys in a create slot or create tx.
  - First funder not on any list.
- **Warning:** 7 of the 8 have a negative MEDIAN trade after 5% costs (9PB1 −19.5%, AH75 −6.5%, zhYnX −46.5%, HMDW −10.0%, B1uH −14.6%, 82uF −11.4%, HJp8 −11.2%). Their edge is a few big winners; 82uF and HJp8 are not profitable without their best trade. Only neodot has a positive median (+10.8%).
- **Credits:** batch 2 used 2,080 Helius credits (cap 2,500). Day total ~9.9k at 01:45 UTC.

## Files
- **trades.csv:** one row per closed round trip. A round trip runs from the first buy until ≥95% of the position is sold.
- **wallets.csv:** one row per wallet with stats after costs.
- Builder scripts are in /workspace/scout: build_winners.py, finalize.py, rc_creators.py and gtfa_fetch.py.

## Sources
- **Swaps:**
  - 9PB1 and AH75: Helius enhanced `type=SWAP`, cached 2026-10-23.
  - 5o3k and zhYnX: Helius `getTransactionsForAddress` (tokenAccounts=balanceChanged, 25 pages each).
  - Batch 2 (HMDW, B1uH, 82uF, HJp8): Helius `getTransactionsForAddress`, resumable pages (scout/gtfa_fetch.py).
  - Windows: batch 1 14–28 days; batch 2 30 days except 82uF (15.3 days). NOT always the full 30 days. wallets.csv `window_days` is the span from first to last closed trade.
- **Market context:** GeckoTerminal (GT) pools and OHLCV (5m candles, 288 before entry; 1m candles for stair_step). The candles are historical.
- **Holder and creator fields:** rugcheck `/v1/tokens/{mint}/report`, fetched NOW (2026-10-24), not at entry.
- **Self-created check:** pump.fun `coins?creator=`.
- **Activity:** 30-day signatures from public mainnet-beta, including spam.

## Field definitions: historical vs approximated vs now
| field | basis |
|---|---|
| entry/exit time, sizes, prices, pnl_*, hold_min | Historical (on-chain). pnl_pct_netX = gross % − X points; pnl_sol_netX = out − in×(1+X%). |
| age_at_entry_h | Historical: entry − GT pool_created_at of the top pool. Negative means the context pool was created after entry (e.g. a migrated pool), so treat it as approximate. |
| mcap_at_entry_usd_approx | APPROX: entry price × CURRENT supply (GT fdv/price; 1e9 for pump mints). Wrong if supply changed. |
| liquidity_at_entry_usd | BLANK: no free historical liquidity source. liquidity_now_usd is from rugcheck now. |
| vol_1h/6h/24h_usd | Historical: GT 5m candles before entry, summed for the context pool only (other pools excluded). vol_24h is blank if the pool is <24h old at entry. |
| chg_5m/1h/24h_pct | Historical: change of the last 5m close before entry vs the close at entry − 5m/1h/24h. Blank when there's no candle that far back. GT omits empty candles. |
| holders_at_entry, holder_growth, top10_share_at_entry | BLANK: no free historical holder snapshots. |
| smart_co_buys_30m | Historical: buys of the same mint within ±30 min of entry by wallets in smart_wallets.json ('smart'/'early_buyer'), onchain-intel/wallets.csv, or the other winners. Only counts wallets whose swaps are cached locally, so it is a lower bound. avoid_co_buys_30m is the same for avoid.csv wallets. |
| *_now fields | Rugcheck snapshot at build time, NOT at entry. max_single_holder_pct_now excludes AMM/LP/market/knownAccounts. top10_pct_now_incl_lp includes LP. |
| creator, wallet_is_creator | Creator from rugcheck. Blank when rugcheck has no creator (11%). |

## Rug-check hypothesis fields (untested, for Lab)
- **max_single_holder_pct (at entry):** BLANK. Historical holder snapshots are not available for free. The proxy `max_single_holder_pct_now` plus `max_holder_gt5_now` (flag >5%) uses the current rugcheck snapshot and has look-ahead bias: holders at entry can differ completely.
- **top_holders_linked_pct:** BLANK. It needs the funding graph of the top holders at entry, about 20+ first_txs lookups per mint (~200 Helius credits per mint), which this budget can't cover. The proxy `insider_top20_pct_now_rugcheck` (rugcheck's insider flags, current) is included.
- **fresh_holder_pct_top50:** BLANK. It needs the top-50 holders at entry plus a wallet-age lookup for each (~50 calls per mint). Not affordable, and not available historically.
- **vol24h_mcap:** vol_24h_usd / mcap_at_entry_usd_approx. Inherits the approximations of both fields. Blank when vol_24h is blank.
- **stair_step (exact definition):** uses GT 1m candles of the context pool in [entry − 1800 s, entry). Blank if there are fewer than 20 non-empty 1m candles. stair_step = 1 only if ALL of these hold:
  1. up_share (candles with close > open) ≥ 0.65
  2. the worst single-candle return (close/open − 1) ≥ −2%
  3. net change (last close / first open − 1) is between +5% and +100%
  4. the coefficient of variation of candle volume (std/mean) ≤ 0.6

  Otherwise it is 0. Helper columns: up_share_1m_30m, vol_cv_1m_30m, n_1m_candles_30m. On batches 1+2, stair_step = 1 for 0 of 107 computable trades.

## Coverage (387 trades)
- **100%:** trade fields, smart/avoid co-buys, *_now holder fields, n_1m_candles
- **99%:** liquidity_now_usd
- **93%:** age_at_entry_h, mcap_at_entry_usd_approx
- **86%:** creator / wallet_is_creator
- **81%:** vol_1h/6h
- **68%:** chg_5m
- **46%:** chg_1h
- **28%:** stair_step
- **22%:** vol_24h, chg_24h, vol24h_mcap
- **0%:** liquidity_at_entry, holders_at_entry, holder_growth, top10_share_at_entry, max_single_holder_pct, top_holders_linked_pct, fresh_holder_pct_top50

## Caveats
- **Partial windows:** batch 1 14–28 days instead of 30; 82uF 15.3 days.
- **Batch 2 is outlier-driven:** all 4 new wallets have negative medians; treat as low-confidence examples, not copy candidates.
- **AH75:** only about 15 days of data.
- **Signature activity (sigs_per_hour_30d, night_hours_active_share_30d)** counts all signatures, including spam, so it overstates trading activity. trades_per_night counts closed round trips, with night = 21:00–08:00 Europe/Dublin.
- **Pool-only volume:** volume comes from the single context pool (the top GT pool now). That pool may not be the pool traded at entry, e.g. pump bonding curve vs a migrated pool.
- **Creator-funding links** were only checked for creators with a known funder in data/funding.json (9 of 111). No links were found, but the check is partial.
- **Wallet-specific notes:**
  - neodot's funder Dv34prGm… also funded 3ntjjwpq…, an early SPIKE buyer (weak link).
  - onlyzhynx created 10 pump.fun coins in Mar–Apr 2026, outside the window.
- **Pulse leads:** /workspace/x-intel/copy-leads.md exists with 6 leads. On-chain verdicts are in /workspace/scout/copy-candidates.md.
