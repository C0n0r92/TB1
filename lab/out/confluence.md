# Confluence / clustering test (CL_) — phase 1, PAPER ONLY

_Generated 2026-10-24T00:50Z. Pre-registration: notes.md section '2026-10-24T00:10Z confluence (CL_) phase 1'. Code: cl_events.py, cl_fetch.py, cl_sim.py, cl_run.py, cl_report.py._

## Plain answer

**Nothing clears costs out of sample. No CL_ variant is a candidate.** The point-in-time-clean set (EB_PIT, N≥2/30m) has 76 trades at a mean of -0.133 per trade (CI entirely below 0). Its held-out part (n=32) averages -0.116. That is *worse* than its own controls: the first buyer's entry, single-wallet copies, the same token at a random time, and the same time on other tokens. N≥3 is worse again. Confluence here mostly means one sniper operator firing several keys within seconds, and the copier is its exit liquidity. Leader confluence can't be tested (1–2 events), SMART4 has 8 events (LOOKAHEAD), and every EB_ALL/LEAD/SMART4 row is LOOKAHEAD and can never become a candidate. All data covers about 1–2 days, so stability scores are capped.

## Lookahead status of each signal set

| set | wallets | status | why |
|---|---|---|---|
| LEAD | 4 copy leaders (_benjitrades, bystevenr, pointfarmcap, ExactTallTakin) + BtheBezel/cosby/zelda89 from trader_swaps.csv | **LOOKAHEAD** | picked from the fomo leaderboard over the same window as their swaps |
| SMART4 | Scout `smart` (4 radar_early_trader) | **LOOKAHEAD** | every recorded buy comes before date_added (10-23 20–21h) |
| EB_ALL | Scout `early_buyer` (187, 35 with buys) | **LOOKAHEAD** | wallets picked for being early in 100x runners; all buys counted |
| EB_PIT | same, point-in-time | **PIT** | a wallet counts only from its runner's peak_at + 1h (when 'early in a 100x' became knowable); runner mints excluded |

## Results at the pre-registered default exit

Default: entry = close of the minute containing (Nth buy + 10 s), else the next open within 10 min. SL −25% / TP +50% / 2 h time stop / 08:00 Dublin flat / 12 h cap. A drop to ≤0.2× counts as a rug, capped at −90%. Cost 4.7% round trip if entry mcap < $1M, else 2%. $5 stake, $100 equity. Holdout = signals after the 60th-percentile signal time (PIT: 10-23 19:29Z).

| test | events | trades (with candles) | mean/trade | 95% CI | win | OOS n / mean | score/25 | status | candidate |
|---|---|---|---|---|---|---|---|---|---|
| CL_LEAD_n2_w10 | 0 | 0 | — | — | — | — | — | LOOKAHEAD | no |
| CL_LEAD_n2_w30 | 1 | 1 | +0.453 | [—, —] | 100% | 0 / — | 12 (nights 1) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_LEAD_n2_w60 | 2 | 2 | +0.047 | [-0.36, +0.45] | 50% | 1 / -0.359 | 11 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_LEAD_n3_w10 | 0 | 0 | — | — | — | — | — | LOOKAHEAD | no |
| CL_LEAD_n3_w30 | 0 | 0 | — | — | — | — | — | LOOKAHEAD | no |
| CL_LEAD_n3_w60 | 0 | 0 | — | — | — | — | — | LOOKAHEAD | no |
| CL_EB_ALL_n2_w10 | 307 | 77 | -0.146 | [-0.25, -0.05] | 29% | 31 / -0.134 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_ALL_n2_w30 | 316 | 77 | -0.146 | [-0.25, -0.05] | 29% | 31 / -0.134 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_ALL_n2_w60 | 318 | 77 | -0.146 | [-0.25, -0.05] | 29% | 31 / -0.134 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_ALL_n3_w10 | 79 | 30 | -0.211 | [-0.36, -0.06] | 27% | 12 / -0.249 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_ALL_n3_w30 | 80 | 31 | -0.189 | [-0.34, -0.04] | 29% | 12 / -0.146 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_ALL_n3_w60 | 82 | 31 | -0.189 | [-0.34, -0.04] | 29% | 12 / -0.146 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_PIT_n2_w10 | 78 | 75 | -0.141 | [-0.24, -0.04] | 29% | 31 / -0.134 | 8 (nights 2) | PIT | no |
| CL_EB_PIT_n2_w30 | 79 | 76 | -0.133 | [-0.23, -0.04] | 30% | 32 / -0.116 | 8 (nights 2) | PIT | no |
| CL_EB_PIT_n2_w60 | 79 | 76 | -0.133 | [-0.23, -0.04] | 30% | 32 / -0.116 | 8 (nights 2) | PIT | no |
| CL_EB_PIT_n3_w10 | 14 | 12 | -0.210 | [-0.51, +0.11] | 42% | 5 / -0.128 | 9 (nights 2) | PIT | no |
| CL_EB_PIT_n3_w30 | 14 | 12 | -0.210 | [-0.51, +0.11] | 42% | 5 / -0.128 | 9 (nights 2) | PIT | no |
| CL_EB_PIT_n3_w60 | 14 | 12 | -0.210 | [-0.51, +0.11] | 42% | 5 / -0.128 | 9 (nights 2) | PIT | no |
| CL_SMART4_n2_w10 | 8 | 8 | -0.021 | [-0.30, +0.26] | 38% | 3 / -0.047 | 10 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_SMART4_n2_w30 | 8 | 8 | -0.021 | [-0.30, +0.26] | 38% | 3 / -0.047 | 10 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_SMART4_n2_w60 | 8 | 8 | -0.021 | [-0.30, +0.26] | 38% | 3 / -0.047 | 10 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_SMART4_n3_w10 | 2 | 2 | +0.078 | [-0.30, +0.45] | 50% | 1 / -0.297 | 12 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_SMART4_n3_w30 | 2 | 2 | +0.078 | [-0.30, +0.45] | 50% | 1 / -0.297 | 12 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_SMART4_n3_w60 | 2 | 2 | +0.078 | [-0.30, +0.45] | 50% | 1 / -0.297 | 12 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_PIT_n2_w30_firstbuyer | 79 | 76 | -0.103 | [-0.21, -0.00] | 34% | 32 / -0.033 | 8 (nights 2) | PIT | no |
| CL_EB_PIT_n3_w30_firstbuyer | 14 | 13 | -0.197 | [-0.48, +0.09] | 38% | 5 / -0.128 | 9 (nights 2) | PIT | no |
| CL_EB_ALL_n2_w30_firstbuyer | 316 | 77 | -0.119 | [-0.22, -0.02] | 32% | 31 / -0.010 | 8 (nights 2) | LOOKAHEAD | no (LOOKAHEAD) |
| CL_EB_PIT_single_noncluster | 281 | 59 | -0.100 | [-0.20, -0.00] | 24% | 18 / -0.135 | 9 (nights 2) | PIT | no |

