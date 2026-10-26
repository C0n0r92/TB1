# Post-mortem: 25 Oct 2026, scalper (15m) + perp bot (1h), HL account 0x8bf4…c482

Built from HL `userFillsByTime`/`userFunding`/`portfolio` (the source of truth), plus each bot's trades.jsonl/fills.jsonl/bot.log, with 1m candles for MFE/MAE. Every round trip that closed on 25 Oct is included. All 6 perp trades were opened in the 24 Oct 20:44 "join" pass. One day is a **small sample**: 25 trades, 5 winners. Read everything below as hypotheses, not proof.

Definitions:
- Net = closedPnl − fees + funding.
- R = net ÷ the bot's planned risk_usd at entry. For LIT, risk is estimated from its backfilled record. BNB uses the resized 0.106 risk.
- MFE/MAE = the best and worst 1m high/low between entry and exit, × size ÷ risk.
- "1h pre-move in dir" = how far price had already moved in the trade's direction in the hour before entry (+ means chasing).

## Part A: manual close-out at ~20:22 UTC
- **Account:** flat, with 0 open orders (checked 20:23:41 and again ~20:24). No orphan cancels were needed.
- **Scalper:**
  - kPEPE was closed by the bot's own 6h time stop at 20:21:53, just before the user's closes.
  - BNB, UNI, LTC and AERO (user closes, no bot cloid, 20:22:38) were logged FLAT/closed at 20:22:56.
  - The recorded P&L matches HL to within $0.002 on every trade. state.json shows trades=[]. status shows last_error None, 19 closed, −6.318 vs HL −6.314.
  - No ADOPTED or ERROR lines afterwards. No restart was needed.
- **Perp bot:**
  - It had no positions when the user closed. Its last two (ETH, SOL) stopped out at 19:42, and they are on cooldown until 21:44.
  - status positions {}, equity 80.81 (HL agrees: 84.62 − 3.82).
  - Known record error: HYPE was logged at **+$0.005, but HL shows −$0.941** (the HYPE fill race, exit None).
- PUMP long, 19:55:24: closed with no bot cloid, so it was an external/manual close. The scalper handled it cleanly (FLAT −0.479).

## Totals
| | Trades | Wins | Gross $ | Fees $ | Funding $ | Net $ | ΣR |
|---|---|---|---|---|---|---|---|
| Scalper | 19 | 5 | −5.060 | 1.256 | +0.002 | **−6.314** | −11.0 |
| Perp bot | 6 | 0 | −3.612 | 0.295 | +0.090 | **−3.816** | −3.2 |
| **All** | 25 | 5 | −8.672 | 1.550 | +0.092 | **−10.131** | −14.2 |

HL's 24h pnlHistory is −10.19, which agrees.

**Equity:**
- Account was 84.62 at 24 Oct 20:04. It is 157.80 now, after the ~$83.25 USOL→USDC funding at 10:56.
- Scalper: base 83.25 → ≈76.94 (−7.6%).
- Perp bot: 84.62 → 80.81 (−4.5%).

**Scalper by trigger:**

| Trigger | Trades | Wins | Net $ | R |
|---|---|---|---|---|
| PULLBACK | 8 | 0 | −5.354 | −9.73 |
| VPROFILE | 5 | 1 | −1.789 | −2.89 |
| CORE | 5 | 3 | +0.486 | +0.69 |
| ABSORB | 1 | 1 | +0.343 | +0.91 |

**Scalper by rules version:**

| Version | Live | Trades | Wins | Net $ | R |
|---|---|---|---|---|---|
| S1: 5-strat vote, 0.4% min stop | 10:56–11:52 | 6 | 0 | −3.181 | −7.66 |
| S2: + exhaustion rules 4/5 | 11:52–12:16 | 2 | 0 | −1.940 | −2.42 |
| S3: trigger + confirmers, 0.8%/1 ATR stops, slip buffer | 12:16 onward | 11 | 5 | −1.193 | −0.94 |

Later changes under S3: reconcile fix at 16:06, PULLBACK dropped at 19:46, Hull 1h at 20:11. No trades opened under the last two.

**By side:**

| Bot | Side | Trades | Wins | Net $ |
|---|---|---|---|---|
| Scalper | Short | 11 | 2 | −5.397 |
| Scalper | Long | 8 | 3 | −0.917 |
| Perp bot | Short | 6 | 0 | −3.816 |

**By exit:**

| Bot | Exit | Trades | Net $ | R |
|---|---|---|---|---|
| Scalper | Stop loss | 11 | −7.581 | −13.15 |
| Scalper | TP1 then BE/trail stop | 2 | +1.291 | +2.17 |
| Scalper | Time stop | 1 | +0.192 | |
| Scalper | Manual/external | 5 | −0.216 | |
| Perp bot | signal_faded | 3 | −2.186 | |
| Perp bot | Stop | 3 | −1.630 | |

**Market:** BTC chopped between 80.24k and 80.90k (±0.4%). It fell from 04:00 to a low at 10:00 and rebounded to 80.79k by 16:00. ETH did the same. There was no clean trend for a trend-follower to hold.

