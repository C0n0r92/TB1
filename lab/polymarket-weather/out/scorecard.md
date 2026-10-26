# Polymarket weather - scorecard (auto)
_updated 2026-10-23T22:21:28Z_

BACKFILL = historical replay, OPTIMISTIC fills. LIVE = forward paper test from logged books. Never mix them.

| variant | trades | win | net $ | mean ret | CI95 | OOS | score | cand | lucky | MC DD p95 | open |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PMW_bf_m03_fee | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m03_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m05_fee | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m05_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m08_fee | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m08_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m12_fee | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m12_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m15_fee | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_bf_m15_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  |  |
| PMW_live_m03_fee | 0 |  | 0 |  |  |  |  |  | n/a |  | 79 |
| PMW_live_m03_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  | 74 |
| PMW_live_m05_fee | 0 |  | 0 |  |  |  |  |  | n/a |  | 65 |
| PMW_live_m05_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  | 62 |
| PMW_live_m08_fee | 0 |  | 0 |  |  |  |  |  | n/a |  | 50 |
| PMW_live_m08_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  | 48 |
| PMW_live_m12_fee | 0 |  | 0 |  |  |  |  |  | n/a |  | 35 |
| PMW_live_m12_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  | 32 |
| PMW_live_m15_fee | 0 |  | 0 |  |  |  |  |  | n/a |  | 29 |
| PMW_live_m15_fee5 | 0 |  | 0 |  |  |  |  |  | n/a |  | 27 |

## Calibration
- Backfill model Brier (all 0 brackets): None
- Backfill subset with a market price (0 brackets, model p>=0.05 only): model None vs market None (lower is better)
- Live (resolved, one point per token per lead bucket, n=0): model None vs market mid None

Backfill model reliability (bucket, n, mean p, hit rate):

Live model reliability:
