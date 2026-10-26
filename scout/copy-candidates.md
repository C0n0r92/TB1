# Copy candidates: Pulse/X leads verified on-chain
Generated 2026-10-24 ~00:50 UTC by scout. This is read-only analysis, not trading advice. Source leads: /workspace/x-intel/copy-leads.md (6 leads, treated as untrusted). Only wallets listed in that file were checked.

**Method.**
- **Swap history:** Helius getTransactionsForAddress, 25 pages per wallet. This covers the last 14–26 days, not the full 30.
- **Round trips:** a trade closes when ≥95% of the position is sold.
- **Costs:** PnL is after on-chain fees. "net3/net5" subtract 3 or 5 percentage points per round trip. "avg net5" is the expectancy of an equal-size copy.
- **Frequency:** two measures.
  - Closed round trips: trades/hour and trades/night, where night = 21:00–08:00 Europe/Dublin.
  - All signatures over 30 days (public RPC): sigs/h and the share of night hours with at least 1 signature. Signatures include spam/airdrops, so they overstate activity.
- **Creator/bundle checks:**
  - pump.fun `coins?creator=` lookup.
  - rugcheck creator compared with the wallet for every traded mint.
  - First funder (first_txs) compared with avoid.csv, known_funders.csv, known_ruggers.json and data/funding.json.
  - Create-slot check on every entry with GT pool age <30 s: does the entry tx contain the create instruction, and how many slots after the mint's first tx did it land?
  - Shared funding with creators can only be checked for creators that have a known funder (9 of 111 creators). That check is partial.

## PASS
| wallet | label | confidence | reason |
|---|---|---|---|
| 5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG | neodot | medium | 40 closed in ~23 d. Win 60%. Median +10.8% / avg +42% after 5% (net3 sum +34.9 SOL, net5 +33.8 SOL). Max drawdown only −2.7 SOL. Median hold 15.6 min (25% of winners held <2 min). Size ~1 SOL, fresh_launch (median entry age 0.43 h, mcap ~$6.6k, 82% pump.fun entries). 0 self-created coins (pump.fun + rugcheck on 37 mints). No entries in a create slot. Not in avoid, funders or ruggers. **Caveats:** closed-trade frequency is low (0.07 trades/h, 1.2/night). Signature activity is 3.6/h with 82% of night hours active, but that includes spam, so idle hours of 1h+ are likely. Funder Dv34prGm… (5.0 SOL) also funded 3ntjjwpq…, an early buyer of SPIKE; that link is weak. Micro-cap entries are hard to copy at size. |

## FAIL / not recommended
| wallet | label | verdict | key numbers / reason |
|---|---|---|---|
| zhYnXqK3MNSmwS3yxSvPmY5kUa1n2WUaCJgYUDrAHkL | onlyzhynx | not a copy candidate (kept in winners/ as a low-confidence sample) | 31 closed in 25.6 d. Win 35%. Median −46.5% / avg +21% after 5%; sum +81 SOL comes from outliers; max drawdown −120.6 SOL. Hold 21 min (45% of winners <2 min). Low frequency: 0.05 trades/h, 0.43/night. Created 10 pump.fun coins in Mar–Apr 2026 (outside the window, none traded in it). Earliest entry (PACT) came 36 slots / ~14 s after the mint's first tx, not in the create tx. |
| A3W8psibkTUvjxs4LRscbnjux6TFDXdvD4m4GsGpQ2KJ | Numerooo0 | FAIL | 117 closed in 14.2 d. Win 52%. Median +4.6% / avg +58% after 5%, +308 SOL. But median hold is exactly 2.0 min and 62% of winners were held <2 min, so the hold rule fails and it is too fast to copy. Promo red flags: TG "fakepumpsbynumer0" and pushing influencer tokens. 0 self-created coins of 107 mints. Frequency: 5.15 trades/night. |
| 3bzaJd5yZG73EVDz8xosQb7gfZm2LN5auFGh6wnP1n1f | MattFws | FAIL | 66 closed in 21.8 d. Win 24%. Median −52.7% / avg −17.7% after 5%, so equal-size copy expectancy is negative. The +592 SOL sum comes from a few large outliers. Max drawdown −478 SOL. |
| SAALE2x3sn51EyahJyqD6913L3GqHZdZo3egUdMayQp | saale | FAIL | 49 closed in 23 d. Win 20%. Median −32.5% / avg −21.1% after 5%. Sum −9.7 SOL after 5% (+7.6 after 3%). Max drawdown −144.8 SOL. Settles through a relayer (counterparty 6M7Mq1Mh…), which makes it hard to copy. |
| 4xY9T1Q7foJzJsJ6YZDSsfp9zkzeZsXnxd45SixduMmr | im0pnl | FAIL | Serial deployer: created 50 pump.fun coins since Oct 21 (micro-caps ~$2.8k). 12 sigs/h. PnL not computed because it fails the dev rule. |

Raw data: /workspace/scout/data/stats_wg.json, data/wg/*.json, data/activity.json, data/rc_creators.json. Per-trade rows for the PASS wallet and onlyzhynx: /workspace/onchain-intel/winners/trades.csv.
