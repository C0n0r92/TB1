# Copy fee sensitivity: copyfomo vs a self-run Jupiter copier (2026-10-23T23:12:01+00:00, PAPER ONLY, research only)

Question (Zero): replacing copyfomo's ~5.3% round trip with a self-run Jupiter copier, which leaders turn profitable, and by how much per $5 copy?

## Short answer

- **_benjitrades** (29 copies): copyfomo -0.57/copy (median -1.26, total -16.63) -> Jupiter 2 s -0.39/copy (median -1.09, total -11.25); pessimistic band -0.61/copy. stays negative; without the best copy: -21.27 (Jupiter) vs -26.05 (copyfomo). Score 8 -> 10/25.
- **bystevenr** (27 copies): copyfomo +9.23/copy (median -0.47, total +249.09) -> Jupiter 2 s +9.86/copy (median -0.26, total +266.25); pessimistic band +9.13/copy. already positive under copyfomo; without the best copy: +93.63 (Jupiter) vs +84.38 (copyfomo). Score 19 -> 19/25.
- **pointfarmcap** (8 copies): copyfomo +2.60/copy (median +0.69, total +20.79) -> Jupiter 2 s +2.93/copy (median +0.95, total +23.45); pessimistic band +2.56/copy. already positive under copyfomo; without the best copy: +7.99 (Jupiter) vs +6.16 (copyfomo). Score 19 -> 19/25.
- **ExactTallTakin** (39 copies): copyfomo -0.44/copy (median -0.53, total -17.08) -> Jupiter 2 s -0.24/copy (median -0.32, total -9.51); pessimistic band -0.50/copy. stays negative; without the best copy: -23.72 (Jupiter) vs -30.51 (copyfomo). Score 8 -> 10/25.

## Cost assumptions

| model | explicit fee/side | per-tx fixed | slippage | delay / drift | stop fill |
|---|---|---|---|---|---|
| REF copyfomo (unchanged from copy_candidates.py central) | 2.0% | $0.015/side (=$0.03 gas per round trip) | 0.5% + 2 x $5/$20k assumed pool | 10 s; approx mode +2% entry drift; exit at leader's sell price | 2.5% below -25% trigger |
| JUP central | 0.30% (pool LP ~0.25% + route; Jupiter swap API platform fee 0) | priority fee P + $0.0005 base, per tx (buy, TP leg, final sell) | 0.5% + 2 x $5 / liq(mcap), liq = 0.41 x sqrt($70k x mcap) | 2 s or 5 s; approx mode drift 2% x delay/10 s on entry AND exit | 2.5% below trigger |
| JUP pessimistic | 0.50% | $0.0505 per tx | 1.0% + 2 x $5 / (liq/2) | full 2% adverse drift on entry and exit | 2.5% below trigger |

Round trip at $5 (approx, no TP leg): REF ~ 4% fees + 1.0% slip + $0.03/$5 (0.6%) + 2% drift = ~7.6% incl. lag; JUP 2 s P=$0.02 ~ 0.6% fees + ~1.0% slip + $0.041/$5 (0.8%) + 0.8% drift = ~3.2%; JUP 5 s ~ 4.4%; JUP pessimistic ~ 1.0% + 2.0% + 2.0% + 4.0% = ~9%. Impact of a $5 ticket is ~0.03% at $100k mcap, so the size term is negligible; the base slip and the delay drift dominate.

Why liq(mcap): no point-in-time liquidity exists for these leader trades. A pump.fun coin graduates to a constant-product pool holding ~20.6% of supply at ~$70k mcap (liq ~ 0.41 x mcap); as price rises the pool's token share falls with 1/sqrt(price), giving liq ~ 0.41 x sqrt(70k x mcap): ~$34k at $100k, ~$77k at $500k, ~$108k at $1M. Non-pump pools and LP pulls break this, hence the liq/2 band.

Delay pricing: Zero asked to price entry/exit from the next swaps after the delay. That needs the pool's swaps a few slots after the leader's tx. Free sources tried: api.mainnet-beta.solana.com returned 429 (rate-limited, shared IP), solana-rpc.publicnode.com returns null for month-old transactions, GeckoTerminal /trades only keeps the last 24 h. So: trades with cached 1-min candles (8 of the copies; data/copytest/candles) use the candle interpolated at t+delay (1-min resolution cannot really separate 2 s from 5 s); the rest use the drift assumption above. This is the weakest assumption in the file: the pessimistic band (2% drift even at 2 s) is there because 686/291/52 copyfomo copiers and sniper bots race the same buy within the same slot.

