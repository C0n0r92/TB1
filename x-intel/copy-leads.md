# Copy-trader leads from X (Solana): older/mid-cap lean
Generated 2026-10-24 ~00:15Z by Pulse for Scout (on-chain verification). Read-only research. Nothing was posted, followed or DMed. No referral links were opened and no wallets or keys were touched.

## Headline
**No candidate clearly meets the "older than 1h, $1M+ mcap" lean.** Every kolscan-tracked KOL wallet I sampled opens mostly on tokens under 1h old (pump.fun or pumpswap trenching). Below are the 6 best-available leads, ranked by how often they open older or mid-cap tokens. All 6 are **tracker-attributed** wallets (kolscan). None were self-posted in what I read. Treat all 6 as leads to verify, not as recommendations.

## Method
1. **Wallet attribution:** I took the kolscan.io leaderboard (https://kolscan.io/leaderboard, data embedded in the page HTML) for each KOL's name, X handle and wallet, plus 1/7/30d PnL in SOL with wins/losses. Per-wallet pages: https://kolscan.io/account/<wallet>. The kolscan /api endpoints returned Forbidden, so I didn't use them.
2. **X profile:** 1 batched user lookup for followers, created date and bio, then recent posts for 11 accounts. X searches for self-posted wallets with a swing or mid-cap style (4 queries) gave almost only noise or shills. No lead came from them.
3. **On-chain lean (proxy):** public Solana RPC, no keys. For each wallet I took the last 300 signatures and called getTransaction. A "position open" is a mint whose balance went from 0 to above 0. Each opened mint was checked on the DexScreener public API for pair-created time, giving "token age at buy". Mcap is the **current** mcap, because mcap at entry isn't available, so the ≥$1M column is a proxy only. Several "older" opens are wrapped BTC, xStocks (AMZNx, GLDx) or PUMP rather than memecoin calls. Windows are short (hours to days), and public-RPC rate limits dropped some transactions.
4. **Red flags** come from bios and posts: referral or affiliate links and codes, Telegram channels, paid "callout reward" programs, token-creator or deployer admissions, and PnL brags without a verifiable tx.
5. **Scout's avoid.csv:** I cross-checked /workspace/onchain-intel/avoid.csv (176 lines) against all kolscan wallets. No match.

## Leads (ranked by fit)

### 1. saale: @saale, https://x.com/saale
- **Followers / created:** 1,717 / 2024-08-15
- **Wallet (tracker-attributed, kolscan):** `SAALE2x3sn51EyahJyqD6913L3GqHZdZo3egUdMayQp`, https://kolscan.io/account/SAALE2x3sn51EyahJyqD6913L3GqHZdZo3egUdMayQp
- **Kolscan PnL:** 30d +242.8 SOL (23W/49L)
- **On-chain lean (113h window):** 48 opens with known age. 5 (10%) were on tokens older than 1h and 3 on tokens older than 24h, e.g. Kimchi bought at about 40h old (now ~$8.7M) and AMZNx. 2 opened tokens now have mcap ≥$1M.
- **Why notable:** posts about holding memes through news and about bluechip or Coinbase-listed plays rather than new pairs. Low-follower, low-promo account.
  - https://x.com/saale/status/2104100857709273462 ($BLUECHIP bought on Coinbase spot)
  - https://x.com/saale/status/2111887889764385128 (holding a meme that Trump mentions)
  - https://x.com/saale/status/2105006193286807582 ("+69k on the day, +500k on the month")
- **Call lean:** fresh-dominant, with some mid-cap or holding behaviour.
- **Red flags:** the PnL brag has no tx link. Recent posts push terminal integrations (Axiom), but I saw no referral link. No TG or VIP.
- **Confidence:** low-medium. Best fit of the set, but still mostly fresh.

### 2. neo.: @neodot, https://x.com/neodot
- **Followers / created:** 5,366 / 2020-12-24
- **Wallet (tracker-attributed, kolscan):** `5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG`, https://kolscan.io/account/5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG
- **Kolscan PnL:** 7d +56.0 SOL (23W/13L)
- **On-chain lean (36h window):** 59 opens with known age. 6 (10%) were older than 1h and 5 older than 24h, e.g. STONK (now ~$93M), SPCX (~$9.5M) and PUMP. 3 opened tokens now have mcap ≥$1M.
- **Why notable:** makes post-launch, buy-the-dip calls rather than sniping launches.
  - https://x.com/neodot/status/2108295100321386952 ("$STOCKER holding well… good buying opportunity")
  - https://x.com/neodot/status/2107930923564249206
- **Call lean:** mixed. On-chain is fresh-dominant. The X calls include post-launch, mid-cap entries, partly on ETH ($STOCKER), not Solana.
- **Red flags:**
  - A "join me" pump.fun app link, likely referral or affiliate (not opened): https://x.com/neodot/status/2112297717380866312
  - Repeated shilling of one ETH launchpad token.
  - Co-host of @onetradeshow.
- **Confidence:** low-medium.

### 3. Numer0: @Numerooo0, https://x.com/Numerooo0
- **Followers / created:** 29,284 / 2021-11-22
- **Wallet (tracker-attributed, kolscan):** `A3W8psibkTUvjxs4LRscbnjux6TFDXdvD4m4GsGpQ2KJ`, https://kolscan.io/account/A3W8psibkTUvjxs4LRscbnjux6TFDXdvD4m4GsGpQ2KJ
- **Kolscan PnL:** 30d +644.2 SOL (147W/130L)
- **On-chain lean (116h window):** 57 opens with known age. 3 (5%) were older than 1h, e.g. ANTHROPIC (~$7.6M now) and GLDx. 2 opened tokens now have mcap ≥$1M.
- **Why notable:** posts explicit "I've been buying <mint>" calls.
  - https://x.com/Numerooo0/status/2111997548411928643
- **Call lean:** fresh-dominant.
- **Red flags:**
  - Admits pushing tokens as an "influencer": https://x.com/Numerooo0/status/2111463321333322190 and https://x.com/Numerooo0/status/2113382282434343121
  - Kolscan lists a TG channel, t.me/fakepumpsbynumer0.
  - Brags about Fomo app leaderboard ranks.
- **Confidence:** low.

### 4. zhynx: @onlyzhynx, https://x.com/onlyzhynx
- **Followers / created:** 5,707 / 2022-08-16
- **Wallet (tracker-attributed, kolscan):** `zhYnXqK3MNSmwS3yxSvPmY5kUa1n2WUaCJgYUDrAHkL`, https://kolscan.io/account/zhYnXqK3MNSmwS3yxSvPmY5kUa1n2WUaCJgYUDrAHkL
- **Kolscan PnL:** 30d +1265.3 SOL (14W/23L)
- **On-chain lean (159h window):** 42 opens with known age. 2 (5%) were older than 1h, e.g. OPENAI (~$2.6M now). 1 opened token now has mcap ≥$1M.
- **Why notable:** bio says "researcher". Writes thesis-style posts and long articles on AI-infra coins after launch, which is the closest to a "conviction/research" style here.
  - https://x.com/onlyzhynx/status/2076795322555109616 (article on a low-cap coin)
  - https://x.com/onlyzhynx/status/2074348562712817997 ($ZERO/c0mpute thesis)
  - https://x.com/onlyzhynx/status/2099506035425751366 ("sometimes being patient pays")
- **Call lean:** X content leans research or hold. On-chain is fresh-dominant.
- **Red flags:**
  - Earns pump.fun app "callout" rewards and promotes following him there ("0% fees"), which works like an affiliate: https://x.com/onlyzhynx/status/2089812067838472394
  - TG zhynxjournal.
- **Confidence:** low-medium.

### 5. Matt: @MattFws, https://x.com/MattFws
- **Followers / created:** 3,884 / 2017-01-03
- **Wallet (tracker-attributed, kolscan):** `3bzaJd5yZG73EVDz8xosQb7gfZm2LN5auFGh6wnP1n1f`, https://kolscan.io/account/3bzaJd5yZG73EVDz8xosQb7gfZm2LN5auFGh6wnP1n1f
- **Kolscan PnL:** 30d +732.7 SOL (21W/76L)
- **On-chain lean (57h window):** 60 opens with known age. 8 (13%) were older than 1h and 7 older than 24h, the highest share in the set. Most are PUMP, WBTC, MCDx or DJT rather than memecoin calls. 3 opened tokens now have mcap ≥$1M.
- **Why notable:** the highest older-token share on-chain. Few actual calls on X.
  - https://x.com/MattFws/status/2095529259515453796 (says he'll trade solely on the pump.fun app and share his thought process)
- **Call lean:** mixed, with few calls.
- **Red flags:** a steady stream of pump.fun app promotion, possibly sponsored (https://x.com/MattFws/status/2111907686325579834). Poor W/L ratio.
- **Confidence:** low.

### 6. zeropnl: @im0pnl, https://x.com/im0pnl
- **Followers / created:** 3,610 / 2024-10-19
- **Wallet (tracker-attributed, kolscan):** `4xY9T1Q7foJzJsJ6YZDSsfp9zkzeZsXnxd45SixduMmr`, https://kolscan.io/account/4xY9T1Q7foJzJsJ6YZDSsfp9zkzeZsXnxd45SixduMmr
- **Kolscan PnL:** 30d +2693.8 SOL (540W/216L)
- **On-chain lean (5.6h window):** 38 opens with known age. 6 (16%) were older than 1h, including Fartcoin (~$136M) and ZEC (~$120M). 2 opened tokens now have mcap ≥$1M.
- **Why notable:** strong kolscan PnL and some large-cap entries. Posts on-chain forensics (https://x.com/im0pnl/status/2112696764364902503).
- **Call lean:** fresh-dominant, high frequency.
- **Red flags:**
  - Self-described "serial deployer" (token creator): https://x.com/im0pnl/status/2109842103023128855. Scout should check for deployer or bundler overlap.
  - Abusive posting.
  - Bio has only a link.
- **Confidence:** low.

## Checked and excluded
- **Referral, promo or creator flags, and also fresh-dominant:**
  - @Chairman_DN pushes his referral code "chairman": https://x.com/Chairman_DN/status/2113463795985400064
  - @slingoorio has a referral code and shills his own coins: https://x.com/slingoorio/status/2113692095084966128
  - @0GAntD posted a TradingTerminal referral link: https://x.com/0GAntD/status/2111909527205400950
  - @narracanz is the self-described creator of $alon/$babyalon.
  - @imsheepsol, @notdecu and @jijo_exe have terminal or referral links in their bios.
  - @Dior100x has "Business & collaborations → DM" in his bio.
- **Fresh-only on-chain:** @xWugi_wara (0/26 older), @VERYKOOLLUKEY (0/14), @m4rk3r (1/43), @CookDoc1993 (2/60), @pavlotrading (3/31).
- **Too few txs over public RPC to classify:** @kadenox, @theonomix, @notdecu, @jijo_exe.
- **Suspended or not found on X** although listed by kolscan: TheMisterFrog, idrawline, casino616, fox09_09 (suspended), and clukzSOL, samsrepx, 973Meech, Reljoooo (not found).
- **Context:** X users note that the kolscan boards are often "one good trade" and that KOLs sell into their own calls. Treat kolscan PnL with caution.

Raw data: /workspace/x-pulse/copyleads/ (raw_*.txt, users1.json, lean2_out.json).
