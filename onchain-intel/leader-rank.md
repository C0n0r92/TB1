# Copyfomo leader re-rank (2026-10-23T22:32:42Z), recommendations only

Window: last 30 d of Solana swaps (Helius enhanced SWAP history). The copy filter is the first round per mint with entry mcap ≥ $100,000. Each copy is simulated at $50. Ranked by: not cut, then share of positive weeks, then win rate, then smaller worst drawdown. Peak PnL is not used.
Leaderboard file: /workspace/copyfomo/leaderboard-2026-10-23.md; handles matched to wallets: Altcoinist, BtheBezel, ExactTallTakin, _benjitrades, bystevenr, cosby, pointfarmcap, zelda89.
Leaderboard handles with **no wallet found** (not guessed): 000000, DONBAGS, 0xstanczyk, heat, JamJam0407, end837, 0xBEC001, Hifive_07, DonnyDicey, JohnnyBones, 0xbr9, UsedMerePike, vvvvvvvvvv, scrollingbeauty, escobarpablo, memeking888, earn168, kv4rl, RareDualJay, BTCdayu, gtsb, PromUnchained, smoothietrades, RunningClam, orangie, pricedin.
Caveats: wallet↔handle mappings are not independently verified (see provenance); EVM (Base/BSC) trades not covered; open rounds marked at DexScreener price now; mcap_at_fill = fill price × supply (pump.fun = 1B).