## Per leader, per model ($5 per copy, bootstrap = 5,000 resamples of the per-copy $, seed 7; MC DD on $91)

| leader | model | copies | win | mean $/copy | median $/copy | total $ | ex-best $ | bootstrap 95% CI of mean $ | nights +/total | OOS n / mean $ | MC DD p95 | score /25 (oos,dd,n,edge,stab) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | REF_copyfomo | 29 | 24% | -0.57 | -1.26 | -16.63 | -26.05 | [-1.40, +0.42] | 4/15 | 6 / -0.38 | 32% | 8 (1,2,3,1,1) |
| _benjitrades | JUP_feesonly_10s_refdrift | 29 | 24% | -0.43 | -1.13 | -12.39 | -22.29 | [-1.28, +0.59] | 4/15 | 6 / -0.23 | 29% | 9 (1,3,3,1,1) |
| _benjitrades | JUP_2s_P0.005 | 29 | 24% | -0.36 | -1.06 | -10.38 | -20.47 | [-1.23, +0.67] | 5/15 | 6 / -0.17 | 28% | 10 (1,3,3,1,2) |
| _benjitrades | JUP_2s_P0.020 | 29 | 24% | -0.39 | -1.09 | -11.25 | -21.27 | [-1.25, +0.64] | 5/15 | 6 / -0.21 | 29% | 10 (1,3,3,1,2) |
| _benjitrades | JUP_2s_P0.050 | 29 | 24% | -0.45 | -1.14 | -12.99 | -22.85 | [-1.31, +0.57] | 4/15 | 6 / -0.27 | 30% | 9 (1,3,3,1,1) |
| _benjitrades | JUP_5s_P0.005 | 29 | 24% | -0.40 | -1.11 | -11.54 | -21.51 | [-1.26, +0.63] | 4/15 | 6 / -0.20 | 29% | 9 (1,3,3,1,1) |
| _benjitrades | JUP_5s_P0.020 | 29 | 24% | -0.43 | -1.13 | -12.41 | -22.30 | [-1.28, +0.59] | 4/15 | 6 / -0.23 | 29% | 9 (1,3,3,1,1) |
| _benjitrades | JUP_5s_P0.050 | 29 | 24% | -0.49 | -1.19 | -14.13 | -23.88 | [-1.34, +0.53] | 4/15 | 6 / -0.30 | 31% | 8 (1,2,3,1,1) |
| _benjitrades | JUP_2s_P0.050_pess | 29 | 24% | -0.61 | -1.32 | -17.65 | -27.01 | [-1.43, +0.38] | 4/15 | 6 / -0.41 | 33% | 8 (1,2,3,1,1) |
| _benjitrades | JUP_5s_P0.050_pess | 29 | 24% | -0.61 | -1.32 | -17.65 | -27.01 | [-1.43, +0.38] | 4/15 | 6 / -0.41 | 33% | 8 (1,2,3,1,1) |
| _benjitrades | ZERO_cost_bound | 29 | 24% | -0.25 | -0.95 | -7.30 | -17.72 | [-1.14, +0.81] | 5/15 | 6 / -0.08 | 26% | 10 (1,3,3,1,2) |
| bystevenr | REF_copyfomo | 27 | 41% | +9.23 | -0.47 | +249.09 | +84.38 | [+0.77, +23.21] | 7/13 | 20 / +11.76 | 14% | 19 (4,4,3,5,3) |
| bystevenr | JUP_feesonly_10s_refdrift | 27 | 41% | +9.71 | -0.31 | +262.12 | +91.53 | [+0.96, +24.18] | 7/13 | 20 / +12.33 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_2s_P0.005 | 27 | 41% | +9.92 | -0.23 | +267.94 | +94.76 | [+1.04, +24.61] | 7/13 | 20 / +12.59 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_2s_P0.020 | 27 | 41% | +9.86 | -0.26 | +266.25 | +93.63 | [+1.01, +24.50] | 7/13 | 20 / +12.52 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_2s_P0.050 | 27 | 41% | +9.74 | -0.32 | +262.86 | +91.37 | [+0.94, +24.28] | 7/13 | 20 / +12.38 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_5s_P0.005 | 27 | 41% | +9.77 | -0.29 | +263.73 | +92.61 | [+0.99, +24.28] | 7/13 | 20 / +12.40 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_5s_P0.020 | 27 | 41% | +9.71 | -0.32 | +262.05 | +91.49 | [+0.96, +24.17] | 7/13 | 20 / +12.33 | 13% | 19 (4,4,3,5,3) |
| bystevenr | JUP_5s_P0.050 | 27 | 41% | +9.58 | -0.37 | +258.69 | +89.25 | [+0.89, +23.95] | 7/13 | 20 / +12.19 | 14% | 19 (4,4,3,5,3) |
| bystevenr | JUP_2s_P0.050_pess | 27 | 41% | +9.13 | -0.53 | +246.53 | +82.83 | [+0.72, +23.03] | 7/13 | 20 / +11.65 | 15% | 19 (4,4,3,5,3) |
| bystevenr | JUP_5s_P0.050_pess | 27 | 41% | +9.13 | -0.53 | +246.53 | +82.83 | [+0.72, +23.03] | 7/13 | 20 / +11.65 | 15% | 19 (4,4,3,5,3) |
| bystevenr | ZERO_cost_bound | 27 | 41% | +10.30 | -0.10 | +278.10 | +100.41 | [+1.19, +25.35] | 7/13 | 20 / +13.04 | 12% | 19 (4,4,3,5,3) |
| pointfarmcap | REF_copyfomo | 8 | 50% | +2.60 | +0.69 | +20.79 | +6.16 | [-0.31, +6.40] | 2/3 | 8 / +2.60 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_feesonly_10s_refdrift | 8 | 50% | +2.85 | +0.88 | +22.80 | +7.52 | [-0.15, +6.78] | 2/3 | 8 / +2.85 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_2s_P0.005 | 8 | 50% | +2.97 | +0.99 | +23.79 | +8.24 | [-0.05, +6.95] | 2/3 | 8 / +2.97 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_2s_P0.020 | 8 | 50% | +2.93 | +0.95 | +23.45 | +7.99 | [-0.08, +6.89] | 2/3 | 8 / +2.93 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_2s_P0.050 | 8 | 50% | +2.85 | +0.89 | +22.77 | +7.49 | [-0.14, +6.77] | 2/3 | 8 / +2.85 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_5s_P0.005 | 8 | 50% | +2.89 | +0.91 | +23.13 | +7.76 | [-0.12, +6.83] | 2/3 | 8 / +2.89 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_5s_P0.020 | 8 | 50% | +2.85 | +0.88 | +22.79 | +7.51 | [-0.15, +6.77] | 2/3 | 8 / +2.85 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_5s_P0.050 | 8 | 50% | +2.76 | +0.82 | +22.11 | +7.01 | [-0.21, +6.66] | 2/3 | 8 / +2.76 | 4% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_2s_P0.050_pess | 8 | 50% | +2.56 | +0.62 | +20.44 | +5.92 | [-0.34, +6.33] | 2/3 | 8 / +2.56 | 5% | 19 (5,5,1,4,4) |
| pointfarmcap | JUP_5s_P0.050_pess | 8 | 50% | +2.56 | +0.62 | +20.44 | +5.92 | [-0.34, +6.33] | 2/3 | 8 / +2.56 | 5% | 19 (5,5,1,4,4) |
| pointfarmcap | ZERO_cost_bound | 8 | 50% | +3.17 | +1.15 | +25.33 | +9.29 | [+0.08, +7.23] | 2/3 | 8 / +3.17 | 3% | 20 (5,5,1,5,4) |
| ExactTallTakin | REF_copyfomo | 39 | 18% | -0.44 | -0.53 | -17.08 | -30.51 | [-1.07, +0.46] | 3/14 | 8 / -0.83 | 34% | 8 (1,2,3,1,1) |
| ExactTallTakin | JUP_feesonly_10s_refdrift | 39 | 26% | -0.29 | -0.38 | -11.17 | -25.20 | [-0.94, +0.65] | 4/14 | 8 / -0.70 | 29% | 9 (1,3,3,1,1) |
| ExactTallTakin | JUP_2s_P0.005 | 39 | 26% | -0.21 | -0.29 | -8.35 | -22.65 | [-0.88, +0.73] | 4/14 | 8 / -0.65 | 27% | 10 (1,3,3,2,1) |
| ExactTallTakin | JUP_2s_P0.020 | 39 | 26% | -0.24 | -0.32 | -9.51 | -23.72 | [-0.91, +0.69] | 4/14 | 8 / -0.68 | 28% | 10 (1,3,3,2,1) |
| ExactTallTakin | JUP_2s_P0.050 | 39 | 23% | -0.30 | -0.38 | -11.84 | -25.87 | [-0.96, +0.63] | 3/14 | 8 / -0.73 | 30% | 9 (1,3,3,1,1) |
| ExactTallTakin | JUP_5s_P0.005 | 39 | 26% | -0.26 | -0.35 | -10.15 | -24.27 | [-0.92, +0.67] | 4/14 | 8 / -0.68 | 28% | 9 (1,3,3,1,1) |
| ExactTallTakin | JUP_5s_P0.020 | 39 | 23% | -0.29 | -0.38 | -11.31 | -25.34 | [-0.95, +0.64] | 3/14 | 8 / -0.71 | 29% | 9 (1,3,3,1,1) |
| ExactTallTakin | JUP_5s_P0.050 | 39 | 23% | -0.35 | -0.44 | -13.62 | -27.48 | [-1.00, +0.57] | 3/14 | 8 / -0.77 | 31% | 8 (1,2,3,1,1) |
| ExactTallTakin | JUP_2s_P0.050_pess | 39 | 21% | -0.50 | -0.59 | -19.41 | -32.75 | [-1.15, +0.41] | 3/14 | 8 / -0.63 | 36% | 8 (1,2,3,1,1) |
| ExactTallTakin | JUP_5s_P0.050_pess | 39 | 18% | -0.50 | -0.59 | -19.50 | -32.85 | [-1.15, +0.41] | 3/14 | 8 / -0.64 | 36% | 8 (1,2,3,1,1) |
| ExactTallTakin | ZERO_cost_bound | 39 | 38% | -0.10 | -0.17 | -3.85 | -18.59 | [-0.78, +0.87] | 4/14 | 8 / -0.55 | 24% | 10 (1,3,3,2,1) |

