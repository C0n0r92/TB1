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
