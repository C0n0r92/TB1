# runner-radar (PAPER ONLY)

Tries to spot Solana memecoins **early in a run**, logs them, then measures what really happened.
No trading, no wallets, no keys, no sign-ups, never posts anywhere. Stdlib Python only.

## Run
```bash
cd /workspace/runner-radar
python3 scan.py                 # one scan (~25-40 s), appends new candidates to signals.jsonl
python3 scan.py --threshold 50  # looser
python3 grade.py                # grades every past signal -> outcomes.csv + summary
python3 grade.py --bet 5 --stop -0.25 --tp 2 --fee 0.02
nohup ./run_loop.sh 12 &        # scan every 10 min + grade hourly for 12 h (logs: scan.log, grade_latest.txt)
python3 variants.py             # paper-grade rule variants A-E -> variants_latest.txt + variants.csv (~20 s first run)
```
Files: `signals.jsonl` (signals, deduped per token), `scanned.jsonl` (every evaluated pair incl. rejects/low
scores, for re-tuning thresholds later), `outcomes.csv`, `grade_state.json` (fallback max/min seen).

## Data sources (all free, public, verified working 2026-10-23)
| Source | Used for | Notes |
|---|---|---|
| DexScreener `token-profiles/latest`, `token-boosts/latest`, `token-boosts/top`, `community-takeovers/latest`, `latest/dex/search` | discovery | ~60 req/min on these; boosts/profiles are *paid promotion*, a biased pool |
| DexScreener `/tokens/v1/solana/<≤30 addrs>` | price, mcap, liq, 5m/1h txns, volume, pair age | ~300 req/min |
| GeckoTerminal `trending_pools?duration=5m/1h/6h`, `pools/multi`, `ohlcv/minute?aggregate=5` | discovery, **unique buyer counts**, 5-min candles for grading | ~30 req/min; script spaces calls 2.1 s |
| rugcheck.xyz `/v1/tokens/<mint>/report` (no key) | mint/freeze authority, top holders w/ owners, market vault accounts, insider-network flag | ~1 req/s used |
| Solana public RPC `getAccountInfo` | fallback for mint/freeze authority | `getTokenLargestAccounts` is **429-blocked** on the public RPC (and publicnode/drpc/ankr need keys), hence rugcheck |
GeckoTerminal `new_pools` is useless here: 200 newest pools ≈ last 5 minutes of pump.fun launches.

## Scoring (0–100, signal if ≥ 55 and no hard reject)
Prefilter: pair age 15 min–6 h, mcap $50k–$2M, liquidity ≥ $15k. Best-liquidity pair per token.

Momentum (~60 pts)
- Volume acceleration = 5m volume ÷ (1h volume / 12): 1x→0, 3x→18
- 5m price change: +2%→0, +20%→12; **chase penalty −10 if 5m > +60%**
- 1h price change: 0→0, +150%→8
- Buy share of txns: 5m (50→70% = 6), 1h (50→65% = 4)
- Unique-buyer growth (GeckoTerminal) = 5m buyers ÷ (1h buyers / 12): 1x→0, 2.5x→12

Health (~40 pts)
- Liquidity/mcap: 0.05→0, 0.20→10
- Mint + freeze authority revoked: +8
- Top-10 holders excluding pool vaults/AMM accounts: <15% +12, <22% +8, <30% +4
- Age 0.5–3 h +5, else +2
- Insider network flagged by rugcheck −5; copycat ticker (≥3 live tokens same symbol) −8

Hard rejects: health data unavailable, rugged, mint or freeze authority active, top-10 > 35%,
liquidity < $10k, sells ≫ buys (1h sells > 1.5× buys, or 5m sells > 2× buys).
All token names/symbols are untrusted and stripped to `[A-Za-z0-9 $._-]`.

### Rug guards (`rugguard.py`, added 23 Oct 2026 ~22:15 Dublin)
Why: all 7 live signals on the first night (GRINDCORE, YMB, CI, NVIDIA, Weazel, FOMO, Mr Beast) went −86…−100% within
minutes. On pump.fun/pumpswap coins the checks above are passed by **every** coin (mint/freeze revoked, LP 100% burned
by pump.fun, top-10 spread thin on purpose), so they told us nothing. The rugs were **operator coins**: one fresh
wallet buys the whole bonding curve in the create tx (NVIDIA, Weazel, FOMO, Mr Beast all = 86.077 SOL dev buy → instant
graduation; CI = 24-wallet same-slot bundle with one funder), spreads tokens over many small wallets, wash-trades to fake
volume and "unique buyers" (which the momentum score rewards), then sells into the pool. LP stays burned; the pool's SOL
side is drained (e.g. NVIDIA: $89k liquidity → $36 of SOL). **LP lock is not what protects you here.**

