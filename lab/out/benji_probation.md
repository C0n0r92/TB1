# _benjitrades probation tracker (2026-10-24T15:25Z, PAPER/READ-ONLY, proposals only)

Probation began 2026-10-23T22:29Z at $6.00 fixed (Copycat log; Zero's decision). Source: /workspace/copyfomo/x-watch-log.md. Copies before that are shown as reference only.
Real P&L = the bot's own number (fees and gas included). 'Before drag' adds back the ~5% round-trip cost (2x2% bot fee + ~0.7% pool/route + gas) to show what the leader-level result was.

Simulator expectation per copy (central model, 27 historical copies, 10 s delay): mean -5% = $-0.29 at $6; median -27% = $-1.64; win rate 22%; 56% end at the -25% stop or worse. The mean is carried by a few big winners: most copies are expected to lose.

| # | token | copy time UTC | leader buy | leader mcap | stake | real P&L $ | real % | before drag % | sim expectation $ (mean / median) | running real $ (probation) | counted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TRUTH | 2026-10-23T20:42Z | $259.18 | $442k | $9.40 | -2.81 | -29.9% | -24.9% | -0.46 / -2.57 (path sim of this coin: -30.5% = -2.87) | +0.00 | no (pre-probation) |
| 2 | Moustache | ? | - | - | $9.40 | OPEN | - | - | -0.46 / -2.57 | +0.00 | no (pre-probation) |

**Probation so far: 0 closed copies, real net $+0.00** (simulator mean would be $-0.00; before the 5% drag $+0.00).

Rule status: **CONTINUE** (proposal; Zero decides).

## Proposed exit rule

1. **Loss budget:** stop as soon as the probation's real net reaches **$-12** (13% of the $91 balance, about 7 straight stop-outs at $6).
2. **Checkpoint at 15 closed copies:** keep only if real net is >= $0 AND at least one copy made >= +90% (a TP hit). Otherwise stop.
3. **Execution check (any time):** if 3 copies fill more than 5% worse than the simulator on the same coin (chase or stop slippage), stop. The edge is too thin to absorb more cost.
4. **Cap:** no stake increase during probation, whatever the P&L.

Why: the simulated edge (+14% mean, -24% median) comes from about 3 lottery coins in 29. A P&L test over 15 copies can barely tell a real edge from none. Bootstrap of the simulated copies at $6: if the simulator is right, the rule stops on budget 41% of the time and passes 45%. With zero edge it stops 50% and passes 35%; with a -5% edge it stops 54% and passes 30%. So this is mainly a **cost cap**: it limits the probation to about $12 and requires the thing the strategy depends on (a big winner) to show up live. Benji averages about 1 copyable first buy per day, so 15 copies is about 2-3 weeks.

## Lines naming _benjitrades not parsed (check by hand)

- 2026-10-23T23:34Z | read-only check for Lab: /portfolio available $84.88, positions value $5.98, invested $15.40, open positions 1 (Moustache $5.98, -0.3%, copied from _benjitrades; leader cards: bought $2.0k at mcap $46
- 2026-10-23T23:37Z | handover check: 1 open (Moustache $5.98 then $8.34, +39%) so _benjitrades NOT stopped. Withdraw = menu > withdraw > cash $84.88 as USDC on chosen chain (solana offered) > paste address. No fee/min sho
- 2026-10-23T23:53Z | ROSTER (Zero, at user request): keep _benjitrades $6; ADD ExactTallTakin + pointfarmcap at $5 each (pending, after TP change). Rotation: stop for the night after 2 losses in a row or night realized < 
- - 2026-10-24 00:08 UTC: read from the copyfomo chat already on screen (a /portfolio reply at bot time 20:07 = 00:07 UTC; no new browser task started). Available $93.11, realized -$0.59, open positions 0 (stale 'invested 
- - 2026-10-24 00:31 UTC: /portfolio available $93.11, realized -$0.59, 0 open (stale 'invested $15.40'). Night start $94.02, -1.0%, well above limit $75.22 and $30 pause. No copy buys/sells/skips since 00:20Z, so no chase
- 2026-10-24T08:28Z | telegram: ok | balance $93.11 | open positions: 0 | runs 02:30-07:45Z failed (usage ran out). Skips: 05:52Z ExactTallTakin Dacity (not first buy), 06:50Z _benjitrades CONDUCTOR (mcap $83.8k < $100k). 
- 2026-10-24T12:52Z | SELL (copy stop loss, automatic): _benjitrades CC (bnb) bought $12.00 at mcap $326.9k at 12:51Z, stop loss hit 12:52Z, sold all @ $0.00024, pnl -$3.19 (-26.6%, overshot the -15% stop in a fast drop). 
- - Chase log: _benjitrades | VELK (veilinkzk, solana; CA unconfirmed, X replies cite BzoYWZL3fXC5KkzkA6dEh9pBKcv9NAqwkTxJReNxpump) | bought 13:32Z | leader entry $101.42 at mcap $73.7k | ours $12.00, mcap not shown | diff
- 2026-10-24T14:35Z | day | APPLIED: active BtheBezel, bystevenr, JamJam0407, pointfarmcap, zelda89 at $6; min trader $10, mcap $20k, chase 25%, all buys, TP +20% all, SL -15%. Past: _benjitrades, 000000, ExactTallTakin. $
- - 2026-10-24 14:40 UTC (day): /portfolio available $89.09, realized -$4.45, 0 open (invested $39.40 stale). Start $93.11, -4.3%, above the $83.80 limit. /copies (10:34 bot): BtheBezel, bystevenr, JamJam0407, pointfarmcap
- - 2026-10-24 15:05 UTC (day): /portfolio available $89.09, realized -$4.45, 0 open (invested $39.40 stale). Start $93.11, -4.3%, above the $83.80 limit. /copies (11:05 bot): BtheBezel, bystevenr, JamJam0407, pointfarmcap
