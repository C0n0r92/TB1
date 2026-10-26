# Benji full-horizon copy replay (PAPER / BACKTEST ONLY)
_Lab, 2026-10-24 11:03Z. Script: bj_full_replay.py + bj_report.py. Data: data/cr/win + data/cr/wcandles (on-chain fills from free public RPC, GeckoTerminal candles). No Scout/Helius credits, no X reads. This supersedes the winners section in out/.cr_win_section.md, which is kept. That section had stale coverage and only SELF fitted costs. variants_tried after merge: **1083**._

## Answer
**Mostly no.** Mirroring his sells catches his biggest outlier only when we hold the full horizon with **no stop and no 08:00 flat**. Even then the result is not usable:
- **SI (+595 SOL to him).** He built that position from 29 buys over 3.9 days. A copy of his first buy with pure mirror and full horizon makes **+279%**. With the 08:00 Dublin flat it makes **-23%**, and every stop rule (B, C, D) is stopped out first at about −17% to −27%.
- **CRAWL 10-04 (+90 SOL).** Captured by mirror (A +116%) and by old rule D (+108%). Ladder B only gets +33% (BE stop after TP1), and live rule C is stopped out at −17%. The other two SI outliers (+37 and +33 SOL) are lost or small under every rule.
- **All of benji's covered trips after costs, filters off.** Mirror loses: n=31, self $10 -36.02 $, copyfomo $10 -41.54 $, median trade -20%. Every other rule loses too.
- **With live entry filters on, he leaves n=8, all in-sample.** Mirror at full horizon makes +30.51 $ at self $10, but without the best trade it is +2.65 $. That is SI by itself. With the 08:00 flat it falls to +2.01 $. The pre-registered hold-out has **0** benji trades, so this is not tested out of sample, and the METHOD score is 12/25 (needs ≥18 and n ≥50).
- **His own record has the same shape.** Scout's net5 for these 32 trips is +550 SOL, but without the best trade it is **-45 SOL**. His record after the hold-out date is -25.4 SOL on 2 trips. Copying him is effectively a bet that another SI happens and that we hold it without a stop or a night flat.
- **No exit family is a candidate for any of the three leaders.** onlyzhynx and bystevenr are positive in-sample only because of 1–2 outliers we could not have filtered for: none of onlyzhynx's trades pass the live filters, and only 1–2 of bystevenr's do. Held-out results are negative or flat.

## Coverage and setup
| leader | Scout trips | simulated | no candles | pass live filters | his pre-held bag at entry | drift clamped/missing → median | priced off his own fill (no pool decode) | held-out (≥10-15 07Z) | fails: age / mcap / liq / chase |
|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | 32 | 31 | 1 | 8 | 10 | 21 | 6 | 1 | 6 / 20 / 22 / 0 |
| bystevenr | 38 | 36 | 2 | 2 | 12 | 31 | 14 | 14 | 8 / 34 / 34 / 1 |
| onlyzhynx | 31 | 30 | 1 | 0 | 0 | 22 | 10 | 10 | 20 / 30 / 30 / 27 |