## Split by night (Dublin), $ per night: REF copyfomo vs JUP 2 s P=$0.02

- **_benjitrades**: 09-25 -6.06/-3.85, 09-26 +1.95/+2.27, 09-27 -0.42/+0.07, 09-28 -0.86/-0.67, 10-01 -4.11/-3.70, 10-03 +0.82/+1.09, 10-04 +0.41/+0.66, 10-06 -4.98/-4.98, 10-07 -1.09/-0.91, 10-09 -1.53/-1.42, 10-10 -1.53/-1.42, 10-11 -1.19/-1.01, 10-12 -1.37/-1.21, 10-15 -1.53/-1.42, 10-22 +4.87/+5.24
- **bystevenr**: 10-08 +14.93/+16.83, 10-09 -1.13/-0.95, 10-10 +12.57/+13.77, 10-11 -2.06/-1.74, 10-12 +164.34/+172.69, 10-13 +0.82/+1.31, 10-14 +30.95/+32.54, 10-15 -2.83/-2.55, 10-16 -0.47/-0.26, 10-18 +3.69/+4.09, 10-20 -2.00/-1.68, 10-21 +31.80/+33.62, 10-22 -1.53/-1.42
- **pointfarmcap**: 10-15 +4.07/+5.01, 10-18 -2.54/-2.01, 10-19 +19.26/+20.45
- **ExactTallTakin**: 09-24 +13.34/+14.80, 09-25 -0.51/-0.31, 10-01 -3.68/-1.89, 10-02 -1.03/-0.62, 10-03 +0.40/+0.65, 10-04 -4.21/-3.81, 10-06 -1.67/-1.29, 10-07 -8.44/-7.38, 10-08 -4.60/-4.26, 10-13 -2.21/-2.12, 10-17 -1.65/-1.17, 10-19 -0.12/+0.03, 10-20 +0.76/+1.15, 10-21 -3.46/-3.30

