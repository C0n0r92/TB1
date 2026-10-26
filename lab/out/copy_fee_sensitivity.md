# Copy fee sensitivity v3 — self-copy vs copyfomo on the 30-day on-chain replay (PAPER ONLY)

_Generated 2026-10-24 01:11 UTC. Supersedes v2 (kept at out/copy_fee_sensitivity.md.bak-v2; v1 at copy_fee_sensitivity_v1.md). v2 costed the leaders' own round trips; v3 re-prices every copy from on-chain fills + Gecko 1-min paths (see out/copy_replay_30d.md) under both rule sets. Cost model reused from v2: Jupiter quotes in data/fs_quotes/quotes.jsonl._

## Cost model (round trip, per $ traded)

| pool liquidity | self $5 (prio 0.0001) | self $10 | self $5 (prio 0.0005) | copyfomo $5 |
|---|---|---|---|---|
| $50k | 2.82% | 2.60% | 4.45% | 7.79% |
| $100k | 2.28% | 2.07% | 3.91% | 7.25% |
| $300k | 1.43% | 1.22% | 3.07% | 6.41% |
| $1,000k | 0.93% | 0.71% | 2.56% | 5.90% |
| $3,000k | 0.93% | 0.71% | 2.56% | 5.90% |

## EV per trade by leader, rule set and cost model (5 s delay unless noted)

| leader | rules | size | n | self p0.0001 5s | self p0.0001 2s | self p0.0005 5s | copyfomo | Δ self−copyfomo $/trade |
|---|---|---|---|---|---|---|---|---|
| _benjitrades | OLD | $5 | 17 | +0.13 | -0.29 | +0.02 | -0.03 | +0.16 |
| _benjitrades | OLD | $10 | 17 | +0.29 | -0.54 | +0.18 | -0.02 | +0.30 |
| _benjitrades | OLD | $13 | 17 | +0.38 | -0.70 | +0.27 | -0.01 | +0.39 |
| _benjitrades | NEW | $5 | 4 | +0.67 | -0.62 | +0.57 | +0.35 | +0.32 |
| _benjitrades | NEW | $10 | 4 | +1.36 | -1.22 | +1.26 | +0.72 | +0.63 |
| _benjitrades | NEW | $13 | 4 | +1.77 | -1.58 | +1.68 | +0.95 | +0.82 |
| bystevenr | OLD | $5 | 4 | -0.56 | -0.55 | -0.64 | -0.69 | +0.13 |
| bystevenr | OLD | $10 | 4 | -1.09 | -1.08 | -1.18 | -1.35 | +0.25 |
| bystevenr | OLD | $13 | 4 | -1.41 | -1.39 | -1.50 | -1.74 | +0.33 |
| bystevenr | NEW | $5 | 2 | +1.59 | +1.60 | +1.48 | +0.77 | +0.81 |
| bystevenr | NEW | $10 | 2 | +3.20 | +3.23 | +3.09 | +1.58 | +1.62 |
| bystevenr | NEW | $13 | 2 | +4.17 | +4.21 | +4.06 | +2.06 | +2.11 |
| pointfarmcap | OLD | $5 | 1 | -1.08 | -0.97 | -1.29 | -1.17 | +0.08 |
| pointfarmcap | OLD | $10 | 1 | -2.12 | -1.90 | -2.32 | -2.26 | +0.15 |
| pointfarmcap | OLD | $13 | 1 | -2.74 | -2.45 | -2.94 | -2.92 | +0.18 |
| pointfarmcap | NEW | $5 | 0 | – | – | – | – | – |
| pointfarmcap | NEW | $10 | 0 | – | – | – | – | – |
| pointfarmcap | NEW | $13 | 0 | – | – | – | – | – |
| ExactTallTakin | OLD | $5 | 31 | +0.68 | -0.37 | +0.59 | +0.36 | +0.32 |
| ExactTallTakin | OLD | $10 | 31 | +1.38 | -0.72 | +1.29 | +0.74 | +0.64 |
| ExactTallTakin | OLD | $13 | 31 | +1.81 | -0.93 | +1.71 | +0.97 | +0.83 |
| ExactTallTakin | NEW | $5 | 5 | -0.59 | -0.49 | -0.68 | -0.69 | +0.10 |
| ExactTallTakin | NEW | $10 | 5 | -1.16 | -0.96 | -1.25 | -1.35 | +0.19 |
| ExactTallTakin | NEW | $13 | 5 | -1.50 | -1.24 | -1.59 | -1.74 | +0.24 |
| ALL | OLD | $5 | 53 | +0.38 | -0.37 | +0.28 | +0.12 | +0.26 |
| ALL | OLD | $10 | 53 | +0.78 | -0.70 | +0.68 | +0.27 | +0.51 |
| ALL | OLD | $13 | 53 | +1.02 | -0.91 | +0.92 | +0.36 | +0.67 |
| ALL | NEW | $5 | 11 | +0.26 | -0.13 | +0.17 | -0.13 | +0.39 |
| ALL | NEW | $10 | 11 | +0.55 | -0.23 | +0.45 | -0.23 | +0.78 |
| ALL | NEW | $13 | 11 | +0.72 | -0.29 | +0.62 | -0.29 | +1.01 |

Reading: self-copy saves roughly the cost-model gap per trade vs copyfomo; it does not turn a negative-EV leader positive unless the copyfomo column was already near zero. Full per-cell stats (CI, held-out, score) in out/copy_replay_30d.md and leaderboard rows CR_* / FS_*.
