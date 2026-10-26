# Scout: active-now (7d roster-bar screen, updated 11:06 UTC)

**Standing rules:**
- After 5% costs: positive median trade, positive net with the best trade removed, 30+ closed trades preferred
- **Median hold ≥45 min (HARD rule, since 09:44)**; swing holders (hours) rank above flippers
- Not a sniper, bundler or custodial wallet; not on the lists; entries mostly >$100k mcap; active in the last 1-2h
- Day tag means ≥60% of swaps in 07-20 UTC

**Status:** 0 passes so far. Helius credits this round: 0 (public RPC + GeckoTerminal only).

## 7d roster bar (ask of 10:27 UTC), updated 11:06 UTC
**Bar:** 7d net >0 after 5% and >0 without the best trade, using both the SOL figures and the price-consistent figures. Also ≥15 closed in 7d; median hold ≥30 min; entries mostly ≥$300k mcap with ≥$100k liquidity; not MEV, sniper, bundler, custodial or listed.
**Result: 0 passes. Nothing written to selfcopy/roster_inbox.json. It holds `[]`; it was created 10:29:15 UTC by something other than Scout, and Scout has not touched it.**
- YpnnUu1ZPHpAzy4xggEd5pBTbu1aDayXuARsYsavNs9 (ypnn-day) **FAILS** the new bar.
  - SOL-based: 35 closed, +15.76 SOL, ex-best +6.95, hold 64 min.
  - Price-consistent: net −16.64 SOL, ex-best −16.72, median trade −5.4%. 6 rounds credit SOL far above the token's price move (e.g. 5UUH9R: 1.09→9.96 SOL while the price moved +0.9%), so tokens came in outside the parsed buys.
- Re-checked all 98+ cached wallets with ev7: none pass. Closest misses:
  - AFXf: hold 4.5 min
  - Ew4ue: hold 11.2 min
  - 2Rr1zZ: ex-best <0 and hold too short
  - FUuq and J1uTL: ex-best <0
  - FU6FTN: ex-best −2.17
  - 67kUFU: tokenized-stock mints; its SOL vs price figures are an artifact
- Winners dataset 7d: none pass.
  - 5o3k: hold 16 min, mcap about $6k
  - 82uF: hold 12.6 min
  - HMDW: ex-best −0.81
- Kolscan daily board: 26 KOLs, none on the lists. Deep 7d fetches:
  - Pain J6TDXv: 20 closed, −66.23 SOL
  - omar Dgehc8: 92 closed, −80.6 SOL
  - Grimace EA4MXk: 111 closed, +6.80 SOL, ex-best +2.89, but hold 0.5 min, so it fails
  - The others are higher-rate flippers by sig profile
- Wallets with the same timestamps were skipped as a cluster: 8MNZ8s / CZvfCk / H26ArD / 2QNqLP.
- GT swing candidates (in-sample buy→sell ≥30 min): 49 queued for 7d fetch. The fetch is still running.
- Results so far for the wallets fetched (Kolscan + GT swing):
  - Dgehc8: 92 closed, net -80.6 SOL, ex-best -100.53, price-consistent net -94.99, median hold 0.7 min
  - EA4MXk: 111 closed, net 6.8 SOL, ex-best 2.89, price-consistent net 6.8, median hold 0.5 min
  - J6TDXv: 20 closed, net -66.23 SOL, ex-best -71.04, price-consistent net -66.62, median hold 539.3 min
  - 8Mub5h: 75 closed, net -19.61 SOL, ex-best -26.92, price-consistent net -19.61, median hold 30.1 min
  - 2ANtqM: 0 closed round trips in 7d
  - 7Q1Qh3: 0 closed round trips in 7d
  - 9khVda: 10 closed, net -1.25 SOL, ex-best -3.77, price-consistent net -3.77, median hold 117.3 min
  - 8TD3nf: 154 closed, net -7.73 SOL, ex-best -10.75, price-consistent net -7.73, median hold 3.1 min
  - 95uR1u: 5 closed, net -5.52 SOL, ex-best -9.34, price-consistent net -9.48, median hold 4.7 min
  - qjKD9g: 46 closed, net 2.14 SOL, ex-best -4.93, price-consistent net 2.14, median hold 3.9 min
  - 7zr8Tk: 0 closed round trips in 7d
  - 7Emom4: 0 closed round trips in 7d
  - 8muixP: 8 closed, net -0.87 SOL, ex-best -2.08, price-consistent net -2.14, median hold 1030.4 min
  - DGnCnj: 0 closed round trips in 7d
  - H36Kon: 0 closed round trips in 7d
  - CBhGH3: 0 closed round trips in 7d
  - EC1MK7: 75 closed, net -1.76 SOL, ex-best -2.16, price-consistent net -1.77, median hold 3.4 min
  - F3BihW: 0 closed round trips in 7d
  - 2baaSE: 13 closed, net -10.37 SOL, ex-best -10.49, price-consistent net -10.56, median hold 39.4 min
  - FWcTGb: 96 closed, net 0.32 SOL, ex-best -1.25, price-consistent net -1.08, median hold 2.1 min
  - G9bR3b: 53 closed, net -15.3 SOL, ex-best -19.86, price-consistent net -16.98, median hold 18.5 min
  - 5Z4DJu: 57 closed, net -13.38 SOL, ex-best -13.61, price-consistent net -13.38, median hold 3.4 min
  - DBiStm: 0 closed round trips in 7d
  - CAXcfp: 0 closed round trips in 7d