New hard rejects (reasons appear in `rejects`):
- pair younger than **45 min** (coin is re-scanned later, so it can still signal once it has survived)
- rugcheck `totalHolders` missing, **< 300 holders**, or **> $1,500 market cap per holder** (rugs: $700–12,700; organic: $25–420)
- **wash trading**: GeckoTerminal 5-min unique buyers ≥ total holders (FOMO 959 buyers vs 84 holders)
- **5-min price ≤ −50%** (dumping now) or **≥ +150%** (vertical candle)
- **liquidity down ≥ 30%** vs an earlier scan of the same token in the last 90 min
- any rugcheck **danger**-level risk; traded pool **< 50% LP locked/burned**; creator still holding **> 5%**
- **Scout launch forensics** (`/workspace/onchain-intel/rugcheck_creator.py`, run as a subprocess only for coins that
  would otherwise signal, max 4/scan, 60 s timeout; it uses Scout's own Helius config, scan.py never reads a key):
  reject a **full-curve dev buy** in the create tx, a creator that is a **known rugger**, or a creator **funded by a known
  rugger/funder**. If it's unavailable the coin is not rejected (reason "launch check unavailable").
Penalties: same-block bundle / one funder −10, Scout caution −4 (other block flags −8), mcap/holder $700–1,500 −10,
buyers/holders ≥ 0.4 −8, 5m −25…−50% −6, creator with ≥ 3 other tokens −8.
`scanned.jsonl` rows now carry an extra `guard` object (holders, buyers5, lp_locked, danger, creator, creator_pct,
quote_usd, guard_penalty) for re-tuning. **`signals.jsonl` rows are unchanged** (same keys as before).
`python3 scan.py --dry-run` evaluates and prints without writing anything. Pre-guard version: `scan.py.bak-20261023-prerugguard`.

Back-test on that night's `scanned.jsonl` (28 coins, holder counts/Scout checks fetched afterwards, so optimistic):
all guards reject 11/11 rugs; without the age gate 9/11 (misses GRINDCORE, KIMCHICITY: slow dumps with 2k+ holders).
Holder/wash rules alone: 8/11 rugs, 0/16 "survivors" rejected. Insider-network flag was *not* predictive (more common
on survivors), so it stays a −5 nudge. LP-lock/danger rules caught 0 rugs (2 unlocked-LP coins survived) but stay as
basic safety. "Survivors" were only 0.5–5 h old at test time; several (Grok, GTA6 Coin, Speed) are full-curve operator
coins that hadn't dumped yet.

## Grading
For each signal: GeckoTerminal 5-min candles starting **after** the signal time (no look-ahead).
Records close at +1h/+4h/+24h, max run-up within each window, overall max/min, current return,
hit-2x flag, and a hypothetical $5 bet: −25% stop, sell half at 2x, rest marked at the last candle
(≤ 24 h), 2% fee on each buy and sell. Approximations: entry = DexScreener price at signal time (real fills
worse); stops fill exactly at −25% (real memecoin stops gap lower); if one candle touches both stop and 2x
the stop is assumed first. If candles are missing, falls back to prices polled when grade.py ran ("polled").
**Judge it only after ~50+ matured (24 h) signals.** A handful of signals means nothing.

## Paper variants (`variants.py`)
Re-plays **every evaluated coin** in `scanned.jsonl` under several rule sets and grades each pick with grade.py's own
`simulate()` ($5 bet, −25% stop, half at 2x, 2% fee per side, only candles starting after the signal), plus an
**08:00 Europe/Dublin close** (the live wallet's rule). Reports 1h/4h/24h median returns too. Never touches scan.py,
signals.jsonl, the threshold or `live/`.

| Var | Rule |
|---|---|
| A | baseline: score ≥ 55, no hard reject (= live signals) |
| B | strict: score ≥ 65 |
| C | loose: score ≥ 50 |
| D | A + Pulse X buzz: rising buzz +5 to the score, skip fading buzz or anything on a rug list (`/workspace/x-intel/hot.json`, `/workspace/x-intel/rugs.json`, `/workspace/x-pulse/latest.json`) |
| E | A + Scout on-chain: skip if the token, its creator or a top holder is on `/workspace/onchain-intel/avoid.csv`; +5 per smart wallet (max +10) from `smart_wallets.json` (wallet is a top holder, or a *timestamped* buy before the signal) |

**Point-in-time / no look-ahead.** Each run copies the intel files into `intel_snapshots/` when their content
changes (valid from the file's mtime). A signal may only use the newest snapshot that existed at signal time
(X files ≤ 2 h old, rug list ≤ 7 d, on-chain lists ≤ 48 h), and entries with their own timestamp
(`ts`, `first_seen`, `flagged_at`, `added`…) only if that is ≤ signal time. Untimed smart-wallet buys are ignored.
For E, `--snapshot-only` (run right after each scan) records the top holders + creator of fresh candidates from
rugcheck into `intel_snapshots/holders.jsonl`; holder lists fetched > 15 min after the signal are ignored.
If a variant's inputs don't exist (or weren't fresh at any signal time) it shows **"waiting for data"**, never a
guess. Candidates from before the data existed are counted in `uncovered`, not graded. Parsers are tolerant
(lists, `{mint: {...}}` dicts, `trend`/`direction`/`status` words like rising/fading, numeric `velocity`/`delta`,
`ca`/`mint`/`token`/`address` keys); Pulse/Scout should include a contract address and a timestamp per entry.

Outputs: `variants_latest.txt` (table + per-trade list), `variants.csv` (one row per night × variant, upserted
each run; `status` = provisional until every pick is past its 08:00 close and 24 h): `date, variant, signals,
wins, losses, hit_2x, median_return, sim_pnl`, then `status, staked, open_or_ungraded, med_ret_1h/4h/24h,
uncovered, sim_pnl_gapfill, updated`. **`sim_pnl_gapfill`** re-runs the same trades but a stop that a candle
crashes through fills at that candle's close/open instead of exactly −25%, which is closer to real rug/dump fills.
`median_return` = median bet return under the 08:00-close rule. Night = Dublin date the evening started.
Candles are cached in `candles_cache/` (anchored with `before_timestamp` so >25 h-old windows still grade).
Options: `--snapshot-only`, `--no-fetch` (cache only), `--bet/--stop/--tp/--fee`, `--x-intel/--x-pulse/--onchain/--out-dir` (testing).
Caveats: scan.py never re-scans a coin after it signals at ≥55, so B can't catch coins that later rise to 65 and
C/D/E only see re-scans below 55; no max-3-open-positions or 15% chase rule is simulated; tiny samples are noise.
`run_loop.sh` calls it (snapshot after each scan, full grade hourly) for loops started after 23 Oct 2026 20:45 UTC;
the loop already running that night has a companion `variants_loop.sh <until-epoch>`.

## v2 signal ideas
1. **X mention velocity per contract address** – count posts mentioning the CA/$ticker over 5/15/60 min
   via Grok Bot's X reads (limit 30/min, 1000/day → only check the top ~5 candidates per scan, ~10–20/hour).
   Score acceleration of *distinct, aged, non-bot* accounts, not raw count; penalise shill templates.
2. **FOMO trader convergence** – put ~10 vetted FOMO traders on copyfomo `/alerts` (watch-only) and flag
   coins that ≥2 of them buy within ~30 min; cross with this scanner's health checks. Convergence of
   independent good traders is probably the strongest early signal we can get.
3. **"Early caller" list** – backtest: for each past runner in `outcomes.csv` (hit 2x), find which X accounts
   mentioned the CA first and how early vs the run; keep accounts that are repeatedly early *and* not just
   dumping on followers. Their first mention becomes a signal.
4. Others: buyer-wallet quality (are first buyers fresh wallets/bundles?), dev wallet history from rugcheck
   `creatorTokens`, Base chain via DexScreener + GeckoTerminal (no rugcheck → needs a contract check, e.g.
   honeypot simulation), logistic-regression weights fitted on `scanned.jsonl` once outcomes exist.