Coverage (events → events with candles; EB_ALL/LEAD-only tokens are still being fetched at ≤5 req/min, so EB_ALL is a partial read): LEAD_n2_w30 1→1; LEAD_n2_w60 2→2; EB_ALL_n2_w10 307→79; EB_ALL_n2_w30 316→79; EB_ALL_n2_w60 318→79; EB_ALL_n3_w10 79→32; EB_ALL_n3_w30 80→33; EB_ALL_n3_w60 82→33; EB_PIT_n2_w10 78→77; EB_PIT_n2_w30 79→78; EB_PIT_n2_w60 79→78; EB_PIT_n3_w10 14→14; EB_PIT_n3_w30 14→14; EB_PIT_n3_w60 14→14; SMART4_n2_w10 8→8; SMART4_n2_w30 8→8; SMART4_n2_w60 8→8; SMART4_n3_w10 2→2; SMART4_n3_w30 2→2; SMART4_n3_w60 2→2

## Controls

| set | signal mean | first-buyer entry | same token, random time (±4h) | same time, other tokens |
|---|---|---|---|---|
| EB_PIT_n2_w30 | -0.133 (n=76) | -0.103 (n=76) | -0.096 (n=66) | -0.067 (n=77) |
| EB_PIT_n3_w30 | -0.210 (n=12) | -0.197 (n=13) | -0.039 (n=11) | -0.106 (n=14) |
| EB_ALL_n2_w30 | -0.146 (n=77) | -0.119 (n=77) | -0.096 (n=67) | -0.074 (n=78) |

Single-wallet copies on EB_PIT tokens with no 2-wallet cluster: n=59, mean -0.100, CI [-0.20, -0.00].

## Neighbour sweep (one parameter at a time around the default; PIT sets)