## Passers
(none yet)

## Watchlist
(none yet)

## Near miss
- YpnnUu1ZPHpAzy4xggEd5pBTbu1aDayXuARsYsavNs9: **REJECT (median trade -1.7%)**, tag **both** (day share 0.47, peaks 20, 21 and 23 UTC)
  - Passes the hold rule (64 min)
  - 35 closed in 5.6d, win 40%, +15.76 SOL (+7.1%), ex-best +6.95 SOL
  - Last trade 08:43:55Z

## Rejects (after 5% costs); [H] means it also fails the 45-min hold rule
- CjEU92NcVZLirUa8U7foNUSByhn6TszvrszgKKqLGphj (day 0.86): **REJECT** on the 30d fetch (1500 txs, 25.2d)
  - 22 closed, median -2.6%, net +2.28 SOL but ex-best -88.2 SOL (one moonshot), win 41%, median hold 14.3m [H]
  - The earlier 9d view (3 closed, +102.8) was dominated by one trade
- Ew1LspcKKCDgp9cfquLM6Sbg6ZZgUTbXSR2gZzVgnvnk (day): **REJECT**, median entry mcap ~$45k (0/12 entries >$100k); idle since 10-23 15:05Z; 4 closed
  - Hold 224m OK; not on the lists; no create-slot buys seen; Solscan shows no label
- Free screen, 09:50-10:10 (same method + flip filter, then the swing-weighted sig pre-screen)
  - GcMcBj (day 0.93): median -14% [H 0.6m]
  - 8KmJgg (day 0.68): median -33%, -21.6 SOL [H 1.7m]
  - Ee4TEL (day 0.79): 5 closed, median +0.2%, ex-best -1.06 [H 22.8m]
  - FsgLVC (day 0.92): median -36%, -17.3 SOL [H 17.6m]
  - 92KvVJ (day 0.90): median -24%, -25.1 SOL; hold 74.8m OK
  - JXHdMT (day 0.89): median -13%, -52.6 SOL; hold 64.7m OK
  - FNSZNh (day 0.83): median -42% [H 9.2m]
  - 5uW8td (night 0.46): median +3.7% but ex-best -0.89 [H 21.7m]
  - E8Nk2A (day 0.64): median -5.7% [H 0.8m]
  - G6swLJ (both 0.51): median -14.7% [H 15.4m]
  - GgDAij (both 0.58): median -20.9%, -55 SOL; hold 573m OK
  - Y6rZHu / Z1RZ8o (both/day): pump bots, losing [H 1.3-1.5m]; likely linked (same last trade at 09:04:01Z)
  - Bax3yy / ZpxqUg (day 0.98/1.0): pump 72-75%, median -23 to -27% [H 3m]; likely linked (same last trade at 08:57:00Z)
  - CZdRuh (day 1.0): 2 closed, dust
  - DA5Cdn (day): 1 closed
  - 8Seej1 (day 0.68): 10 closed in 1.0d, median -0.3%, ex-best +0.59; hold 59m OK (near miss: median just negative, too few trades)
  - FLMmW9 (day 0.73): median -10.7%, -7.8 SOL; hold 46m OK
  - BAFWUY (day 0.75): median -63%, -39 SOL [H 26m]
  - 4VTbK9 (day 0.81): median +26.8%, ex-best +1.9, hold 102m, but only 3 closed and the last swap was 10-21 19:56Z (not active now)
  - 3SQEvP (day 0.81): 13 closed, 0 wins, -45 SOL; hold 65m OK