## How much of the drag is fees? (mean $/copy uplift vs REF)

| leader | REF mean | JUP fees only (REF drift) | JUP 2 s P$0.005 | JUP 2 s P$0.05 | JUP 5 s P$0.02 | JUP pess. | ZERO-cost bound | ZERO-cost median |
|---|---|---|---|---|---|---|---|---|
| _benjitrades | -0.57 | -0.43 | -0.36 | -0.45 | -0.43 | -0.61 | -0.25 | -0.95 |
| bystevenr | +9.23 | +9.71 | +9.92 | +9.74 | +9.71 | +9.13 | +10.30 | -0.10 |
| pointfarmcap | +2.60 | +2.85 | +2.97 | +2.85 | +2.85 | +2.56 | +3.17 | +1.15 |
| ExactTallTakin | -0.44 | -0.29 | -0.21 | -0.30 | -0.29 | -0.50 | -0.10 | -0.17 |

Reading: the pessimistic band ignores the delay (2% drift at 2 s and 5 s alike), so its 2 s and 5 s rows are equal by construction. ZERO-cost = no fee, no slippage, no drift, no gas, instant copy: the most any copier could get from these leaders with these rules. If a leader loses even there, cheaper execution cannot rescue them.
Bootstrap caution: bystevenr's CI excludes 0 only because one +3,300% copy dominates every resample that contains it; it is not a robust edge (median copy < 0).

