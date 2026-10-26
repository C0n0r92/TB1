# neodot copy replay (PAPER / RESEARCH ONLY: no trades, no funds, no keys)
Wallet 5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG, his 40 round trips (2026-10-09..10-23) from Scout's winners data (read only).

## Bottom line
- **Mirror exit, all 33 reconstructed trips, 0.1 SOL: L5 +19.8%/trade [95% CI −14.6%, +61.1%], L15 +14.1% [−21.3%, +58.0%], L30 +7.8% [−29.2%, +55.4%].** At 0.05 SOL it is about 2 pts worse (fixed tx costs): +17.7 / +12.0 / +5.7%. Every CI includes zero.
- **The mean is carried by one or two trips.** Medians are negative at every latency (−13% to −22%). Drop the best trip (WIPD +411% or INTERN +366%) and mirror L5 becomes +7.6%, L15 −0.4%, L30 −7.9%. Drop the top two and L5 is −4.0%.
- **Held out (his last 12 trips by date, 9 reconstructed):** mirror L5 +11.0% [−56%, +122%], but the median is −42% and the win rate 22%. **All of it is WIPD:** without WIPD it is −39%/trade. Ladder held out is negative at every latency (L5 −16.7% [−40%, +5%]).
- **Ladder (train-looking):** train +24.3% (L5, 0.1). That does not hold out (−16.7%). On held out the ladder's −20% stop knocked us out of WIPD before its run (−15% vs +411% mirror).
- **Latency is expensive.** Paired, all trips, mirror, 0.1 SOL: being 5 s behind instead of in his very next tx costs **−13.7 pts/trade [−22.2, −6.6]**. 5→15 s costs **−5.7 [−14.3, +2.7]** and 15→30 s **−6.3 [−15.9, +2.0]**, so 5→30 s is −12.0 [−25.0, +1.0]. Ladder steps: −8.7 / −3.3 / −5.1. Size barely matters (0.05 vs 0.1 differ by about 0.1 pt per step).
- **Verdict:** a small copy of neodot is **not demonstrably positive after costs at any latency.** The point estimate is positive only because of a fat right tail that 33 trips cannot pin down. The typical copied trade loses 13–22%. With n=33 (and n=9 held out), the CIs span about ±40 pts. Do not deploy on this evidence; at best it is a lottery-ticket profile.