- Suspected cluster (skipped): about 12 wallets with an identical sig profile (day 0.66, peaks 19/18/09 UTC, ~1265h span, 10 txs in 2h): BBnb, BT8bo, Eg7y, HFxZ, ARsS, BtsX, C4zz, H1Dr, HmeG, HqBG, J4EU, J4fJ. A likely farm or bundle, so not evaluated
- Day-heavy screen (Helius, 08:55): no list hits and no create-slot buys in the sampled first buys
  - GL7MFX (day): median -26%, -6.03 SOL [H 6.1m]
  - ErEX2b (day): median -4.7%, -26.2 SOL [H 3.8m]
  - AAACdD (day): 79% pump coins, median -11.7% [H 7.1m]
  - FUuqK2 (day): +1.95 SOL but -9.58 ex-best, median -8.2%; hold 58m OK
  - xc8TRx (day): median -17.6%; hold 150m OK; entry mcap ~$449k
  - 86KFS6 (day): -42 SOL, entry mcap ~$10k [H 14m]
  - DcahqU (day): median -20.5%, dust sizes; entry mcap ~$474k [H 3.8m]
- Free screen, 09:00-09:50: GT top-volume pools with mcap $100k-$50M, MEV and arb removed, 14d public-RPC history
  - AFXfDh (day 0.80): median -3.4%, ex-best +0.16 [H 3.5m]
  - F6Y13V (day 0.79): median -19.7%, -4.4 SOL; idle 2h; hold 175m OK
  - 9pxPNk (day 0.76): median -21%, -14.4 SOL [H 11m]
  - DRXMnT (both 0.54): median -10.7%, pump 64% [H 13.5m]
  - 7yL1nP (day 0.82): median +1.9% but -21.8 SOL, ex-best -24.3 [H 23.5m]
  - 8FH8Gg (day 0.93): median -16.7% [H 2.4m]
  - i65PC4 (day 0.89): pump 79% [H 0.6m]
  - 3QaPeh (day 0.72): 6 closed, -252 SOL [H 37m]
  - CcBAvA (day 0.69): median -20.9% [H 16.6m]
  - 2utLKa (both 0.54): median -47%; hold 49.5m OK
  - Am7qrF (day 0.60): -49.5 SOL [H 12.7m]
  - GtjsH9 (day 1.0): 3 closed, ex-best +0.06 [H 3.6m]
  - AJQohf (day 0.96): median -4.5% [H 1.4m]
  - GEiV1z (day 0.97): median -37%, pump 81% [H 5m]
  - Kyfnnb (day 1.0): 6 closed, 0 wins, -46.5 SOL [H 37m]
- Earlier rounds (pre-09:00; hold is shown only where it fails)
  - 5SGjrc: median -17%
  - CtqXA1: net -5.07 SOL; hold 77m OK
  - A1s3dJ, AicU, HAQv: hold <1m [H]
  - 2VpmF [H]
  - GB8dKAE: median -6.6%
  - BLUEZY: pump, losing
  - J1uTL: moonshot-driven (ex-best -10.34)
  - 99Jvd: -0.28 SOL; hold 65m OK
  - BNs4x: median -8.4%; hold 72m OK
  - CQw2B: 0 wins; hold 71m OK
  - Y3FJr: 2 closed
  - 7UZoia, D3yhn, 6GxQ6, 3K7X, ACjJnM, 8zkg, BpuSM: net negative
  - FQbwA1, 93LYj6, GemDd, Pavlo: idle
  - 67YoDo, Limfork: too few trades
  - KOLs:
    - Flames: -31 SOL
    - Wugi [H 0.1m]
    - k4ye [H 0.3m]
    - Latuche: ex-best -2.37
    - Ethan Prosper [H 1.3m]
    - Alpha wallet 4: -18.5 SOL
    - Cented, decu, Kadenox, Jijo, theo: unparseable
  - Top GT pool traders: MEV/arb bots
- Method note: the first create-slot pass used maxSupportedTransactionVersion 0, so v1 txs were skipped; it was fixed for later checks.

## Session 2026-10-24 ~11:40 UTC — Zero's new bar (supersedes hold>=30m)
New bar: 7d coverage; >=15 closed; net and ex-best >0 at 5% costs, price-capped; median capped trade at 4% round trip >0; median hold 1-30 min; last swap <=24h ago; >=50% of swaps at 00-20 UTC; mcap>=$300k and liq>=$100k share >=0.7; not sniper, bundler, MEV, farm or custodial.
5s delay is NOT modelled yet. That only matters for wallets that pass everything else.