**Entry**
- We copy the buy where Scout's round trip starts, 5 s after his fill. Fill price is his measured 5 s pool drift; anything missing or outside 0.75–1.33 is clamped to his median (benji buy ×1.000, sell ×0.978). Later buys he makes are **not** copied.
- Live filters: token age ≥60 min and mcap ≥$1M (Scout's entry-time fields), pool liquidity ≥$100k (decoded on chain; trades priced off his own fill fail this), and chase ≤8% (our 5 s mid vs his fill).

**Costs (round trip + liquidity-scaled impact)**
- self $5 = 4.7%, self $10 = 3.0%, copyfomo $10 = 5.3%. Impact is fitted from out/copy_fee_sensitivity and decays as √(price/entry); pump.fun curve impact is used on the curve.
- Each extra sell leg adds $0.02 (self) or $0.015 (copyfomo).
- The realized entry round trip comes out at those figures. Median benji self $5 / $10 / copyfomo: 4.7% / 3.0% / 5.3%. Impact at $5–10 into ≥$100k pools is close to zero. The cost that matters is the 5 s delay and the stop slippage: stops fill at the bar open on a gap, otherwise at trigger ×0.975.

**Exit rules** (triggers on marked value net of exit cost)
- (a) **A_mirror**: sell his sell fraction of our position, all of it once he sells ≥95%. No stop.
- (b) **B_ladder**: TP +40% sells 25% and +100% sells 25%, the rest at +500%; breakeven stop after TP1; −20% hard stop, as in the earlier ladder tests.
- (c) **C_live**: SL −15%; TP +50% sells half; then a 15% trail from the peak on the rest.
- (d) **D_old**: SL −25%; TP +100% sells half; mirror his sells on the rest.
- Horizon is min(his exit + 24 h, entry + 7 d). The 08:00 variant flattens at the next 08:00 Dublin.

**Hold-out**
- Primary: fixed 2026-10-15 07:00 UTC, chosen before any CR result (the last 9 of 30 Dublin nights).
- Secondary, not pre-registered: each leader's last 30% of covered entries by time (benji from 10-02 04Z).
- Both are **selection-contaminated**: Scout picked these wallets because of these trades.

## Outliers: what each rule kept (self $10, % of stake)
| leader | token | entry UTC | his net5 SOL | his buys | passes filters | A mirror full | A mirror 08:00 | B ladder | C live | D old |
|---|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | SI | 09-25 23:33 | +595.0 | 29 | yes | +279% (horizon) | -23% (flat_0800) | -22% (stop) | -17% (stop) | -27% (stop) |
| _benjitrades | CRAWL | 10-04 08:31 | +90.4 | 7 | yes | +116% (mirror_full) | +116% (mirror_full) | +33% (stop_be) | -17% (stop) | +107% (mirror_full) |
| _benjitrades | CRAWL | 10-03 22:21 | +52.4 | 36 | no | +80% (mirror_full) | +80% (mirror_full) | -22% (stop) | -17% (stop) | -27% (stop) |
| _benjitrades | SI | 09-30 10:01 | +36.9 | 1 | yes | -20% (horizon) | -15% (flat_0800) | +8% (stop_be) | -17% (stop) | -26% (stop) |
| bystevenr | VEIL | 10-12 23:03 | +235.6 | 1 | yes | +273% (horizon) | +8% (flat_0800) | -22% (stop) | -17% (stop) | -27% (stop) |
| bystevenr | PQC | 10-08 17:03 | +172.5 | 11 | no | +202% (horizon) | +338% (flat_0800) | -22% (stop) | -17% (stop) | +36% (stop) |
| bystevenr | BNKR | 10-09 03:53 | +22.7 | 3 | no | +47% (mirror_full) | +47% (mirror_full) | +33% (stop_be) | -17% (stop) | +73% (mirror_full) |
| bystevenr | UP | 10-08 16:42 | +18.0 | 2 | no | -37% (horizon) | -26% (flat_0800) | -22% (stop) | -17% (stop) | -27% (stop) |
| onlyzhynx | tOpenAI | 09-29 05:22 | +197.7 | 5 | no | +394% (mirror_full) | +63% (flat_0800) | -22% (stop) | -17% (stop) | -27% (stop) |
| onlyzhynx | UNCC | 10-11 19:34 | +95.8 | 2 | no | +810% (mirror_full) | +810% (mirror_full) | +658% (tp3) | +781% (horizon) | +810% (mirror_full) |
| onlyzhynx | KURA | 10-05 17:14 | +16.4 | 1 | no | +163% (mirror_full) | +163% (mirror_full) | +88% (stop_be) | +161% (trail) | +163% (mirror_full) |
| onlyzhynx | NUKE | 10-05 17:55 | +3.7 | 2 | no | +29% (mirror_full) | +29% (mirror_full) | +12% (stop_be) | +26% (trail) | +29% (mirror_full) |

The 08:00 flat column is shown for A only. B, C and D are almost always stopped out before 08:00, so their flat and full results are the same.

## _benjitrades: full grid ($ PnL; self $5 rows on a $5 stake)
| exit | cost | horizon | filters | n | net $ | ex-best $ | mean | median | win | in-sample n / $ | held-out n / $ (10-15 07Z) | alt last-30% n / $ | score/25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_mirror | self5 | full | off | 31 | -21.89 | -34.59 | -14% | -22% | 19% | 30 / -19.30 | 1 / -2.60 | 10 / -4.92 | 8 |
| A_mirror | self5 | full | on | 8 | +13.14 | +0.44 | +33% | -13% | 38% | 8 / +13.14 | 0 / +0.00 | 2 / +4.11 | 13 |
| A_mirror | self5 | 08:00 flat | off | 31 | -33.26 | -38.85 | -21% | -22% | 16% | 30 / -30.99 | 1 / -2.27 | 10 / -2.97 | 8 |
| A_mirror | self5 | 08:00 flat | on | 8 | +0.19 | -5.39 | +0% | -19% | 25% | 8 / +0.19 | 0 / +0.00 | 2 / +6.47 | 11 |
| A_mirror | self10 | full | off | 31 | -36.02 | -63.88 | -12% | -20% | 19% | 30 / -31.09 | 1 / -4.92 | 10 / -7.41 | 7 |
| A_mirror | self10 | full | on | 8 | +30.51 | +2.65 | +38% | -11% | 38% | 8 / +30.51 | 0 / +0.00 | 2 / +9.13 | 12 |
| A_mirror | self10 | 08:00 flat | off | 31 | -61.54 | -73.11 | -20% | -20% | 16% | 30 / -57.15 | 1 / -4.38 | 10 / -3.94 | 7 |
| A_mirror | self10 | 08:00 flat | on | 8 | +2.01 | -9.56 | +3% | -17% | 25% | 8 / +2.01 | 0 / +0.00 | 2 / +13.58 | 11 |
| A_mirror | cf10 | full | off | 31 | -41.54 | -68.96 | -13% | -22% | 19% | 30 / -36.55 | 1 / -5.00 | 10 / -9.32 | 7 |
| A_mirror | cf10 | full | on | 8 | +28.53 | +1.12 | +36% | -13% | 38% | 8 / +28.53 | 0 / +0.00 | 2 / +8.57 | 12 |
| A_mirror | cf10 | 08:00 flat | off | 31 | -67.01 | -78.11 | -22% | -22% | 16% | 30 / -62.51 | 1 / -4.50 | 10 / -6.04 | 7 |
| A_mirror | cf10 | 08:00 flat | on | 8 | +0.20 | -10.89 | +0% | -19% | 25% | 8 / +0.20 | 0 / +0.00 | 2 / +12.83 | 10 |
| B_ladder | self5 | full | off | 31 | -19.51 | -21.16 | -13% | -22% | 26% | 30 / -18.41 | 1 / -1.10 | 10 / -6.54 | 9 |
| B_ladder | self5 | full | on | 8 | -7.31 | -7.70 | -18% | -22% | 12% | 8 / -7.31 | 0 / +0.00 | 2 / -0.71 | 9 |
| B_ladder | self5 | 08:00 flat | off | 31 | -19.51 | -21.16 | -13% | -22% | 26% | 30 / -18.41 | 1 / -1.10 | 10 / -6.54 | 9 |
| B_ladder | self5 | 08:00 flat | on | 8 | -7.31 | -7.70 | -18% | -22% | 12% | 8 / -7.31 | 0 / +0.00 | 2 / -0.71 | 9 |
| B_ladder | self10 | full | off | 31 | -30.04 | -33.38 | -10% | -22% | 32% | 30 / -27.84 | 1 / -2.20 | 10 / -7.62 | 9 |
| B_ladder | self10 | full | on | 8 | -6.08 | -9.42 | -8% | -22% | 38% | 8 / -6.08 | 0 / +0.00 | 2 / +4.13 | 9 |
| B_ladder | self10 | 08:00 flat | off | 31 | -30.04 | -33.38 | -10% | -22% | 32% | 30 / -27.84 | 1 / -2.20 | 10 / -7.62 | 9 |
| B_ladder | self10 | 08:00 flat | on | 8 | -6.08 | -9.42 | -8% | -22% | 38% | 8 / -6.08 | 0 / +0.00 | 2 / +4.13 | 9 |
| B_ladder | cf10 | full | off | 31 | -38.87 | -42.21 | -13% | -22% | 26% | 30 / -36.67 | 1 / -2.20 | 10 / -13.01 | 8 |
| B_ladder | cf10 | full | on | 8 | -14.60 | -15.40 | -18% | -22% | 12% | 8 / -14.60 | 0 / +0.00 | 2 / -1.40 | 8 |
| B_ladder | cf10 | 08:00 flat | off | 31 | -38.87 | -42.21 | -13% | -22% | 26% | 30 / -36.67 | 1 / -2.20 | 10 / -13.01 | 8 |
| B_ladder | cf10 | 08:00 flat | on | 8 | -14.60 | -15.40 | -18% | -22% | 12% | 8 / -14.60 | 0 / +0.00 | 2 / -1.40 | 8 |
| C_live | self5 | full | off | 31 | -14.03 | -17.43 | -9% | -17% | 13% | 30 / -13.17 | 1 / -0.86 | 10 / -5.45 | 10 |
| C_live | self5 | full | on | 8 | -6.85 | -5.99 | -17% | -17% | 0% | 8 / -6.85 | 0 / +0.00 | 2 / -1.71 | 9 |
| C_live | self5 | 08:00 flat | off | 31 | -12.25 | -15.65 | -8% | -17% | 16% | 30 / -11.39 | 1 / -0.86 | 10 / -3.68 | 10 |
| C_live | self5 | 08:00 flat | on | 8 | -5.07 | -5.99 | -13% | -17% | 12% | 8 / -5.07 | 0 / +0.00 | 2 / +0.07 | 9 |
| C_live | self10 | full | off | 31 | -27.34 | -34.32 | -9% | -17% | 13% | 30 / -25.63 | 1 / -1.71 | 10 / -10.77 | 8 |
| C_live | self10 | full | on | 8 | -13.70 | -11.99 | -17% | -17% | 0% | 8 / -13.70 | 0 / +0.00 | 2 / -3.42 | 8 |
| C_live | self10 | 08:00 flat | off | 31 | -23.58 | -30.56 | -8% | -17% | 16% | 30 / -21.87 | 1 / -1.71 | 10 / -7.01 | 8 |
| C_live | self10 | 08:00 flat | on | 8 | -9.94 | -11.99 | -12% | -17% | 12% | 8 / -9.94 | 0 / +0.00 | 2 / +0.34 | 8 |
| C_live | cf10 | full | off | 31 | -28.17 | -34.94 | -9% | -17% | 13% | 30 / -26.46 | 1 / -1.71 | 10 / -10.93 | 8 |
| C_live | cf10 | full | on | 8 | -13.70 | -11.99 | -17% | -17% | 0% | 8 / -13.70 | 0 / +0.00 | 2 / -3.43 | 8 |
| C_live | cf10 | 08:00 flat | off | 31 | -24.69 | -31.45 | -8% | -17% | 16% | 30 / -22.97 | 1 / -1.71 | 10 / -7.44 | 8 |
| C_live | cf10 | 08:00 flat | on | 8 | -10.21 | -11.99 | -13% | -17% | 12% | 8 / -10.21 | 0 / +0.00 | 2 / +0.06 | 8 |
| D_old | self5 | full | off | 31 | -22.30 | -27.55 | -14% | -27% | 13% | 30 / -20.95 | 1 / -1.34 | 10 / -4.70 | 9 |
| D_old | self5 | full | on | 8 | -2.40 | -7.66 | -6% | -26% | 12% | 8 / -2.40 | 0 / +0.00 | 2 / +3.98 | 9 |
| D_old | self5 | 08:00 flat | off | 31 | -20.13 | -25.39 | -13% | -27% | 16% | 30 / -18.79 | 1 / -1.34 | 10 / -2.53 | 9 |
| D_old | self5 | 08:00 flat | on | 8 | -0.24 | -5.49 | -1% | -22% | 25% | 8 / -0.24 | 0 / +0.00 | 2 / +6.14 | 10 |
| D_old | self10 | full | off | 31 | -42.28 | -53.03 | -14% | -27% | 13% | 30 / -39.60 | 1 / -2.69 | 10 / -8.52 | 7 |
| D_old | self10 | full | on | 8 | -3.84 | -14.59 | -5% | -24% | 12% | 8 / -3.84 | 0 / +0.00 | 2 / +8.51 | 9 |
| D_old | self10 | 08:00 flat | off | 31 | -38.05 | -48.80 | -12% | -27% | 16% | 30 / -35.36 | 1 / -2.69 | 10 / -4.28 | 7 |
| D_old | self10 | 08:00 flat | on | 8 | +0.40 | -10.35 | +0% | -21% | 25% | 8 / +0.40 | 0 / +0.00 | 2 / +12.75 | 10 |
| D_old | cf10 | full | off | 31 | -44.41 | -54.93 | -14% | -27% | 13% | 30 / -41.72 | 1 / -2.69 | 10 / -9.16 | 7 |
| D_old | cf10 | full | on | 8 | -4.41 | -14.93 | -6% | -24% | 12% | 8 / -4.41 | 0 / +0.00 | 2 / +8.30 | 8 |
| D_old | cf10 | 08:00 flat | off | 31 | -40.46 | -50.98 | -13% | -27% | 16% | 30 / -37.77 | 1 / -2.69 | 10 / -5.21 | 7 |
| D_old | cf10 | 08:00 flat | on | 8 | -0.46 | -10.98 | -1% | -21% | 25% | 8 / -0.46 | 0 / +0.00 | 2 / +12.25 | 9 |

## bystevenr
| exit | cost | horizon | filters | n | net $ | ex-best $ | mean | median | win | in-sample n / $ | held-out n / $ (10-15 07Z) | alt last-30% n / $ | score/25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_mirror | self10 | full | off | 36 | -29.83 | -57.16 | -8% | -28% | 28% | 22 / -3.25 | 14 / -26.57 | 11 / -26.63 | 7 |
| A_mirror | self10 | full | on | 2 | +20.72 | -6.62 | +104% | +104% | 50% | 1 / +27.34 | 1 / -6.62 | 1 / -6.62 | 12 |
| A_mirror | self10 | 08:00 flat | off | 36 | -18.60 | -52.39 | -5% | -20% | 28% | 22 / -3.80 | 14 / -14.80 | 11 / -15.96 | 8 |
| A_mirror | self10 | 08:00 flat | on | 2 | -2.67 | -3.48 | -13% | -13% | 50% | 1 / +0.81 | 1 / -3.48 | 1 / -3.48 | 9 |
| A_mirror | cf10 | full | off | 36 | -37.24 | -63.74 | -10% | -30% | 25% | 22 / -8.13 | 14 / -29.11 | 11 / -28.50 | 7 |
| A_mirror | cf10 | full | on | 2 | +19.80 | -6.69 | +99% | +99% | 50% | 1 / +26.49 | 1 / -6.69 | 1 / -6.69 | 12 |
| A_mirror | cf10 | 08:00 flat | off | 36 | -26.30 | -59.10 | -7% | -21% | 25% | 22 / -8.69 | 14 / -17.61 | 11 / -18.08 | 7 |
| A_mirror | cf10 | 08:00 flat | on | 2 | -3.06 | -3.63 | -15% | -15% | 50% | 1 / +0.57 | 1 / -3.63 | 1 / -3.63 | 9 |
| B_ladder | self10 | full | off | 36 | -21.45 | -49.91 | -6% | -22% | 31% | 22 / -26.06 | 14 / +4.62 | 11 / -19.44 | 8 |
| B_ladder | self10 | full | on | 2 | -4.40 | -2.20 | -22% | -22% | 0% | 1 / -2.20 | 1 / -2.20 | 1 / -2.20 | 9 |
| B_ladder | self10 | 08:00 flat | off | 36 | -18.75 | -47.21 | -5% | -22% | 31% | 22 / -24.16 | 14 / +5.41 | 11 / -18.65 | 9 |
| B_ladder | self10 | 08:00 flat | on | 2 | -4.40 | -2.20 | -22% | -22% | 0% | 1 / -2.20 | 1 / -2.20 | 1 / -2.20 | 9 |
| B_ladder | cf10 | full | off | 36 | -24.35 | -52.82 | -7% | -22% | 25% | 22 / -29.68 | 14 / +5.32 | 11 / -18.75 | 8 |
| B_ladder | cf10 | full | on | 2 | -4.40 | -2.20 | -22% | -22% | 0% | 1 / -2.20 | 1 / -2.20 | 1 / -2.20 | 9 |
| B_ladder | cf10 | 08:00 flat | off | 36 | -22.15 | -50.62 | -6% | -22% | 25% | 22 / -27.99 | 14 / +5.85 | 11 / -18.22 | 8 |
| B_ladder | cf10 | 08:00 flat | on | 2 | -4.40 | -2.20 | -22% | -22% | 0% | 1 / -2.20 | 1 / -2.20 | 1 / -2.20 | 9 |
| C_live | self10 | full | off | 36 | -26.22 | -43.08 | -7% | -17% | 17% | 22 / -28.13 | 14 / +1.91 | 11 / -11.52 | 9 |
| C_live | self10 | full | on | 2 | -3.43 | -1.71 | -17% | -17% | 0% | 1 / -1.71 | 1 / -1.71 | 1 / -1.71 | 9 |
| C_live | self10 | 08:00 flat | off | 36 | -26.93 | -43.79 | -7% | -17% | 17% | 22 / -26.71 | 14 / -0.22 | 11 / -13.65 | 8 |
| C_live | self10 | 08:00 flat | on | 2 | -3.43 | -1.71 | -17% | -17% | 0% | 1 / -1.71 | 1 / -1.71 | 1 / -1.71 | 9 |
| C_live | cf10 | full | off | 36 | -33.13 | -49.56 | -9% | -17% | 14% | 22 / -28.32 | 14 / -4.81 | 11 / -17.81 | 7 |
| C_live | cf10 | full | on | 2 | -3.43 | -1.71 | -17% | -17% | 0% | 1 / -1.71 | 1 / -1.71 | 1 / -1.71 | 9 |
| C_live | cf10 | 08:00 flat | off | 36 | -28.90 | -45.33 | -8% | -17% | 17% | 22 / -27.13 | 14 / -1.77 | 11 / -14.77 | 8 |
| C_live | cf10 | 08:00 flat | on | 2 | -3.43 | -1.71 | -17% | -17% | 0% | 1 / -1.71 | 1 / -1.71 | 1 / -1.71 | 9 |
| D_old | self10 | full | off | 36 | -39.01 | -46.31 | -11% | -27% | 22% | 22 / -15.14 | 14 / -23.87 | 11 / -21.44 | 7 |
| D_old | self10 | full | on | 2 | -5.37 | -2.69 | -27% | -27% | 0% | 1 / -2.69 | 1 / -2.69 | 1 / -2.69 | 9 |
| D_old | self10 | 08:00 flat | off | 36 | -32.35 | -39.64 | -9% | -27% | 25% | 22 / -12.75 | 14 / -19.60 | 11 / -17.16 | 8 |
| D_old | self10 | 08:00 flat | on | 2 | -5.37 | -2.69 | -27% | -27% | 0% | 1 / -2.69 | 1 / -2.69 | 1 / -2.69 | 9 |
| D_old | cf10 | full | off | 36 | -41.49 | -48.64 | -12% | -27% | 22% | 22 / -16.33 | 14 / -25.15 | 11 / -22.65 | 7 |
| D_old | cf10 | full | on | 2 | -5.37 | -2.69 | -27% | -27% | 0% | 1 / -2.69 | 1 / -2.69 | 1 / -2.69 | 9 |
| D_old | cf10 | 08:00 flat | off | 36 | -35.31 | -42.46 | -10% | -27% | 25% | 22 / -14.16 | 14 / -21.14 | 11 / -18.64 | 7 |
| D_old | cf10 | 08:00 flat | on | 2 | -5.37 | -2.69 | -27% | -27% | 0% | 1 / -2.69 | 1 / -2.69 | 1 / -2.69 | 9 |

## onlyzhynx (no trade passes the live filters)
| exit | cost | horizon | filters | n | net $ | ex-best $ | mean | median | win | in-sample n / $ | held-out n / $ (10-15 07Z) | alt last-30% n / $ | score/25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_mirror | self10 | full | off | 30 | +36.62 | -44.39 | +12% | -49% | 33% | 20 / +69.08 | 10 / -32.46 | 9 / -27.25 | 10 |
| A_mirror | self10 | full | on | 0 | | | | | | | | | |
| A_mirror | self10 | 08:00 flat | off | 30 | +21.62 | -59.38 | +7% | -39% | 33% | 20 / +54.67 | 10 / -33.04 | 9 / -27.83 | 10 |
| A_mirror | self10 | 08:00 flat | on | 0 | | | | | | | | | |
| A_mirror | cf10 | full | off | 30 | +29.11 | -49.86 | +10% | -50% | 30% | 20 / +63.09 | 10 / -33.98 | 9 / -28.66 | 10 |
| A_mirror | cf10 | full | on | 0 | | | | | | | | | |
| A_mirror | cf10 | 08:00 flat | off | 30 | +14.43 | -64.55 | +5% | -41% | 33% | 20 / +48.97 | 10 / -34.55 | 9 / -29.23 | 9 |
| A_mirror | cf10 | 08:00 flat | on | 0 | | | | | | | | | |
| B_ladder | self10 | full | off | 30 | +17.18 | -48.64 | +6% | -22% | 20% | 20 / +37.71 | 10 / -20.52 | 9 / -18.32 | 10 |
| B_ladder | self10 | full | on | 0 | | | | | | | | | |
| B_ladder | self10 | 08:00 flat | off | 30 | +17.18 | -48.64 | +6% | -22% | 20% | 20 / +37.71 | 10 / -20.52 | 9 / -18.32 | 10 |
| B_ladder | self10 | 08:00 flat | on | 0 | | | | | | | | | |
| B_ladder | cf10 | full | off | 30 | +14.40 | -49.71 | +5% | -22% | 20% | 20 / +35.23 | 10 / -20.83 | 9 / -18.63 | 9 |
| B_ladder | cf10 | full | on | 0 | | | | | | | | | |
| B_ladder | cf10 | 08:00 flat | off | 30 | +14.40 | -49.71 | +5% | -22% | 20% | 20 / +35.23 | 10 / -20.83 | 9 / -18.63 | 9 |
| B_ladder | cf10 | 08:00 flat | on | 0 | | | | | | | | | |
| C_live | self10 | full | off | 30 | +51.83 | -26.29 | +17% | -17% | 17% | 20 / +63.55 | 10 / -11.72 | 9 / -10.01 | 11 |
| C_live | self10 | full | on | 0 | | | | | | | | | |
| C_live | self10 | 08:00 flat | off | 30 | +51.83 | -26.29 | +17% | -17% | 17% | 20 / +63.55 | 10 / -11.72 | 9 / -10.01 | 11 |
| C_live | self10 | 08:00 flat | on | 0 | | | | | | | | | |
| C_live | cf10 | full | off | 30 | +48.35 | -27.76 | +16% | -17% | 17% | 20 / +60.58 | 10 / -12.23 | 9 / -10.52 | 11 |
| C_live | cf10 | full | on | 0 | | | | | | | | | |
| C_live | cf10 | 08:00 flat | off | 30 | +48.35 | -27.76 | +16% | -17% | 17% | 20 / +60.58 | 10 / -12.23 | 9 / -10.52 | 11 |
| C_live | cf10 | 08:00 flat | on | 0 | | | | | | | | | |
| D_old | self10 | full | off | 30 | +48.70 | -32.31 | +16% | -27% | 30% | 20 / +66.90 | 10 / -18.20 | 9 / -15.51 | 11 |
| D_old | self10 | full | on | 0 | | | | | | | | | |
| D_old | self10 | 08:00 flat | off | 30 | +52.27 | -28.74 | +17% | -27% | 30% | 20 / +70.47 | 10 / -18.20 | 9 / -15.51 | 11 |
| D_old | self10 | 08:00 flat | on | 0 | | | | | | | | | |
| D_old | cf10 | full | off | 30 | +44.17 | -34.81 | +15% | -27% | 27% | 20 / +63.24 | 10 / -19.06 | 9 / -16.38 | 10 |
| D_old | cf10 | full | on | 0 | | | | | | | | | |
| D_old | cf10 | 08:00 flat | off | 30 | +44.17 | -34.81 | +15% | -27% | 27% | 20 / +63.24 | 10 / -19.06 | 9 / -16.38 | 10 |
| D_old | cf10 | 08:00 flat | on | 0 | | | | | | | | | |

The full self $5 grid for bystevenr and onlyzhynx is in data/cr/bj_results.json. All 144 configurations are in leaderboard.csv as CR_BJ_* (rows with n=0 are omitted).

## METHOD score (25-point)
| row | OOS risk | drawdown | trades | edge | stability | total | nights + / all |
|---|---|---|---|---|---|---|---|
| benji A_mirror self$10 full, filters ON (best-looking) | 1 | 4 | 1 | 4 | 2 | **12** | 2/5 |
| benji A_mirror self$10 full, filters OFF | 1 | 1 | 3 | 1 | 1 | **7** | 3/13 |
| benji C_live (live rule) self$10, filters ON | 1 | 4 | 1 | 1 | 1 | **8** | 0/5 |
| onlyzhynx C_live self$10 full (highest any-leader total) | 1 | 2 | 3 | 4 | 1 | **11** | 2/14 |

Nothing reaches 18/25. Nothing has ≥50 trades or ≥20 held-out trades. **No candidate.**

## WHY THIS COULD FAIL
- **One trade is the whole result.** Benji's own +550 SOL is −45 SOL without SI. The only positive benji copy row loses money once SI is removed. Any rule that might miss the next SI (a stop, a night flat, a filter, a late entry) turns the strategy negative. A no-stop mirror also takes the full loss on every rug.
- **Selection bias.** Scout chose these three wallets because of these trades, so every "in-sample" number here is inflated by construction. The fixed hold-out has 1 benji trade (0 with filters on). After the hold-out date, his own record is negative (−25 SOL on 2 trips) and so are onlyzhynx's (−64 SOL) and bystevenr's (−20 SOL).
- **We don't copy his averaging.** SI came from 29 buys over 3.9 days. Copying only his first buy sizes us the opposite way to him: small when he is most confident. A model that copies his adds is untested.
- **Price path.** GT 1-min, then 15-min candles of one pool are rescaled to our fill. Fills of 21 of 31 benji trades use his median drift, and 6 trades are priced off his own fill (no pool decode). Stop fills on 15-min bars after the first day are coarse, so a stop and a TP inside one bar resolve stop-first.
- **Four trips have no candles** (benji PUMPERS, bystevenr UP×2, onlyzhynx Minibot; GT has no pool data for them. A GT retry recovered buni and Cardback). They are excluded rather than marked as losses, which probably biases the results up.
- **Costs are the team's stated round-trip figures, not fills we measured on these tokens.** The 5 s delay is assumed: copyfomo is often slower, and Chunk reports 3-min entry windows being missed.
- **Who is on the other side.** On SI and CRAWL, he is often the size that moves price, and our copy buys right behind him. When he takes profit, followers like us are the exit liquidity, and our 5 s-later sell fills below his print (sell drift ×0.978). On the losers, the other side is the deployer and early holders.

## Next
- Deprioritize copying benji as a strategy. If anything, run a paper-forward log of his *new* trips after 10-24 with mirror and no flat, and score it only once there are ≥20 trips.
- Untested: copying his adds (DCA-mirror) at a capped size. That is the only mechanism that could have captured SI, and a forward test is the only clean way to check it.
