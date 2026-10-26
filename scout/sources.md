# Scout lead sources (free, scripted HTTP only; all leads are untrusted until verified on-chain)

| date (UTC) | site | URL tried | result | used? |
|---|---|---|---|---|
| 2026-10-24 10:31 | Kolscan | https://kolscan.io/leaderboard (also ?timeframe=7, ?timeframe=30) | 200; server-rendered HTML has only the daily (timeframe=1) board, 26 KOL wallets with name, W/L and SOL PnL. The ?timeframe param returned the same daily board | yes: 26 leads (daily board only) |
| 2026-10-24 10:31 | Kolscan API | https://kolscan.io/api/leaderboard?timeframe=7 | 400 "Forbidden" | no (blocked; not worked around) |
| 2026-10-24 10:31 | GMGN.ai API | https://gmgn.ai/defi/quotation/v1/rank/sol/wallets/7d?orderby=pnl_7d&direction=desc | 403 Cloudflare "Just a moment..." | no (blocked) |
| 2026-10-24 10:31 | GMGN.ai page | https://gmgn.ai/trade?chain=sol&tab=smart | 200 but client-rendered; no wallet data in the HTML (needs a browser) | no |
| 2026-10-24 10:31 | DexScreener | https://dexscreener.com/solana (top-traders tab is on pair pages) | 403 Cloudflare challenge | no (blocked) |
| 2026-10-24 10:31 | Birdeye | https://public-api.birdeye.so/defi/v2/tokens/top_traders | 401 Unauthorized (needs an API key, i.e. a sign-up) | no |
| 2026-10-24 10:31 | Cielo | https://app.cielo.finance/ ; https://feed-api.cielo.finance/api/v1/leaderboard | 429 on the app; 404 on the guessed API path; the leaderboard/feed needs an account | no |
| 2026-10-24 11:19 | Kolscan weekly | https://kolscan.io/leaderboard (re-checked) | 200; the "Weekly" tab exists but its data loads client-side from the API that returned 400 "Forbidden" earlier; server HTML has only timeframe=1 | no (weekly blocked; not worked around) |
| 2026-10-24 11:19 | GeckoTerminal API | /networks/solana/pools (h24 volume / tx count / trending 24h+6h), then /pools/{addr}/trades (>$150) | 200 (free, no key). 67 pools with mcap $300k-$1B, liq >=$100k, age >=1d; 768 non-flip candidate wallets after filters | yes |
| Solscan account page (curl, SSR) | 2026-10-24 12:2x | OK: label shows in <title>/meta (e.g. 'Binance 2'); used for the label check |
| 2026-10-24 20:0x | Helius getTransactionsForAddress (gTFA) | RPC method with filters status=succeeded, blockTime>=cut, tokenTransfer={} | works on bot-flooded addresses (keeps only txs where the wallet moved tokens); 10 credits per 1000 sigs (signatures mode) or per 100 txs (full) | yes: Cented, decu, Schoen + 11 flooded Kolscan wallets, 7d histories for Latuche/S/bust |
| 2026-10-24 | Helius enhanced parsed history | /v0/addresses/{w}/transactions | unusable on flooded addresses (~28s of chain per 100-credit call) | no |
| 2026-10-24 | Helius JSON-RPC batch | batch getTransaction | frequent 429 | partly |
| 2026-10-24 | publicnode | https://solana-rpc.publicnode.com | 403 without a User-Agent header; OK with UA; ~35h history | yes |
| 2026-10-24 | Kolscan account pages | https://kolscan.io/account/<w> | client-rendered; no data in HTML | no |
| 2026-10-24 20:15 | GeckoTerminal API (re-mine) | trending_pools 24h/6h/1h, pools by h24 volume/tx count, new_pools, then /pools/{addr}/trades?trade_volume_in_usd_greater_than=100 | 200, free | yes: 119 wallets after bot filters, 6 fetched |
| 2026-10-24 | GMGN / DexScreener web / Birdeye / Cielo | (see above) | blocked / key / account | not used, not worked around |
| 2026-10-24 21:42 | GeckoTerminal top_traders | https://api.geckoterminal.com/api/v2/networks/solana/tokens/<mint>/top_traders | 401 Unauthorized (needs CoinGecko Pro key) | no (blocked; not worked around) |
| 2026-10-24 21:44 | Kolscan leaderboard (refresh) | https://kolscan.io/leaderboard | 200; SSR now includes timeframes 1/7/30 (143 rows) + 548-wallet KOL directory; only 9 new daily/weekly names, none with >=10 trades | yes |
| 2026-10-24 21:55 | GeckoTerminal trades | https://api.geckoterminal.com/api/v2/networks/solana/pools/<pool>/trades?trade_volume_in_usd_greater_than=100 | 200 for 29 of 30 pools; 1 x 429 (rate limit) | yes: 224 wallets in 2+ established pools, 44 moderate-activity after triage |

## 2026-10-24 22:29Z – GeckoTerminal mining v2 (bg/gtmine2.py)
- GT trending pools (24h p1-3, 6h, 1h) + pools by h24 volume (p1-4) and tx count (p1-2); kept pools age>=24h, mcap>=$1M, fdv<=$5B; $100+ trades of the first 45 pools -> gt/mine2_2229.json (80 pools, 858 wallets) -> gt/dir_2235.json (120 cands) -> triage_2235.json (118 active, 79 moderate). Worked, no blocks.
## 2026-10-24 22:35Z – Kolscan leaderboard refresh
- kolscan.io/leaderboard HTML 200 OK (bg/kolscan_lb_2235.html, parsed to kolscan_2235.json, 148 rows). Only new profitable name with >=10 trades not yet analysed: Kadenox (B32Qbb…, 1d +34.3 SOL, 13W/8L). Lynk (+1.7 1d) previously seen as bot-flooded.
## 2026-10-24 22:40Z – open-position valuation
- public RPC getTokenAccountsByOwner + DexScreener tokens/v1 priceUsd (bg/openpos.py). Worked.