Rescreened ~140 cached wallets with pre8 (no network): 2 pre-passed, then BOTH FAILED bar7 market checks:
- Ew4ueQQwA4p5sDf6PqwME54Th4trkQZqJZ2bsEzWqY2y: 16 closed, net +3.15, ex-best +0.56, med4 +4.3%, hold 11.0m, last 10:51Z, no snipes or same-tx; FAIL med entry mcap $48k, share>=300k 0.00, liq>=100k 0.00
- AFXfDhhwcZ3GU7hN4C2eFYPrJnAFtuYwV2Ma9d4njNz3: 24 closed, net +7.57, ex-best +2.11, med4 +2.7%, hold 4.5m, last 07:56Z, day 0.85 (peak 15-19 UTC); FAIL med entry mcap $174k, share>=300k 0.25, liq>=100k 0.00

### Near-pass list (new bar)
| wallet | failed check | by how much |
|---|---|---|
| Ew4ueQQwA4p5sDf6PqwME54Th4trkQZqJZ2bsEzWqY2y | mcap/liq | med entry mcap $48k (needs >=$300k); share>=300k 0.00 vs 0.7 |
| AFXfDhhwcZ3GU7hN4C2eFYPrJnAFtuYwV2Ma9d4njNz3 | mcap/liq | share>=300k 0.25 vs 0.7; liq share 0.00 |
| J1uTLDskxDsmTjxeD3zbCKRkoAsTJwEzSojrcspEp83s | ex-best | -10.34 SOL (25 closed, med4 +2.4%, hold 4.9m) |
| 8wvUi7jnhMKxCQKuhAKL5FtJKgpJrTBZxyEHb4jn8AaD | closed, ex-best | 9 closed (<15); ex-best -0.19 |
| 7yL1nP (see wg) | net | -20.5 SOL (med +6.0%, hold 23.2m) |
| BWRurF (see wg) | ex-best, median | -0.84 SOL; median -25.9% |
Farm cluster (0 closed trips; token plus 0.007 SOL dust, then tiny sells): 2ANtqM, 7Q1Qh3, DGnCnj, 7zr8Tk, 7Emom4, H36Kon, CBhGH3, F3BihW, DBiStm, CAXcfp, 2WMzev, A8PFSF
Other new-source fails: 62Nbnr -73 SOL, HRJohi -2.6, CiPMdA/CmZpMH/2p3gfA <15 closed and negative, 8KppDf -2.36, 819Xg8 -6.95
More fails (~12:00 UTC): 9rg9SQ -5.5; 2JXLpC -95.5; Bi2RqM 11 closed, ex-best -0.1; 5frx5s -15.5; 5F5ueQ -9.7 (median -0.6%); 35Kq84 -23.5; 72wwPT -12.9; 3CvPWx 8 closed; 9ycfhu no closed rounds.
Still running: pf10 (q10 top-20, about 11 left), pf9 (3 left). Prescreen them with: python3 an/pre8.py <wallets>, then an/bar7.py.

