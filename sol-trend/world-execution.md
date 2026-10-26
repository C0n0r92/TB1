# World (world.xyz) execution research: SOL Up-or-Down (Track C)
Research only, written 2026-10-23. No wallet was created, connected or used for signing. No sign-ins, orders or API keys. Everything below is a description, not something that was built.
Sources: World support articles and terms, taken from world.xyz JS bundles (saved in track-c/data/web, extracted to track-c/data/support_articles.md); Phantom Help; DFlow docs; Chainstack's world-xyz-research write-up (third-party, track-c/data/reference.md).

## 0. Bottom line (read first)
- **Do not proceed. Ireland is on World's restricted-country list** (https://world.xyz/support/which-countries-can-use-world), and World's ToS (17 Jun 2026) say there are "NO EXCEPTIONS" and that using a VPN to get around this is prohibited. GRAI says unlicensed prediction markets must block Irish consumers. The design below is only useful if the user is legally in a supported jurisdiction. It must not be used from Ireland or behind a VPN.
- **There is no edge either.** The best paper strategy loses money after costs out of sample (see track-c/reports/first-read.md).

## 1. Can a bet be placed other than through the app?
| Route | Status |
|---|---|
| Phantom app | Mobile only, market orders, whole contracts. Phantom Help says: "Phantom does not offer a public API for this feature". This route is app only. |
| World web app (world.xyz) | Connect a Solana wallet, and the UI requests a quote. The web app's own backend (`markets-api-proxy.world-xyz.workers.dev/api/v1`, `aggregator-api-proxy…`) needs a Cloudflare Turnstile JWT (`POST /auth/token`). It returns **401** without one, so it is not a public API. |
| World API (api.world.xyz) | Returns **403**. docs.world.xyz redirects to login. Access needs an application at https://world.xyz/docs/request-access. |
| DFlow Trade API | The web app routes buys and sells through DFlow: `GET /order?inputMint=CASH&outputMint=<YES/NO mint>&amount&userPublicKey&slippageBps` returns a base64 transaction to sign, and `GET /order-status` reports open, closed, failed or pendingClose. Production `quote-api.dflow.net` needs an `x-api-key`. `dev-quote-api` is keyless but rate-limited and not for production. The DFlow docs mention Proof KYC for Kalshi markets. |
| On-chain keypair | Program `prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM`. Outcome tokens are Token-2022 YES/NO mints. Chainstack notes that split/merge (CASH to YES+NO and back) can be called directly, but directional fills come from RFQ market makers (JanusFI, which is World's own, and BisonFI) through DFlow. A bot would therefore be a keypair plus DFlow quote, sign and send. |
| **PayBox MCP (World's official agent route)** | World support: "PayBox gives your AI agent access to World markets… place orders when you tell it to, without ever handing over your keys… it cannot spend beyond the limits you set when you connect." Connector URL from the bundle: `https://api.paybox.sh/mcp?app=world`, for Claude, ChatGPT or Grok. **Not connected or tested**, since it needs a wallet connection. This is the sanctioned automation path for an eligible user, with spending limits built in. |

## 2. What a bet requires
- **Currency:** CASH (`CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH`), a Bridge/Stripe Token-2022 stablecoin with a permanent delegate (the issuer can move or freeze it). Deposits in other tokens are converted to CASH.
- **Size:** World says there is "No [minimum]. You can trade any amount", though tiny orders cost more in fees than they are worth. No published maximum; in practice the limit is the depth of the RFQ quote. Phantom requires whole contracts.
- **Fees:** World Foundation charges no protocol fee. World adds a network fee on each buy and sell, plus a refundable rent deposit on the first buy in a market. Interface fees vary: Phantom charges ≈ 0.1·p·(1−p) per contract, about 2.5c at p=0.5, and Chainstack observed web-app interface fees of about 800·(1−p) bps. One decoded trade had a 2.16% overround. From the screenshot payouts (3.8x at 26%, 1.4x at 74%), the all-in cost is about 1–3c per contract. My model uses mid + 1c half-spread + the Phantom fee, giving a 53.5% break-even at p=0.50.
- **Slippage:** Auto, 0.3%, 0.5% or custom. "If the price moves further than that… the order does not go through at all". Fills behave like limit IOC orders.
- **Quote expiry and latency:** These are RFQ quotes, so the transaction must land before the quote expires (a few seconds on Solana). DFlow /order-status can return `pendingClose`. Expect 1–3s from quote to confirmation, longer under congestion.
- **Settlement:** Some crypto markets settle on a **Chainlink TWAP** ("World settles on a Chainlink TWAP feed, so it's…" not the last Binance tick). The operator key `DDucv2DeUsTsg1rfAcWAnUSUVpqfdHEzxX66ARB2JYVg` calls `determine_outcome` and then `redeem_outcome_for_user`. Payment usually arrives within about 1 minute.

## 3. Geo, KYC, bot terms, Ireland
- World: "World does not require KYC, but trading is not permitted from certain restricted jurisdictions". The list has 64 countries, **including Ireland**. Blocking is enforced in the UI by IP and wallet screening. ToS: "THERE ARE NO EXCEPTIONS" and VPNs are prohibited. The ToS bind users "whether directly or through any Interface", which covers Phantom, DFlow and PayBox.
- Phantom's region page doesn't name Ireland ("Not available in the US, UK, Germany…"). That silence is not permission, because the underlying venue (World) restricts Ireland.
- Bots: World explicitly supports AI agents through PayBox. No anti-bot clause was found beyond the restricted-person and circumvention clauses.
- **Ireland: RESTRICTED.** Quotes and links are in track-c/reports/compliance-and-costs.md.

## 4. Monitoring and a read-only Guard
This is feasible with only public Solana RPC and no keys:
- `getSignaturesForAddress(wallet)` and `getTransaction` to detect every buy and sell (DFlow program `DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH`, prediCt program).
- `getTokenAccountsByOwner(wallet, Token-2022)` to read open YES/NO positions and the CASH balance.
- Watching `redeem_outcome_for_user` and `determine_outcome` from the operator key to confirm settlement and payout.
- Market metadata (series ticker, close time and target) needs World's gated API. A Guard would use the user's own World or PayBox read access, or on-chain mint metadata only.
The Guard can alert and can recommend that the bot stops. It cannot sign anything and holds no keys.

## 5. Recommended safe setup (described only; nothing created)
Only for an eligible user in a supported jurisdiction, and only if a positive edge appears in forward paper trading:
1. A **dedicated hot wallet** holding only the risk budget (e.g. ≤ €50 of CASH). It is never the main wallet and is never reused.
2. Prefer **PayBox** with its connect-time spending limits over a raw keypair. If a keypair is used, keep it in an OS keychain or HSM, never in code or the repo.
3. **Hard caps in code** (section 6) plus a **kill switch** (a file flag or env var that is checked every loop, and a Guard alert that triggers it).
4. Run the read-only Guard as a separate process that tracks P&L and alerts.
5. Run forward paper trading for at least 4 weeks on real quotes before any live money.

## 6. Early cash-out (sell before close)
- **Allowed:** yes. "You can sell at any time, at whatever the market is paying then". But "Selling before resolution needs someone to take the other side. In thin or very lopsided markets… you might not be able to exit at the price you want, or at all." Phantom says cash-out is available only when liquidity exists.
- **Bid, spread and fee:** the bid is an RFQ quote from JanusFI or BisonFI, and no public data exists for it. The sell carries a network fee plus the interface fee (Phantom ≈ 0.1·p·(1−p)), and the rent deposit is returned only at market end. Modelled as fair − 1–2c minus the fee.
- **Paper result:** none of the exit rules beat holding after costs. Lock-in at 85–90% is worse than holding, and the stop rule is roughly equal to holding (see first-read.md).

## 7. Continuous-loop spec (spec only; no signing or order code)
```
every 3-5 s:
  if KILL_SWITCH file exists or guard_alert: cancel nothing (IOC), stop new entries, log, exit
  feeds: spot (Chainlink Data Streams / Pyth for SOL, cross-checked against a CEX), the TWAP-so-far for the active window,
         vol (60m rolling 1m stdev), 15m and 1h bars for trend, ADX, S/R and volume, World quote (bid/ask/depth) via PayBox or the approved API
  for each active SOL window (15m main, 1h, 5m baseline):
     t_left = close - now; fair = Phi(ln(twap_proj/target)/(sigma*sqrt(t_left)))
     entry allowed only at the scheduled checkpoints (open, +2m, +5m) AND all filters agree AND edge = fair - ask - fee >= MIN_EDGE
     exit: re-check position each loop; sell only if bid - fee > fair + EXIT_MARGIN (rule a), else hold to settlement
  decision timing: never act with < 30 s left (TWAP mostly fixed, makers hold the faster feed); stale-data guard: skip if any feed is > 2 s old
hard caps (constants in code, not config):
  MAX_STAKE_PER_BET = €5   MAX_BETS_PER_WINDOW = 1   MAX_OPEN_WINDOWS = 2
  MAX_DAILY_LOSS = €15 -> trips kill switch   MAX_TOTAL_EXPOSURE = €20
  MAX_PRICE = 0.80 (never buy above)   MIN_EDGE = 0.03 after fees   MAX_SLIPPAGE = 0.5 %
  MAX_ORDERS_PER_HOUR = 6   consecutive-loss stop = 6
monitoring hooks (read-only): an append-only JSONL of every decision (inputs, fair, quote, edge, action), a Guard reconciliation
  of on-chain fills against the decision log every minute, alerts on cap breaches, failed or pendingClose status, or a quote/fill mismatch
```