## Lottery-ticket check (Jupiter 2 s, P=$0.02)

- _benjitrades: top 3 copies +10.02, +5.24, +2.27 of total -11.25; without top 3: -28.78; share of copies losing: 22/29; path-mode (1-min candles) copies: 1.
- bystevenr: top 3 copies +172.62, +35.04, +32.54 of total +266.25; without top 3: +26.05; share of copies losing: 16/27; path-mode (1-min candles) copies: 0.
- pointfarmcap: top 3 copies +15.46, +4.99, +4.24 of total +23.45; without top 3: -1.25; share of copies losing: 4/8; path-mode (1-min candles) copies: 0.
- ExactTallTakin: top 3 copies +14.21, +2.57, +1.46 of total -9.51; without top 3: -27.75; share of copies losing: 29/39; path-mode (1-min candles) copies: 8.

## Candidate check (METHOD: >= 18/25, >= 50 trades, holds OOS with >= 20 OOS trades and OOS CI low > 0)

- _benjitrades: 10/25, 29 copies, OOS 6 -> not a candidate (fails trade count) (fails OOS count).
- bystevenr: 19/25, 27 copies, OOS 20 -> not a candidate (fails trade count).
- pointfarmcap: 19/25, 8 copies, OOS 8 -> not a candidate (fails trade count) (fails OOS count).
- ExactTallTakin: 10/25, 39 copies, OOS 8 -> not a candidate (fails trade count) (fails OOS count).

## WHY THIS COULD FAIL

- The leaders' histories are Scout's reconstruction from wallets whose mapping is LOW confidence for _benjitrades and bystevenr (medium-low pointfarmcap, medium ExactTallTakin). _benjitrades' live TRUTH buy came from a wallet we don't have, so his file is not his full trading.
- Partial coverage: bystevenr from Oct 8, pointfarmcap only Oct 16-21 (8 copies). 22 of bystevenr's and 8 of pointfarmcap's first buys are still open and excluded.
- Most copies are approx mode (no price path): TP/SL hits are inferred from the leader's round trip; intratrade stop-outs before a recovery are invisible, which flatters leaders who hold through dips.
- The delay drift is assumed, not measured (see 'Delay pricing'). If bots front-run the leader in the same slot, a 2 s copier pays the pessimistic band, not the central one.
- A self-run copier needs its own infra (RPC/websocket, signing, key management, retries) and fails differently from copyfomo: missed txs, failed swaps in congestion, stuck partial fills. None of that is modelled. Running it would be a live-trading change: proposal only, not tested here.
- Means are carried by 1-3 lottery coins; medians tell the typical copy.

Who is on the other side: the leader (sells into followers), the snipers/bundlers who bought before the leader, and the other copy bots and copyfomo's own copiers racing the same buy. Lower fees don't change who we trade against; a faster copier only moves us up that queue.

Multiple testing: 11 cost/delay models x 4 leaders added to the variants count (rows FS_*).