## Method
- **Trips and legs:** his exact buy and sell txs (signature, slot, blockTime), from Scout's wg data plus a getTransaction per leg (keyless api.mainnet-beta.solana.com).
- **Copy:** his FIRST buy of each trip only, fixed size 0.05 or 0.1 SOL. Entry at his blockTime + L, for L = 5, 15, 30 s. L = 0 means landing in the tx right after his, at his post-state; it is a reference only.
- **Fill price:** the exact pool state, i.e. the post-state of the last successful tx on that pool with blockTime < t_his + L. The pool's full signature history for the hold came from getSignaturesForAddress (WIPD's PumpSwap pool needed about 436k signatures). Fills use constant-product math at our size, so slippage is included.
  - **SOL-quoted pump.fun curve:** virtual reserves from the pump TradeEvent.
  - **Non-SOL-quoted pump curve** (quote = PUMP, USDC-like and other tokens; 10 trips): token virtual reserve from the event, quote = vault balance + a virtual offset calibrated on his buy. SOL conversion uses the SOL↔quote rate realised in his own buy and sell tx (this embeds the hop cost), interpolated in time.
  - **PumpSwap:** vault balances (they match the pool's own event reserves) + a virtual quote offset fitted on his legs. Raw x·y=k on vaults was off by 20–50% for these pools; this needs a closer look.
- **Fees:**
  - Venue fee read from the pump fee-program return data on his tx: curve 1.25%, PumpSwap 1.1–1.25%, 0.3% on some pools.
  - 5000 lamports + 0.001 SOL priority per tx, so about 2 txs per trade (more with partial sells).
  - Sensitivity runs: priority 0.0002 and 0.003, and a +1% bot fee per swap.
  - ATA rent ignored, since it is refunded on close.
- **Mirror exit:** at each of his sells (+L), sell the same fraction of holdings he sold. On his last sell, sell everything.
- **Ladder exit:**
  - Rules: TP +40% → sell 25%; TP +100% → 25%; the rest on his sells or at +500%. SL −20%, moving to breakeven after TP1. Thresholds are on spot vs our fill price.
  - **Trigger detection:** GeckoTerminal free 1-minute OHLCV of the same pool (currency=token). Within a candle, the low is checked first (conservative). The trigger time is mid-candle and the fill is on the exact on-chain state at trigger + L.
  - The minute of entry is not scanned for triggers.
- **Split:** his 40 trips ordered by entry time; the last 12 (30%) are held out, of which 9 are reconstructed. The train set is 24 reconstructed of 28.
- **Statistics:** bootstrap 5000 resamples, seed 7, 95% percentile CI. Latency costs are paired differences on the same trips.

## Validation (repricing HIS OWN legs on his exact pre-trade state)
- **pump_sol:** buys 20, sells 19. Median error +0.33% / +0.40%, max 0.5%. The model is ~0.35% optimistic per swap, probably because of his router fee. The +1% bot-fee sensitivity covers this.
- **pump_q:** buys are exact by construction (calibrated). Sells 10: median +2.2%, max 6.1% optimistic.
- **PumpSwap:** buys 5, max 1.2%. Sells 12: median +0.35%. WIPD has two outliers: +9.5%, and −32.7% on his dust sell 9 h later.

## Unreconstructed trips (7 of 40) and bias
- **Which:** PUMPKIN ×3, SOLANA, TRUMP, ZC and STONK. Their buys or sells route through Raydium LaunchLab, CPMM, CLMM, Meteora DLMM, Whirlpool or multi-hop Jupiter paths I could not price from one pool state.
- **Which way:** his own gross on these is +51.2% mean, against +46.4% on the reconstructed ones, so dropping them probably biases our copy result *slightly down*. The impact is small next to the CI width.
- **Where they fall:** 3 of the 7 are in held out (TRUMP +79%, STONK +117%, ZC 0%). Held out is therefore 9 trips, and its picture would be less bad if TRUMP/STONK copied well.

**Other biases**
- **Ladder candles:** 1-minute candles miss sub-minute wicks, and low-first ordering is pessimistic for TPs. The entry minute is skipped, which misses very early TP/SL.
- **Copy rules:** we copy only his first buy. On Spiralism he averaged down three times and we did not (−59% vs his −40%).
- **No failed or late txs:** we assume our tx lands in the first block at or after t+L. In reality copy txs sometimes fail or land later, so true latency costs are probably worse.
- **Non-SOL quote rate:** linear between his buy and sell rates. This matters only for the 10 non-SOL-quoted trips.
- **Sample:** n=33 from one wallet over 2 weeks, and the wallet was selected *because* it was a winner (survivorship).

## Files
- **Scripts:** legs.py, pools.py, fetch_sigs.py, gt.py, replay.py, validate.py, analyze.py.
- **Raw output:** replay_rows.json (every row plus the ladder event logs), validation.json, results.csv.
- **Cache:** cache/ holds the tx, sig and GT caches.

---
## Main grid (base costs: venue fee + CPMM slippage + 5000 lamports + 0.001 SOL priority per tx)

| split | exit | size | L | n | mean/trade | 95% CI | P(mean>0) boot | median | win% | his gross mean (same trips) |
|---|---|---|---|---|---|---|---|---|---|---|
| train | mirror | 0.05 | 0 (ref) | 24 | +32.8% | [-3.4%, +82.7%] | 0.96 | +2.7% | 50% | +47.6% |
| train | mirror | 0.05 | 5 | 24 | +21.2% | [-10.6%, +62.6%] | 0.88 | -3.6% | 50% | +47.6% |
| train | mirror | 0.05 | 15 | 24 | +9.7% | [-21.4%, +49.8%] | 0.68 | -21.1% | 46% | +47.6% |
| train | mirror | 0.05 | 30 | 24 | +0.4% | [-31.5%, +43.9%] | 0.46 | -22.7% | 33% | +47.6% |
| train | mirror | 0.1 | 0 (ref) | 24 | +34.7% | [-1.7%, +84.8%] | 0.97 | +4.5% | 54% | +47.6% |
| train | mirror | 0.1 | 5 | 24 | +23.1% | [-9.0%, +64.8%] | 0.90 | -1.8% | 50% | +47.6% |
| train | mirror | 0.1 | 15 | 24 | +11.5% | [-19.8%, +51.9%] | 0.72 | -19.5% | 46% | +47.6% |
| train | mirror | 0.1 | 30 | 24 | +2.1% | [-30.0%, +45.8%] | 0.50 | -21.0% | 33% | +47.6% |
| train | ladder | 0.05 | 0 (ref) | 24 | +29.3% | [+4.2%, +58.2%] | 0.99 | +21.9% | 62% | +47.6% |
| train | ladder | 0.05 | 5 | 24 | +21.6% | [+0.9%, +45.8%] | 0.98 | +15.3% | 71% | +47.6% |
| train | ladder | 0.05 | 15 | 24 | +15.7% | [-9.5%, +49.1%] | 0.86 | -5.7% | 50% | +47.6% |
| train | ladder | 0.05 | 30 | 24 | +9.2% | [-15.0%, +39.3%] | 0.74 | -5.2% | 46% | +47.6% |
| train | ladder | 0.1 | 0 (ref) | 24 | +32.3% | [+6.8%, +61.7%] | 0.99 | +24.4% | 71% | +47.6% |
| train | ladder | 0.1 | 5 | 24 | +24.3% | [+3.2%, +49.1%] | 0.99 | +17.2% | 71% | +47.6% |
| train | ladder | 0.1 | 15 | 24 | +18.4% | [-7.4%, +52.3%] | 0.90 | -3.9% | 50% | +47.6% |
| train | ladder | 0.1 | 30 | 24 | +11.8% | [-12.8%, +42.4%] | 0.80 | -2.4% | 46% | +47.6% |
| held_out | mirror | 0.05 | 0 (ref) | 9 | +27.3% | [-48.6%, +150.5%] | 0.65 | -38.0% | 33% | +43.3% |
| held_out | mirror | 0.05 | 5 | 9 | +8.2% | [-57.6%, +116.8%] | 0.55 | -43.2% | 22% | +43.3% |
| held_out | mirror | 0.05 | 15 | 9 | +18.1% | [-54.0%, +139.2%] | 0.63 | -46.1% | 22% | +43.3% |
| held_out | mirror | 0.05 | 30 | 9 | +20.0% | [-55.6%, +148.2%] | 0.64 | -51.9% | 22% | +43.3% |
| held_out | mirror | 0.1 | 0 (ref) | 9 | +30.2% | [-47.2%, +156.1%] | 0.66 | -36.5% | 33% | +43.3% |
| held_out | mirror | 0.1 | 5 | 9 | +11.0% | [-56.2%, +122.3%] | 0.58 | -41.7% | 22% | +43.3% |
| held_out | mirror | 0.1 | 15 | 9 | +21.0% | [-52.5%, +144.9%] | 0.64 | -44.6% | 22% | +43.3% |
| held_out | mirror | 0.1 | 30 | 9 | +22.9% | [-54.2%, +154.0%] | 0.64 | -50.5% | 22% | +43.3% |
| held_out | ladder | 0.05 | 0 (ref) | 9 | -9.1% | [-33.7%, +12.0%] | 0.22 | +5.8% | 56% | +43.3% |
| held_out | ladder | 0.05 | 5 | 9 | -19.1% | [-42.1%, +1.7%] | 0.03 | -17.0% | 33% | +43.3% |
| held_out | ladder | 0.05 | 15 | 9 | -15.5% | [-37.8%, +3.2%] | 0.06 | -10.5% | 33% | +43.3% |
| held_out | ladder | 0.05 | 30 | 9 | -16.3% | [-40.9%, +6.4%] | 0.08 | -14.2% | 33% | +43.3% |
| held_out | ladder | 0.1 | 0 (ref) | 9 | -6.4% | [-31.5%, +15.3%] | 0.31 | +8.7% | 56% | +43.3% |
| held_out | ladder | 0.1 | 5 | 9 | -16.7% | [-40.4%, +4.8%] | 0.06 | -15.3% | 44% | +43.3% |
| held_out | ladder | 0.1 | 15 | 9 | -13.1% | [-35.9%, +6.3%] | 0.11 | -8.8% | 33% | +43.3% |
| held_out | ladder | 0.1 | 30 | 9 | -14.3% | [-39.2%, +8.8%] | 0.12 | -12.5% | 33% | +43.3% |
| all | mirror | 0.05 | 0 (ref) | 33 | +31.3% | [-7.5%, +78.2%] | 0.94 | -2.0% | 45% | +46.4% |
| all | mirror | 0.05 | 5 | 33 | +17.7% | [-16.3%, +58.3%] | 0.82 | -14.6% | 42% | +46.4% |
| all | mirror | 0.05 | 15 | 33 | +12.0% | [-23.0%, +55.1%] | 0.70 | -22.2% | 39% | +46.4% |
| all | mirror | 0.05 | 30 | 33 | +5.7% | [-30.8%, +52.6%] | 0.58 | -23.9% | 30% | +46.4% |
| all | mirror | 0.1 | 0 (ref) | 33 | +33.5% | [-5.7%, +81.1%] | 0.95 | -0.3% | 48% | +46.4% |
| all | mirror | 0.1 | 5 | 33 | +19.8% | [-14.6%, +61.1%] | 0.85 | -13.0% | 42% | +46.4% |
| all | mirror | 0.1 | 15 | 33 | +14.1% | [-21.3%, +58.0%] | 0.74 | -20.6% | 39% | +46.4% |
| all | mirror | 0.1 | 30 | 33 | +7.8% | [-29.2%, +55.4%] | 0.61 | -22.2% | 30% | +46.4% |
| all | ladder | 0.05 | 0 (ref) | 33 | +18.8% | [-1.7%, +41.2%] | 0.96 | +11.5% | 61% | +46.4% |
| all | ladder | 0.05 | 5 | 33 | +10.5% | [-7.6%, +29.5%] | 0.86 | +4.7% | 61% | +46.4% |
| all | ladder | 0.05 | 15 | 33 | +7.2% | [-12.9%, +32.0%] | 0.72 | -10.5% | 45% | +46.4% |
| all | ladder | 0.05 | 30 | 33 | +2.2% | [-16.5%, +23.9%] | 0.56 | -13.0% | 42% | +46.4% |
| all | ladder | 0.1 | 0 (ref) | 33 | +21.7% | [+0.8%, +44.5%] | 0.98 | +13.4% | 67% | +46.4% |
| all | ladder | 0.1 | 5 | 33 | +13.1% | [-5.2%, +32.4%] | 0.91 | +7.5% | 64% | +46.4% |
| all | ladder | 0.1 | 15 | 33 | +9.8% | [-10.7%, +34.9%] | 0.79 | -8.8% | 45% | +46.4% |
| all | ladder | 0.1 | 30 | 33 | +4.7% | [-14.3%, +26.9%] | 0.65 | -11.2% | 42% | +46.4% |

## Cost of each latency step (paired, same trips; mean difference in return per trade, 95% bootstrap CI)

| split | exit | size | step | mean cost per trade | 95% CI |
|---|---|---|---|---|---|
| train | mirror | 0.05 | 0s→5s | -11.5% | [-22.5%, -3.3%] |
| train | mirror | 0.05 | 5s→15s | -11.5% | [-21.5%, -3.4%] |
| train | mirror | 0.05 | 15s→30s | -9.3% | [-22.3%, +1.4%] |
| train | mirror | 0.05 | 5s→30s | -20.8% | [-37.1%, -7.4%] |
| train | mirror | 0.1 | 0s→5s | -11.6% | [-22.6%, -3.3%] |
| train | mirror | 0.1 | 5s→15s | -11.6% | [-21.6%, -3.4%] |
| train | mirror | 0.1 | 15s→30s | -9.4% | [-22.4%, +1.4%] |
| train | mirror | 0.1 | 5s→30s | -21.0% | [-37.3%, -7.4%] |
| train | ladder | 0.05 | 0s→5s | -7.7% | [-17.8%, +3.1%] |
| train | ladder | 0.05 | 5s→15s | -5.9% | [-18.3%, +7.1%] |
| train | ladder | 0.05 | 15s→30s | -6.5% | [-19.1%, +5.4%] |
| train | ladder | 0.05 | 5s→30s | -12.4% | [-31.0%, +4.2%] |
| train | ladder | 0.1 | 0s→5s | -8.1% | [-18.3%, +2.8%] |
| train | ladder | 0.1 | 5s→15s | -5.9% | [-18.4%, +7.2%] |
| train | ladder | 0.1 | 15s→30s | -6.6% | [-19.4%, +5.7%] |
| train | ladder | 0.1 | 5s→30s | -12.5% | [-31.4%, +4.5%] |
| held_out | mirror | 0.05 | 0s→5s | -19.1% | [-34.6%, -7.8%] |
| held_out | mirror | 0.05 | 5s→15s | +9.9% | [-1.6%, +25.6%] |
| held_out | mirror | 0.05 | 15s→30s | +1.9% | [-6.0%, +11.9%] |
| held_out | mirror | 0.05 | 5s→30s | +11.8% | [-5.4%, +36.5%] |
| held_out | mirror | 0.1 | 0s→5s | -19.3% | [-34.8%, -7.9%] |
| held_out | mirror | 0.1 | 5s→15s | +10.0% | [-1.6%, +25.9%] |
| held_out | mirror | 0.1 | 15s→30s | +1.9% | [-6.0%, +12.0%] |
| held_out | mirror | 0.1 | 5s→30s | +11.9% | [-5.4%, +36.8%] |
| held_out | ladder | 0.05 | 0s→5s | -10.1% | [-19.9%, -0.0%] |
| held_out | ladder | 0.05 | 5s→15s | +3.6% | [-1.8%, +9.5%] |
| held_out | ladder | 0.05 | 15s→30s | -0.8% | [-14.4%, +9.6%] |
| held_out | ladder | 0.05 | 5s→30s | +2.8% | [-10.7%, +13.4%] |
| held_out | ladder | 0.1 | 0s→5s | -10.3% | [-20.2%, -0.1%] |
| held_out | ladder | 0.1 | 5s→15s | +3.6% | [-1.8%, +9.5%] |
| held_out | ladder | 0.1 | 15s→30s | -1.3% | [-15.0%, +8.7%] |
| held_out | ladder | 0.1 | 5s→30s | +2.4% | [-11.3%, +12.7%] |
| all | mirror | 0.05 | 0s→5s | -13.6% | [-22.1%, -6.6%] |
| all | mirror | 0.05 | 5s→15s | -5.7% | [-14.2%, +2.7%] |
| all | mirror | 0.05 | 15s→30s | -6.2% | [-15.8%, +2.0%] |
| all | mirror | 0.05 | 5s→30s | -11.9% | [-24.9%, +1.0%] |
| all | mirror | 0.1 | 0s→5s | -13.7% | [-22.2%, -6.6%] |
| all | mirror | 0.1 | 5s→15s | -5.7% | [-14.3%, +2.7%] |
| all | mirror | 0.1 | 15s→30s | -6.3% | [-15.9%, +2.0%] |
| all | mirror | 0.1 | 5s→30s | -12.0% | [-25.0%, +1.0%] |
| all | ladder | 0.05 | 0s→5s | -8.4% | [-16.4%, +0.1%] |
| all | ladder | 0.05 | 5s→15s | -3.3% | [-12.2%, +5.8%] |
| all | ladder | 0.05 | 15s→30s | -5.0% | [-15.0%, +4.1%] |
| all | ladder | 0.05 | 5s→30s | -8.2% | [-21.5%, +4.1%] |
| all | ladder | 0.1 | 0s→5s | -8.7% | [-16.8%, -0.1%] |
| all | ladder | 0.1 | 5s→15s | -3.3% | [-12.4%, +5.8%] |
| all | ladder | 0.1 | 15s→30s | -5.1% | [-15.3%, +4.2%] |
| all | ladder | 0.1 | 5s→30s | -8.4% | [-21.9%, +4.2%] |

(step cost shown as change in return: negative = latency costs you that many % points per trade)

## Cost sensitivity (mirror exit, all reconstructed trips)

| size | L | base (0.001 prio) | low prio 0.0002 | high prio 0.003 | +1% bot fee/swap |
|---|---|---|---|---|---|
| 0.05 | 5 | +17.7% | +21.5% | +8.5% | +15.3% |
| 0.05 | 15 | +12.0% | +15.7% | +3.1% | +9.7% |
| 0.05 | 30 | +5.7% | +9.4% | -2.9% | +3.6% |
| 0.1 | 5 | +19.8% | +21.8% | +15.1% | +17.4% |
| 0.1 | 15 | +14.1% | +16.0% | +9.5% | +11.8% |
| 0.1 | 30 | +7.8% | +9.7% | +3.3% | +5.6% |

## Per-trip (mirror, 0.1 SOL, base) 

| # | sym | split | venue model | his gross | L0 | L5 | L15 | L30 | ladder L5 | ladder L5 events |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | CONAN | train | pump_sol | +77.6% | +64.4% | +59.0% | +42.9% | -12.2% | +87.9% | tp1 tp2 his |
| 1 | Spiralism | train | pumpswap | -39.8% | -59.0% | -58.7% | -53.0% | -56.6% | +3.3% | stop0.8 |
| 2 | SWIMOTHY | train | pump_q | +190.4% | +172.0% | +169.2% | +174.8% | +187.3% | +113.1% | tp1 tp2 his |
| 3 | INTERN | train | pump_sol | +495.1% | +456.4% | +365.8% | +332.0% | +379.4% | +207.7% | tp1 tp2 his |
| 4 | DOGS | train | pump_sol | +87.8% | +70.5% | +69.9% | -20.2% | -45.9% | +69.9% | his |
| 5 | HEADS | train | pump_sol | +2.9% | -3.4% | -18.3% | -40.4% | -33.2% | -27.3% | stop0.8 |
| 6 | TAILS | train | pump_sol | +15.6% | +8.3% | -6.8% | -35.0% | -31.9% | +30.7% | tp1 tp2 stop1.0 |
| 7 | StayDown | train | pump_sol | +40.7% | +30.8% | +24.8% | +25.8% | +32.4% | +39.8% | tp1 his |
| 8 | GLOW | train | pump_q | -15.6% | -19.0% | -34.1% | -44.3% | -58.6% | +12.1% | stop0.8 |
| 9 | fun | train | pumpswap | -75.1% | -76.8% | -76.8% | -79.6% | -79.9% | -76.8% | his |
| 10 | Yaku | train | pump_sol | +99.2% | +58.1% | +56.9% | +27.7% | -17.8% | +56.6% | tp1 his |
| 11 | Garou | train | pump_sol | +33.0% | +23.9% | +22.4% | +8.2% | +6.6% | +22.5% | tp1 his |
| 12 | LOAF | train | pump_sol | -4.3% | -10.0% | -8.6% | +3.2% | -22.2% | -37.0% | stop0.8 |
| 13 | LOAF | train | pump_sol | +25.2% | +13.4% | +15.2% | +21.8% | +19.8% | +15.2% | his |
| 17 | 1 | train | pump_sol | +1.5% | -5.3% | -13.0% | -23.2% | -35.9% | +7.5% | tp1 stop1.0 |
| 18 | ROBOTFIGHT | train | pump_sol | +161.8% | +138.4% | +55.0% | +74.4% | +71.9% | +39.3% | tp1 tp2 his |
| 19 | ROBOTFIGHT | train | pump_sol | +46.3% | +35.5% | +19.1% | -20.6% | -19.8% | +19.1% | his |
| 20 | ser | train | pumpswap | +7.8% | +0.8% | +3.1% | +6.3% | +11.9% | +3.1% | his |
| 21 | memedeath | train | pump_sol | -49.4% | -52.1% | -52.7% | -52.5% | -52.2% | -35.8% | stop0.8 |
| 22 | POKEMONOOOR | train | pump_sol | +8.0% | -0.3% | -18.4% | -54.7% | -54.3% | -22.0% | stop0.8 |
| 23 | PHILIP | train | pump_q | +127.4% | +106.3% | +116.0% | +117.9% | +6.8% | +72.6% | tp1 tp2 his |
| 24 | PHILIP | train | pump_q | -7.3% | -14.1% | -22.5% | -22.1% | -41.9% | +28.2% | tp1 tp2 stop1.0 |
| 25 | JEWTWO | train | pump_q | -92.6% | -93.8% | -95.0% | -95.0% | -94.9% | -26.0% | stop0.8 |
| 26 | KIM | train | pump_sol | +5.0% | -12.5% | -16.9% | -18.8% | -7.8% | -21.7% | stop0.8 |
| 28 | Pokéball | held_out | pump_q | -41.6% | -44.4% | -53.7% | -53.7% | -58.2% | +1.9% | tp1 stop1.0 |
| 29 | grail | held_out | pump_q | -54.0% | -57.5% | -61.7% | -62.8% | -64.0% | +29.3% | tp1 tp2 stop1.0 |
| 31 | WIPD | held_out | pump_sol | +531.0% | +483.3% | +411.4% | +476.5% | +511.2% | -15.3% | stop0.8 |
| 32 | KIMCHI | held_out | pump_q | +78.7% | +65.9% | +46.6% | +38.7% | +25.5% | +21.4% | tp1 tp2 his his |
| 33 | KIMCHI | held_out | pump_q | +28.6% | +11.4% | -24.1% | -8.8% | -12.5% | -24.1% | his |
| 34 | Susan | held_out | pump_sol | +16.0% | -4.8% | -22.0% | -24.1% | -6.7% | +3.4% | tp1 stop1.0 |
| 36 | DIF | held_out | pump_sol | -83.7% | -87.2% | -87.3% | -86.9% | -87.8% | -87.4% | stop0.8 |
| 37 | QRCAT | held_out | pump_q | -31.8% | -36.5% | -41.7% | -44.6% | -50.6% | -30.7% | stop0.8 |
| 39 | DNN | held_out | pump_sol | -53.9% | -58.1% | -68.6% | -45.3% | -50.5% | -48.7% | stop0.8 |

## Not reconstructed

| # | sym | split | his gross | reason |
|---|---|---|---|---|
| 14 | PUMPKIN | train | +21.4% | non-pump venue (111111,3TK9D8,6EF8rr,6Vo324,AToken,DRVSpZ,JUP6Lk,Tokenk,Tokenz,goonud,whirLb) |
| 15 | PUMPKIN | train | +94.9% | non-pump venue (111111,6EF8rr,6Vo324,AToken,DEXYos,JUP6Lk,MNFSTq,Tokenk,Tokenz,goonud,whirLb) |
| 16 | PUMPKIN | train | +72.8% | non-pump venue (111111,AToken,JUP6Lk,LanMV9,SCoRcH,Tokenk,Tokenz,ZERor4,ojh19o,whirLb) |
| 27 | SOLANA | train | -27.2% | non-pump venue (111111,3TK9D8,6EF8rr,6Vo324,AToken,CAMMCz,JUP6Lk,MNFSTq,Tokenk,Tokenz) |
| 30 | TRUMP | held_out | +79.4% | non-pump venue (111111,AToken,CPMMoo,JUP6Lk,LBUZKh,Tokenk,Tokenz) |
| 35 | ZC | held_out | +0.1% | non-pump venue (111111,AToken,BiSoNH,JUP6Lk,LanMV9,TessVd,Tokenk,Tokenz) |
| 38 | STONK | held_out | +117.0% | non-pump venue (111111,AToken,CPMMoo,JUP6Lk,LBUZKh,Tokenk,Tokenz,ZERor4,whirLb) |

His own gross on unreconstructed trips: mean +51.2% (n=7) vs reconstructed +46.4% (n=33).