## 12:2x UTC: Zero's relaxed quick-flip rule (no mcap/liq gate; strict copy costs). Ew4ue and AFXf both FAIL
Model (an/qf.py, details in an/qf/<w6>.json): each buy leg priced at its 1-min candle HIGH and each sell leg at its LOW (GT OHLCV for the pool found in the wallet's own tx), 4% RT, plus constant-product impact of 0.09 SOL in and out (dx/R_sol, R_sol = pool token vault post-tx x spot).
- Ew4ue: 12/16 modelled; median copy -5.5%; win 0.50; 0.09-SOL equal-size net -0.048 SOL, ex-best -0.196; wallet-size net +5.83, ex-best -0.011; impact RT 0.16%; p10 mcap $19.7k; p10 liq $12.0k (median $25.9k). FAIL median and ex-best.
- AFXf: 22/24 modelled; median copy -10.4%; win 0.32; equal-size net -0.166, ex-best -0.216; wallet-size net +0.146, ex-best -2.085; impact RT 0.09%; p10 mcap $54.5k; p10 liq $20.4k. FAIL all three.
Filling unmodelled trades with wallet return minus 4% (optimistic) still fails: Ew4ue median -6.7%, AFXf -8.8%. The candle high/low costs about 25pp per trade versus the wallet's own fills.
Solscan: no label on either (SOL bal 7.43 / 3.31). Not in custodial_ignore.json. No copyfomo mapping in leader_mappings.json.

## True +5s model (qf.py run4, gap cap 30s, candle fallback rejected if >50% off leader fill) — 2026-10-24
- Ew4ue: 8/16 modelled; legs real 53 / fallback 28; 1 trade all-real. Median +2.73%, win 0.50, eq(0.09) net -0.0029, ex-best -0.0976. FAIL. Unmodelled filled at wallet-4%: med +1.55%, ex-best -0.082; at -10%: -1.45%, -0.120.
- AFXf: 22/24 modelled; legs real 16 / fallback 58; median -6.73%, win 0.36, eq net -0.080, ex-best -0.130. FAIL.
- Run3's Ew4ue "pass" (+23% med) was an artefact: "+5s" legs with 89-868s gaps and an SPCX-quoted pool (3HKKrX) priced as SOL.
- pf11 (q10) prescreen pre8: 19 wallets screened, all FAIL (neg net/median or holds >30m or <15 closed).

## Queue exhausted — 2026-10-24 ~13:10 UTC — 0 passes
- pf11 done (33/33 q10). pre8: 28 scored, all FAIL; 5 no closed rounds (A7scPb, 3ZSXHY, 7FDFjm, Gx2NYe, CQMPqD). No survivors -> nothing sent to bar7/qf.
- Closest misses: Ew4ue (qf true+5s: med +2.73%, eq ex-best -0.098), AFXf (med -6.73%), 2MT7y9 (ex-best +6.08 SOL but median -13.3%, hold 742m).
- roster_inbox.json unchanged ([]). No background fetchers running.

## FAST small-size trial bar (13:27-13:57 UTC 2026-10-24)
- PASS -> written: Ew4ue-flip (Ew4ueQQwA4p5sDf6PqwME54Th4trkQZqJZ2bsEzWqY2y), last swap 13:17Z, qf med +2.73%, hold 11.0m, 16 closed, eq ex-best -0.098, p10 mcap $32.3k, p10 liq $16.7k.
- J1uTLDsk: last swap 13:27Z, 25 closed, hold 4.9m, bar7 clean; qf not finished in budget (killed; cache kept). 8wvUi7jn: last swap 13:18Z (USDC pair, co-signed), 9 closed, hold 2.9m; qf not reached.
- H26ArD: last swap 10:26Z (>2h). 7yL1nP: last swap 08:32Z, net -20.5. Bi2RqM: hold 2389m. AFXf: qf med -6.73%.
- Ew4ue peers (GT trades on 4 shared pools): FHpcNS, AgmLJB, 7Js5gm all >800 tx/8d (truncated, bot-like) -> not covered.

## 13:56-14:35 UTC follow-up (low bar)
- J1uTLDsk qf true+5s: 22/25 modelled, legs real 39 / fb 49, med -7.01%, win 0.32, eq net -0.152, ex-best -0.264 -> FAIL.
- 8wvUi7jn: fee payer AgmLJB = Solscan "Fomo Co-signer" (Fomo app relayer, DFlow routing; 8wvU co-signs = user wallet, not bot). Not in custodial_ignore / leader_mappings. qf (USDC quote now converted via SOL/USD at block time): 7/9 modelled, med -7.35%, ex-best -0.047 -> FAIL (median).
- Fresh (GT trending 1h, 12 pools, 1921 traders -> 10 round-trippers): Eb3ZjJ >800 tx/8d, hold 1.0m, med -5.8% FAIL; GxDC9e >800 tx, no closed 7d rounds. Remaining 8 not fetched (≈8 min/wallet on public RPC). Stopped.
- roster_inbox.json unchanged since Ew4ue-flip.

## 14:23-14:35 UTC fresh candidates (8 remaining)
- First-page sig check (1000 sigs): 7 skipped for >800 tx in 8d (AyHuCe, 8ZdLGk, GLiCiN, kEFiAX, 9S65Ci, E6sa49, 23Dwx4 [959 in 8d]).
- 4AFjrC fetched (717 tx): 102 closed 7d, hold 12.9m, last swap 0.4h ago, but pre9 median -12.0% (proxy is lenient vs qf), net -6.57 -> FAIL, qf not run.
- Fresh path exhausted; 0 new passes. Inbox still 1 entry (Ew4ue-flip).
