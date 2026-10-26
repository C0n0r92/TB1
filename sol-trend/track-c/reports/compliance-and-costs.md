# Track C — World / Phantom Predictions: compliance and costs
Fetched 2026-10-23 (UTC) by Oracle's Track C worker. Public pages only; no wallet, no sign-in.

## VERDICT: Ireland is RESTRICTED. Stop Track C as a live/real-money idea.
World's own support centre lists Ireland as a restricted country. Phantom's region page doesn't name Ireland but says the feature "varies by region". Phantom's World markets run on World, so World's restriction applies. On top of that, Ireland's gambling regulator (GRAI) says unlicensed prediction markets must block Irish users.

### Exact quotes
1. **World Support, "Which countries can use World?"** (https://world.xyz/support/which-countries-can-use-world). The page is a JS app, so the text was taken from its bundle `https://world.xyz/assets/SupportSearchBar-BPpKbhIq.js`, saved at `data/support_articles.md`:
   > "World does not require KYC, but trading is not permitted from certain restricted jurisdictions. World prediction markets are not available in the following countries and territories: … Hungary · India · Iran · Iraq · **Ireland** · Italy · Japan …"
   > "Access is also blocked anywhere under comprehensive U.S. sanctions or where using the Services would break local law, and this list can change over time."
   The list has 64 countries, including the UK, US, France, Germany, Italy, the Netherlands, Belgium, Poland, Portugal and Malta.
2. **World Terms of Service** (https://world.xyz/terms, "Last Updated: June 17, 2026", from the World Protocol Foundation, Cayman):
   > "…NOT AVAILABLE TO, ANY PERSONS OR ENTITIES WHO RESIDE IN, ARE CITIZENS OF, ARE LOCATED IN … ANY JURISDICTION WHERE SUCH SERVICES ARE INELIGIBLE FOR USE … THERE ARE NO EXCEPTIONS."
   > "USE OF ANY TECHNOLOGY OR MECHANISM, SUCH AS A VIRTUAL PRIVATE NETWORK OR OTHER IDENTITY MASKING TECHNOLOGY, TO CIRCUMVENT THE RESTRICTIONS SET FORTH HEREIN IS PROHIBITED."
   > Restricted Person includes anyone in a "(B) jurisdiction where the Services, any Market, Outcome Token … Interface … are ineligible for use under applic[able law]".
   The terms say they bind users "whether directly or through any Interface", and Phantom is such an Interface.
3. **Phantom, Feature availability by region** (https://help.phantom.com/articles/feature-availability-by-region-48634486197651):
   > "Prediction markets | Available in some jurisdictions. Not available in the US, UK, Germany, and jurisdictions sanctioned by the US."
   Ireland is not named here, which is where the "user can use it from Ireland" belief probably came from. The app may currently let an Irish user in, but that does not make it allowed under World's terms.
4. **Phantom, Prediction Markets Disclosures** (https://phantom.com/prediction-market-disclosures, dated Jul 1 2026):
   > "If you opened your position on or after June 1, 2026: Prediction markets on Phantom are powered by World Prediction Markets ("World")."
   > "Prediction Markets on Phantom are only available to users in certain jurisdictions. Users participate at their own risk and are responsible for ensuring their participation complies with applicable laws in their jurisdiction."
5. **Phantom Help, Trade World prediction markets** (https://help.phantom.com/articles/trade-world-prediction-markets-in-phantom-47187740851731):
   > "Outside the United States, prediction markets in Phantom are powered by World Prediction Markets on Solana." "Prediction markets are available only to eligible users in supported jurisdictions."

### Irish gambling-regulation angle (GRAI)
- GRAI licensing page (https://www.grai.ie/licensing-regulation/business-to-consumer-licenses):
  > "The GRAI is of the view that prediction markets that provide betting activities fall within the definition of remote betting intermediary under Irish law… Prediction market operators that require a betting licence but do not hold one should take appropriate steps to prevent access to their platforms by consumers in Ireland."
- GRAI, 1 Jul 2026 (https://www.grai.ie/news/commencement-of-gambling-regulatory-authority-of-ireland-remote-betting-licences): remote betting and betting-intermediary licences began 1 July 2026.
- Irish Examiner (https://www.irishexaminer.com/news/courtandcrime/arid-41883400.html) and SiGMA (https://sigma.world/news/ireland-restricts-prediction-markets-eu-scrutiny/) report that Polymarket geoblocked Ireland after GRAI intervention.
- Phantom's line "Phantom does not offer gambling… skill-based forecasting" is Phantom's own label. GRAI looks at what the activity is, not what it is called. A 5-minute SOL Up/Down market is very close to a fixed-odds bet. I found no GRAI licence for World or Phantom (not exhaustively checked).

**Conclusion:** restricted under World's terms, and there's a GRAI risk on top. A VPN or any other workaround is ruled out, and the terms prohibit it explicitly.

## Fees and spread
| Layer | What | Source |
|---|---|---|
| World protocol | "The Foundation does not currently charge fees for the Services" (reserves the right to add them). The user still pays gas, Interface fees, "AMM price impact and spread", and oracle fees. | world.xyz/terms §Responsibility for Fees |
| Phantom prediction fee | `fee = 0.1 * p * (1-p) * C` (p = contract price, C = number of contracts). Example: 100 contracts at $0.75 cost $1.875. Highest at p=0.5 ($0.025 per contract, 5% of stake); about 0.2% of stake at p=0.98. Charged on buys and on cash-outs ("Review the sale amount and fees"). | Phantom Help article above |
| Network | Trades from the Cash account are gasless. Trades paid with portfolio tokens need SOL. The first buy in a market pays a refundable rent deposit. | Phantom Help; World support "What am I charged?" |
| World web app (world.xyz) | Per-fill platform fee set by whoever builds the transaction (DFlow `platform_fee_ubps`). An observed open-endpoint quote followed `feeBps ≈ 800×(1−p)`, about 7.9% on a long shot and about 0.03% near certainty. World's referral page says referrers earn "a share of the fees your referred traders pay". | Chainstack research repo (third-party, verified 2026-09-11): github.com/chainstacklabs/world-xyz-research/blob/main/docs/reference.md |
| Spread | There is no order book. A market maker (JanusFI, which is World's own MM, or BisonFI) quotes through the DFlow RFQ router. One decoded trade had YES 0.2484 + NO 0.7732 = 1.0216, a 2.16% overround. Payouts are fixed at 1 CASH per winning token. | same |
| Order types (Phantom) | Market orders only, whole contracts only, mobile app only. Slippage on world.xyz is "Auto" or 0.3% / 0.5% / custom. An order that moves beyond tolerance does not fill. | Phantom Help; World support "What is slippage" |

**Effective cost per bet (inferred).** In the user's screenshots, 26% paying 3.8x implies a cost of 1/3.8 = 0.263, only about 0.3c over mid. 74% paying 1.4x implies 0.714, which is *below* 0.74. Neither fits the Phantom formula (that would give 3.58x and 1.32x). So the displayed "x" multiplier most likely leaves out the prediction fee, and it is rounded. Conservative model used in the tests: **mid + 1–2c half-spread + 0.1·p(1−p)**. At p=0.5 that means you must win more than 53.5% just to break even.

## Early cash-out
- Phantom: "You can sell an open position before the market resolves if liquidity is available… The amount you receive depends on the prices and available buyers." There is a fee on the sale. "Cashing out requires a buyer… you may be unable to sell… even when your position shows a profit." It says "Quote unavailable" when there is no buyer.
- World: "You can sell at any time, at whatever the market is paying then." "In thin or very lopsided markets there may be little demand… you might not be able to exit at the price you want, or at all. You can always hold a position to resolution."
- Bid, spread and depth for a sale come from an RFQ quote, not a visible book. No public data on cash-out bids is available (see the API section). Assume a sale costs the half-spread plus the Phantom fee at the sale price.

## Public read API: NOT publicly readable (as of 2026-10-23)
| Endpoint | Result |
|---|---|
| `https://api.world.xyz/*` | **403** with an empty body on every path tried |
| `https://docs.world.xyz/` and `/llms.txt` | **302 to `/login`**, so the developer docs require a login |
| `https://world.xyz/docs/request-access` | "Request API Access — Reach out and tell us about your project." |
| `https://markets-api-proxy.world-xyz.workers.dev/api/v1/{markets,events,series}` | **401 `{"error":"Unauthorized"}`**. This was open until about Sept 2026 (Chainstack). The web app now sends `Authorization: Bearer <JWT>`, which it gets from `aggregator-api-proxy…/auth/token` after passing a **Cloudflare Turnstile** bot check (seen in `assets/client-C0Ryceh1.js`). I did not try to obtain or automate a Turnstile token, because that would mean getting around bot protection. |
| `wss://markets-api-proxy…/api/v1/ws` | HTTP 403 |
| `aggregator-api-proxy…/order` | 404 without parameters. It builds a transaction for a user key, so it is not a read API and I did not probe it further. |
| `users-api.world.xyz/api/v1` | 404 |
| Solana public RPC (`api.mainnet-beta.solana.com`) | **Works.** World program `prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM` is readable (executable, owner BPFLoaderUpgradeable), and `getSignaturesForAddress` returns live finalized transactions. On-chain data shows trades and resolutions, but not quotes or the "price to beat" in a usable form without per-transaction decoding. |
| Binance spot (`api.binance.com`) | 451 (geo-blocked from the box). `data.binance.vision` bulk 1m files return 200 and were used. |

The endpoints the press reported (markets, series, trades, candlesticks, price history, order books, quotes) are presumably behind the access-request or login wall. None of them are readable without authentication.

### Addendum (2026-10-23): World's official agent route
World support says AI agents (Claude, ChatGPT, Grok) can trade through **PayBox**. The MCP connector URL in the world.xyz bundle is `https://api.paybox.sh/mcp?app=world`. It "signs orders through your wallet" and "cannot spend beyond the limits you set when you connect". It was not connected or tested, because that needs a wallet. The Ireland restriction applies to it too.