| # | trader | mapping conf. | wallet | copyable trades (closed) | win rate | positive weeks | weekly $ (sd) | worst DD $ | copy PnL $ | median entry mcap | median entry age h | dumped <$10k | rugcheck block/caution | <60s entries / flips | acct age d | cut |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | _benjitrades (current) | low | `9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc` | 31 (24) | 0.29 | 2/5 | {'2026-W39': 47.6, '2026-W40': -44.21, '2026-W41': 119.71, '2026-W42': -81.27, '2026-W43': -31.02} (sd 72.24) | 186.8 | 10.81 | 572486 | 3.0 | 0.42 | 7/9 | 0 / 1 of 32 | 50 | - |
| 2 | ExactTallTakin (current) | medium | `AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v` | 50 (41) | 0.54 | 1/5 | {'2026-W39': 1325.59, '2026-W40': -65.31, '2026-W41': -101.5, '2026-W42': -113.25, '2026-W43': -130.54} (sd 571.7) | 465.07 | 914.99 | 349801 | 0.5 | 0.6 | 6/9 | 12 / 72 of 116 | 35 | insider-like: 12 entries <60 s after pair creation; fast flips: 72/116 closed rounds held <60 s (copiers can't match) |
| 3 | zelda89 | low | `FG4c1qnq8vEc9nn6uxmtWVjWZLE9rxTfeExBYh5GQnRb` | 1 (1) | 1.0 | 1/1 | {'2026-W40': 63.59} (sd None) | 0 | 63.59 | 369156 | 63.2 | 0.0 | 0/0 | 0 / 0 of 1 | 38 | only 1 copyable trades (<30) |
| 4 | bystevenr | low | `AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx` | 25 (14) | 0.43 | 2/3 | {'2026-W41': 218.11, '2026-W42': 2436.08, '2026-W43': -131.11} (sd 1136.85) | 211.61 | 2523.08 | 249629 | 18.2 | 0.28 | 4/8 | 7 / 1 of 38 | 76 | only 25 copyable trades (<30); insider-like: 7 entries <60 s after pair creation |
| 5 | pointfarmcap | medium-low | `Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit` | 13 (6) | 0.33 | 1/2 | {'2026-W42': -46.95, '2026-W43': 8.29} (sd 27.62) | 59.25 | -38.65 | 1093593 | 235.2 | 0.15 | 1/1 | 1 / 0 of 7 | 358 | only 13 copyable trades (<30) |
| 6 | BtheBezel | low | `HWYpE693cw8AWxHSynrHhUsKDbfzubAFYWpTcMZdNWKR` | 25 (19) | 0.16 | 1/4 | {'2026-W39': -27.69, '2026-W40': -109.96, '2026-W41': -227.23, '2026-W42': 140.65} (sd 133.89) | 409.04 | -224.23 | 265081 | 1.1 | 0.56 | 4/6 | 8 / 16 of 76 | 163 | only 25 copyable trades (<30); insider-like: 8 entries <60 s after pair creation |
| 7 | Altcoinist | low | `DVFYHVKFYLxws4bV97va6EceVRrKjddHSWYq3is4ad49` | 0 (0) | None | 0/0 | {} (sd None) | 0 | 0 | None | None | None | 0/0 | 0 / 0 of 0 | 99 | only 0 copyable trades (<30); no Solana swaps found in window |
| 8 | cosby | low | `HmLwYRdPE3QsSexagobJdjxcWFZgqrSXtsQUrRZLWqnB` | 1 (0) | None | 0/1 | {'2026-W39': -4.11} (sd None) | 4.11 | -4.11 | 285821284 | 1038.6 | 0.0 | 0/0 | 0 / 0 of 0 | 106 | only 1 copyable trades (<30) |

## Recommendation (auto)
- Traders passing every filter: _benjitrades.
- Treat cut traders as watch or drop only. Mappings below medium confidence are not evidence of identity, so verify them before acting.
- Insider-like = several first entries less than 60 s after pair creation (launch sniping). Fast flips = round trips held under 60 s; fomo copiers cannot match these.

## Watch list (data/leader_watchlist.json), added 2026-10-23T23:59Z
Watched handles get a longer SWAP history on the next `scripts/leader_rank.py` run. Their rows will then use that window, so their counts won't be directly comparable with the 30 d rows. Watch is a recommendation only. The longer history has not been pulled yet: today's Helius budget is about used up (~29.9k of 30k).

- bystevenr: 90 d, up to 25 extra pages (about 2,500 Helius credits max on the first backfill). Current 30 d result: 25 copyable trades (<30), 7 entries <60 s after pair creation.
- pointfarmcap: 120 d, up to 25 extra pages (about 2,500 credits max). Current 30 d result: 13 copyable trades (<30), median hold about 25 h.

## Evidence per trader
### _benjitrades: `9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc`
- Provenance: [low] Only trader-analysis/wallets.json (source not recorded). The X handle _benjitrades was not found, and no post links the wallet. On-chain: fomo-relayed swaps; the median buy is about $2.0k against the leaderboard's $1.7k average, which is consistent but not proof.
- 727 swaps, 729 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 42 rounds in total; copying all of them at $50 would give $360.92. Median hold is 56.0 min.
- First tx 2026-09-03T22:55:13Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $-108.9 (shows whether one week carries the result)
- Worst copyable trades: 85Mo19cmRzg89Vz1niSw7jRZtrtfvCrkEwFSW1CBaQcg -99.4% (2026-10-11T18:53:39Z, https://solscan.io/tx/4wM2RU27FhswpzGSoY7s8Vky3mHvav9Pbm3yeX6jLzvbGaD8Z5siko2V8RZgcoHBWZKzGjRqW5yS6jDAN72jkQHo); Czt6xFcRWDPtZQABkN3RKv8kkMdvbCiZwvTUzvKbpump -99.1% (2026-10-06T19:42:48Z, https://solscan.io/tx/3hKzBEJewVaDhRAqJF7qA9gDGkL1KadrZ3gr9eyoRLHsAy18fUBXcWTcBRFTcTxymhaXogw8GVqHbF6jAFegLbHH); 5UxPc1WtxQPUXCfMZJFhhbvqNsbULEHRwYfMjyfEpump -97.7% (2026-10-21T11:14:50Z, https://solscan.io/tx/2U6xPT2hF9Dn7WDrFk93JSLoaQMCLhzbUdzzAmAGkNhtG7WTzPTwxWXQhn9V18JD6mVr617V5DxEgRf1QurttUqQ)

### ExactTallTakin: `AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v`
- Provenance: [medium] Third-party post listing the wallet next to the handle: https://x.com/OmegaTrades_SOL/status/2105278280920072452 (untrusted). On-chain, the wallet's swaps are fomo-app relayed (fee payer AgmLJBMD…, fee to R4rNJHaf…). It matches posted trades: posts say he was 'fully out' of $SI (DEW9dSN6…) by about Sep 30 (https://x.com/zettelkastten/status/2106524578684301700), and the wallet sold about $234k of SI on 2026-09-30 14:35-14:37Z (sig 3KUCCTE6ZeyWLW9b5YmF…). Posts also report SI re-buys at ~$12.5M MC and Dacity buys at $10-12M MC (https://x.com/TrenchWatchX/status/2112742656908443890). The wallet bought $10k of SI on 10-21 01:20Z (sig 2YxvzHdgjq7BKZwX9ToG…) and $2.5k of Dacity nxPqZ4F7… on 10-21 and 10-23. Sizes are smaller than posted, so there may be a second wallet. No self-post by the trader was found (X account is protected).
- 441 swaps, 443 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 143 rounds in total; copying all of them at $50 would give $158.94. Median hold is 0.6 min.
- First tx 2026-09-18T17:04:31Z; first funder `7iX1QyRNLTPLmRjmv3YrbtmDSsnhKxqwzSecg7diRgi7` (0.0806 SOL, https://solscan.io/tx/3RUnD324HTDN1i5dPm6ieLQJwfbVyQcHkUk1iRDqA4jBVbHSyPfSK3D8mJVdYSzwTXPH61X6U9N9XA5hoPxA1m7L); funder in rugger lists: False
- Copy PnL without the best week: $-410.6 (shows whether one week carries the result)
- Worst copyable trades: 39ahtL8ynzE4amH26J29C93PA5172V3ft9UuUcqQS8fz -99.9% (2026-10-06T22:26:09Z, https://solscan.io/tx/32raAckh1tjNXWkrCTBAtAx5WgALqXW2yQpyJhhRn5Qp4Z9Q1kHKzbvAkXdvBwhdq111CjKPrWoAbpyFJch7GR8L); 9JUYGis9NeLKjoHYG4A81UxikZYNg5VHZ5r5Y4xDpump -99.6% (2026-10-19T19:58:48Z, https://solscan.io/tx/2sK8EyYWMEfyThGoLyWYqs152P9T1o35ERHa1xE2VpgdKjqvS13DoFfgGnX1CphWfgDmPPSd2XVniAq6XceXrKzj); GK9Tu2kobcbzuCLsNQUZcXaq9A5EAEDwnm7H1Hbfpump -98.1% (2026-10-13T21:24:54Z, https://solscan.io/tx/5TbTe9KcfcoQ4coFV1m21obFWprjUF4zo8TBGuhqKJ9mhYKQN7HKJYProDJHjRmZDEGnnVGoBV1ZGicqo8AwrwmD)

### zelda89: `FG4c1qnq8vEc9nn6uxmtWVjWZLE9rxTfeExBYh5GQnRb`
- Provenance: [low] trader-analysis/wallets.json only.
- 3 swaps, 3 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 1 rounds in total; copying all of them at $50 would give $63.59. Median hold is 13621.6 min.
- First tx 2026-09-15T16:39:25Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $0.0 (shows whether one week carries the result)
- Worst copyable trades: 4zfwqBtYpDjdiocYL91bc4h2qoeuD13MwgbiZWbECPTE 127.2% (2026-10-02T04:49:16Z, https://solscan.io/tx/ov7cRtgwWzJPsRm6LoMtusCKoiTsCXa216HjgavEBLgrXLWAiydifUKeh3VqV75DU7FEVRhQzGZU3HzXH5bAkqQ)

### bystevenr: `AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx`
- Provenance: [low] trader-analysis/wallets.json only (source not recorded); no public post found linking it.
- 328 swaps, 337 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 67 rounds in total; copying all of them at $50 would give $3683.45. Median hold is 147.7 min.
- First tx 2026-08-09T04:17:07Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $87.0 (shows whether one week carries the result)
- Worst copyable trades: 5XHR1a82F8YRKuNzbdg1S2fwRgGmHG4Ly1JCJDyPpump -84.2% (2026-10-08T22:13:03Z, https://solscan.io/tx/zYzijTNdk6gyom99z5GVeoFfcM8HchymQ2o3YzSnTM1MbHREQ7trre26f7bKiWerbY5nGE63V3Ebg2bXLeFNPyy); Gyk9Z93Ri2JUjqES9HTpc7pxCJTLD7vhBhEjBhyApump -81.4% (2026-10-11T14:32:00Z, https://solscan.io/tx/2iAY1xeyWcwKzPVuxEDcrC8fw3ZRstV8YXs8FuwooWiyYPZKFfgKnbHkZKGAgsjocoioU1YW2Yka8xzNgFJorxYa); 9T1DbbiKfhfubEabDj5SWSMzBuyU4tJHkpSgR51Tpump -77.7% (2026-10-19T23:40:43Z, https://solscan.io/tx/3wSdZRayrMFmEjUC8Z4AFugZti1vovhyAPXTMHngckRPrJBzaDVDeYkg8ZU6FyKPqfQ7vxCPw6seoPaP5C5vMSDR)

### pointfarmcap: `Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit`
- Provenance: [medium-low] Several independent third-party posts name it as pointfarmcap's fomo wallet; the EVM pair 0xfd87… matches trader-analysis/wallets.json: https://x.com/fomo_xbt/status/2105392725235298657 , https://x.com/wutoken/status/2102979326081982935 (both untrusted, not by the trader). On-chain: see the fomo-relayed swap count in leader-rank.md. A posted trade has not been matched yet.
- 337 swaps, 336 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 16 rounds in total; copying all of them at $50 would give $257.67. Median hold is 1527.7 min.
- First tx 2025-10-31T01:45:16Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $-46.95 (shows whether one week carries the result)
- Worst copyable trades: B2GESkSErPjuCq6n4LcaJP5v2z1kJnw3xHVZnop2sZx -93.9% (2026-10-18T19:12:45Z, https://solscan.io/tx/21rfFVchVzKjaqpYdXaSfz6gtWFzUuUwM3LpkEDuh4fFXFTuRuK5wqvnNGLFEpYrKHpAvUhGbY9WMHZH5ScV9LFK); D3S6J9s1byrNBt3ZKwEDiPsNRqHtoEP8zQKdhyBdpump -46.5% (2026-10-18T19:59:09Z, https://solscan.io/tx/5u3Hv1NKbeVefQDFzfZWbfL21YnkGK6DBsobAWcda53z4qKU8FnhzYwkZcEoMpJHgrCBPrek3Y6uPuzavgTrfnFE); 8RNUw4N655VSrZKuhGdywhbSMDTrheguFPfxbpE2NZHQ -29.6% (2026-10-16T02:04:05Z, https://solscan.io/tx/3KgmHJJ3iN6xJZW7UzYiamyVNE7SdhRokwcWjuZXPDcJNnD7EoJ7EFa5LtkLDiEyDB7Q3ymXSVkaqhEQ1weP1MKc)

### BtheBezel: `HWYpE693cw8AWxHSynrHhUsKDbfzubAFYWpTcMZdNWKR`
- Provenance: [low] trader-analysis/wallets.json. StalkHQ calls this wallet the biggest $Dacity winner but does not name BtheBezel: https://x.com/StalkHQ/status/2113243077985095836. ETT's swaps pay small USDC fees to this wallet (likely fomo referral), e.g. sig 3shL3tC72j52GipjL6kc….
- 355 swaps, 353 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 91 rounds in total; copying all of them at $50 would give $-629.59. Median hold is 9.9 min.
- First tx 2026-05-13T19:00:14Z; first funder `B34R72b3btC9hvpdWQWWEbR1suBQ9C69DQC9oZd6qxZt` (27.2632 SOL, https://solscan.io/tx/5V9ERoVj2nMT2GY1jPL2mkJwT5M83UxQiXwiKC5e7G1UN3CwVoCKAGGN8dSBnQzoT143PVy925xc7dDVSDwxkhP7); funder in rugger lists: False
- Copy PnL without the best week: $-364.88 (shows whether one week carries the result)
- Worst copyable trades: ffw3qE9Vm5XvS3HKR3b38dey6qcezDok6NsF3X1w4qQ -100.0% (2026-10-06T03:33:20Z, https://solscan.io/tx/3c6RYzGbaenJVqnJgU4sWTdHNfUFGS24dM1ixVzd2Hk4RGQF6n3kLJeZmARWQ4DcDeMYAnp6mhQzHsPC5k3CCPC9); 6ZjXu9fMvvEWwpZFTvNaGfkYQU48VvHLYWmb5Uqbco3C -97.8% (2026-10-08T19:59:37Z, https://solscan.io/tx/tgGAXZRtAurPNttvVnxU58BQWMPZTEG9bK28dfJpr2W2TAFaE7idobbNy3FGBcQWKaVrxpuH7TP2N2T7NMBXxAn); 3CrvvHzAYTRFYatnLzV6ANPfvUCu56pPojG2ZSuqpump -97.7% (2026-10-07T01:01:56Z, https://solscan.io/tx/3yrgVUGTeDuCcKkpF9ngf1wongC4DfknJ8RttKDdMhvicM3drC3nrgKR5ncF4jTrDyjyE1Ct75WeBww3BcD6nuYW)

### Altcoinist: `DVFYHVKFYLxws4bV97va6EceVRrKjddHSWYq3is4ad49`
- Provenance: [low] trader-analysis/wallets.json only.
- 0 swaps, 0 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 0 rounds in total; copying all of them at $50 would give $0. Median hold is None min.
- First tx 2026-07-17T07:54:08Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $0 (shows whether one week carries the result)
- Worst copyable trades: 

### cosby: `HmLwYRdPE3QsSexagobJdjxcWFZgqrSXtsQUrRZLWqnB`
- Provenance: [low] trader-analysis/wallets.json only. The X user @Cosby is an actor, probably not the same person.
- 7 swaps, 7 fomo-app-relayed txs (fee payer AgmLJBMD… or platform fee to R4rNJHaf…). 1 rounds in total; copying all of them at $50 would give $-4.11. Median hold is None min.
- First tx 2026-07-10T00:47:19Z; first funder: not found (no plain SOL transfer in the first 5 txs)
- Copy PnL without the best week: $0.0 (shows whether one week carries the result)
- Worst copyable trades: 6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx -8.2% (2026-09-24T17:25:36Z, https://solscan.io/tx/2iTUbgWVFRuR4H74iDyanLQwLygE1SqDGGRwpXxtjxydLdU3LKnWqFVrZeuRUYdWSoupAStjUK5vCFai9D5sJE9Z)