| variant | trades | mean | OOS n/mean | score | lucky flag |
|---|---|---|---|---|---|
| CL_EB_PIT_n2_w30__sl0.15 | 76 | -0.122 | 32/-0.108 | 8 | n/a |
| CL_EB_PIT_n2_w30__sl0.4 | 76 | -0.163 | 32/-0.175 | 8 | n/a |
| CL_EB_PIT_n2_w30__tp0.25 | 76 | -0.125 | 32/-0.144 | 8 | n/a |
| CL_EB_PIT_n2_w30__tp1.0 | 76 | -0.128 | 32/-0.184 | 8 | n/a |
| CL_EB_PIT_n2_w30__tp2.0 | 76 | -0.130 | 32/-0.174 | 8 | n/a |
| CL_EB_PIT_n2_w30__tp0 | 76 | -0.395 | 32/-0.309 | 8 | n/a |
| CL_EB_PIT_n2_w30__hold_m15 | 76 | -0.136 | 32/-0.114 | 8 | n/a |
| CL_EB_PIT_n2_w30__hold_m30 | 76 | -0.138 | 32/-0.115 | 8 | n/a |
| CL_EB_PIT_n2_w30__hold_m360 | 76 | -0.133 | 32/-0.116 | 8 | n/a |
| CL_EB_PIT_n2_w30__delay_s60 | 68 | -0.108 | 32/-0.145 | 9 | n/a |
| CL_EB_PIT_n2_w30__delay_s120 | 66 | -0.067 | 31/-0.105 | 9 | n/a |
| CL_EB_PIT_n2_w30__cost_pump0.033 | 76 | -0.119 | 32/-0.102 | 8 | n/a |
| CL_EB_PIT_n2_w30__cost_pump0.07 | 76 | -0.156 | 32/-0.138 | 8 | n/a |
| CL_EB_PIT_n2_w30__ladder0.15 | 76 | -0.119 | 32/-0.104 | 8 | n/a |
| CL_EB_PIT_n2_w30__ladder0.3 | 76 | -0.126 | 32/-0.092 | 8 | n/a |
| CL_EB_PIT_n3_w30__sl0.15 | 12 | -0.201 | 5/-0.106 | 9 | n/a |
| CL_EB_PIT_n3_w30__sl0.4 | 12 | -0.157 | 5/-0.154 | 9 | n/a |
| CL_EB_PIT_n3_w30__tp0.25 | 12 | -0.212 | 5/-0.228 | 9 | n/a |
| CL_EB_PIT_n3_w30__tp1.0 | 12 | -0.167 | 5/-0.225 | 8 | n/a |
| CL_EB_PIT_n3_w30__tp2.0 | 12 | -0.158 | 5/-0.025 | 8 | n/a |
| CL_EB_PIT_n3_w30__tp0 | 12 | -0.274 | 5/+0.280 | 9 | n/a |
| CL_EB_PIT_n3_w30__hold_m15 | 12 | -0.210 | 5/-0.128 | 9 | n/a |
| CL_EB_PIT_n3_w30__hold_m30 | 12 | -0.210 | 5/-0.128 | 9 | n/a |
| CL_EB_PIT_n3_w30__hold_m360 | 12 | -0.210 | 5/-0.128 | 9 | n/a |
| CL_EB_PIT_n3_w30__delay_s60 | 12 | -0.078 | 5/-0.285 | 9 | n/a |
| CL_EB_PIT_n3_w30__delay_s120 | 11 | +0.079 | 5/+0.084 | 15 | yes (EB_PIT_n3_w30@delay_s) |
| CL_EB_PIT_n3_w30__cost_pump0.033 | 12 | -0.196 | 5/-0.114 | 9 | n/a |
| CL_EB_PIT_n3_w30__cost_pump0.07 | 12 | -0.233 | 5/-0.151 | 8 | n/a |
| CL_EB_PIT_n3_w30__ladder0.15 | 12 | -0.243 | 5/-0.192 | 8 | n/a |
| CL_EB_PIT_n3_w30__ladder0.3 | 12 | -0.204 | 5/+0.126 | 10 | n/a |

## Why the PIT 'confluence' isn't independent smart money

- 79 EB_PIT N≥2/30m events, by day: {'10-23': 79}. Gap between 1st and Nth buy: median 2 s, 52/79 within 5 s.
- Only 9 distinct wallets appear; the top ones: q2z7i2…×41, 7K8JxX…×35, q2iQvv…×31, 9mQxmz…×27, ALM9ue…×8, FAKeL7…×7. Six of the nine were early in the same runner (ogkimchi, ranks 5–18, 1–2 s after launch), and two share the vanity prefix q2… That looks like one operator's sniper fleet firing together early on the bonding curve (median entry mcap ≈ $22k, all 4.7%-cost trades).
- So 'N wallets agree' here is really 'one bot fired on several keys'. Scout's NOTES say the same thing: do not use clusters as a buy signal.

## WHY THIS COULD FAIL / who is on the other side

- **Who's on the other side:** these wallets buy in the same second as the signal. A copier enters at least 10 s and one candle later, after the snipers' own buys have moved the price, so the copier is the exit liquidity for the sniper fleet and the migration bundlers.
- **Sample:** every PIT event is on 10-23 (about 2 Dublin nights). The N≥2 holdout (n=32) is later in that same day, not a new regime, and N≥3 has only 5 held-out trades. The one positive sweep cell (N≥3, delay 120 s: n=11, +0.079) is flagged as a single lucky number, because its neighbours at 10 s and 60 s are negative.
- **Selection:** the larger EB_ALL and LEAD sets were picked using the same window (LOOKAHEAD) and can never be candidates.
- **Execution:** fills are on 1-minute candle closes. The real slippage at same-second sniper entries is worse than the 4.7% assumed (the 7% sensitivity case is in the sweep).
- **Survivorship:** tokens with no GT candles (dead or rugged before indexing) drop out, which biases results upward.

## Multiple testing

variants_tried (global, data/variants_tried.json) = 424; CL_ configs this run = 54.
