# Self-copy summary (PAPER all roster leaders + LIVE rotation slots)

> **Paper rows are simulated** from live Jupiter quotes (read-only). **The LIVE section at the bottom is real money** in the dedicated bot wallet.

Updated 2026-10-26T10:07:18Z (Dublin 2026-10-26 10:07). Running since 2026-10-23T23:15:40Z. Leader swaps detected: 4108.

Rules: $5/trade, leader buy ≥ $50, mcap ≥ $100,000, first buys only, avoid.csv, max chase 15%, 3s delay, exits = LIVE v3 rules (SL −15% → breakeven after first TP; TP 25% at +40% and 25% at +100%, deferred while the leader adds; trail 25%/35% below peak after TP1; leader's first sell → keep 10% leftover that exits at +500% or its stop), flat by 08:00 Dublin; SESSION day-2026-10-24: entries until 2026-10-24T19:30:00Z, flat at 2026-10-24T20:00:00Z. Trades opened before 24 Oct 00:20 UTC used −25%/+100% until then. Costs (ours): Jupiter quote (route fees + impact) + 0.0005 SOL priority fee per tx.

| leader | conf. | trades (closed/open) | wins | losses | our net $ | our net % | copyfomo 2%/side $ | copyfomo % | copyfomo flat 5.3% $ |
|---|---|---|---|---|---|---|---|---|---|
| _benjitrades | low | 1 (1/0) | 1 | 0 | +1.83 | +36.6% | +1.71 | +34.1% | +1.72 |
| bystevenr | low | 2 (2/0) | 0 | 2 | -1.88 | -18.8% | -2.01 | -20.1% | -2.21 |
| pointfarmcap | medium-low | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| ExactTallTakin | medium | 1 (1/0) | 1 | 0 | +1.25 | +24.9% | +1.15 | +22.9% | +1.13 |
| neodot | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| ypnn-day | medium-low | 5 (5/0) | 2 | 3 | -0.22 | -0.9% | -0.52 | -2.1% | -0.83 |
| ew4ue-flip | low | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| zeropnl | medium | 6 (6/0) | 1 | 5 | -0.95 | -3.2% | -1.33 | -4.4% | -1.73 |
| Cented | medium | 3 (3/0) | 1 | 2 | +1.54 | +10.3% | +1.23 | +8.2% | +1.10 |
| decu | medium | 2 (2/0) | 0 | 2 | -2.16 | -21.6% | -2.23 | -22.3% | -2.44 |
| Schoen | medium | 2 (2/0) | 2 | 0 | +4.89 | +48.9% | +4.59 | +45.9% | +4.66 |
| West | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| Rilsio | medium | 3 (3/0) | 1 | 2 | -3.53 | -23.6% | -3.60 | -24.0% | -3.92 |
| KOREAN | medium | 14 (14/0) | 3 | 11 | -6.73 | -9.6% | -7.35 | -10.5% | -8.47 |
| Doji | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| bust | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| Mel | medium | 2 (2/0) | 0 | 2 | -1.55 | -15.5% | -1.60 | -16.0% | -1.78 |
| KingSolomon | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| gr3g | medium | 0 (0/0) | 0 | 0 | +0.00 | – | +0.00 | – | +0.00 |
| **total** | | 41 (41/0) | 12 | 29 | -7.54 | -3.7% | -9.96 | -4.9% | -12.78 |

Paper trades that would pass the new LIVE filters (mcap ≥$1M, liq ≥$100k, age ≥60 min, leader buy seen ≤2 min, chase ≤8%): 15 of 41, paper net +7.21 $.

Open positions are marked at the latest Jupiter SELL quote. Wins/losses count closed trades only.
copyfomo 2%/side = same quoted fills with a 2% fee on each side and no priority fee; flat 5.3% = same fills minus 5.3% of stake.

## Trades

| opened (UTC) | leader | mint | status | entry delay s | chase | impact | exits | our net $ | copyfomo $ | new live filters |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-24T09:44:46Z | ypnn-day | `HgBRWf…` | closed | 4.0 | -0.0043 | 0.0027 | leader_sold_16%_keep10 $4.54; close_session_end $0.51 | -0.10 | -0.15 | pass |
| 2026-10-24T10:26:31Z | ypnn-day | `2j5SaS…` | closed | 3.5 | 0.0073 | 0.0003 | leader_sold_25%_keep10 $4.64; close_session_end $0.58 | +0.07 | +0.01 | pass |
| 2026-10-24T10:29:43Z | ypnn-day | `9cRCn9…` | closed | 16.5 | -0.0007 | 0.0000 | leader_sold_100%_keep10 $4.60; close_session_end $0.54 | -0.01 | -0.06 | pass |
| 2026-10-24T10:29:49Z | ypnn-day | `98kfF7…` | closed | 4.0 | 0.0079 | 0.0051 | close_session_end $5.15 | +0.05 | -0.05 | pass |
| 2026-10-24T10:43:06Z | ypnn-day | `y1AZt4…` | closed | 8.8 | 0.0004 | 0.0041 | leader_sold_32%_keep10 $4.44; close_session_end $0.49 | -0.22 | -0.26 | pass |
| 2026-10-24T15:02:36Z | Mel | `9Bn4iA…` | closed | 17.0 | -0.0589 | 0.0187 | leader_sold_100%_keep10 $4.28; sl_-15% $0.41 | -0.47 | -0.50 | fail: age_lt_min |
| 2026-10-24T15:15:07Z | Mel | `58Yoqj…` | closed | 6.0 | -0.0313 | 0.0141 | leader_sold_100%_keep10 $3.65; sl_-15% $0.42 | -1.09 | -1.10 | fail: liq_lt_min,age_lt_min |
| 2026-10-24T15:19:20Z | Rilsio | `MsGDyb…` | closed | 6.6 | 0.0164 | 0.0060 | leader_sold_100%_keep10 $5.08; close_session_end $0.63 | +0.56 | +0.49 | pass |
| 2026-10-24T15:20:32Z | KOREAN | `3yEGBB…` | closed | 14.2 | 0.0606 | 0.0000 | leader_sold_100%_keep10 $4.02; sl_-15% $0.32 | -0.81 | -0.83 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T15:21:36Z | KOREAN | `HviocW…` | closed | 8.2 | -0.1339 | 0.0000 | leader_sold_25%_keep10 $3.65; sl_-15% $0.27 | -1.23 | -1.24 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T15:24:46Z | ExactTallTakin | `nxPqZ4…` | closed | 15.8 | 0.0092 | 0.0089 | tp_+40%_25% $1.79; close_session_end $4.61 | +1.25 | +1.15 | pass |
| 2026-10-24T15:25:46Z | KOREAN | `BqPUxG…` | closed | 8.2 | 0.0697 | 0.0000 | leader_sold_100%_keep10 $4.02; sl_-15% $0.32 | -0.81 | -0.83 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T15:27:02Z | bystevenr | `ABSZ6r…` | closed | 5.5 | 0.1137 | 0.0351 | sl_-15% $4.13 | -0.97 | -1.03 | pass |
| 2026-10-24T15:41:01Z | Schoen | `C1mBfB…` | closed | 7.1 | 0.0154 | 0.0089 | tp_+40%_25% $1.77; tp_+100%_25% $2.75; sl_trail_-25%_from_peak_3.07x $5.55 | +4.86 | +4.66 | pass |
| 2026-10-24T15:49:39Z | zeropnl | `pumpCm…` | closed | 16.7 | -0.0154 | 0.0000 | leader_sold_100%_keep10 $4.55; close_session_end $0.52 | -0.09 | -0.13 | pass |
| 2026-10-24T15:54:17Z | zeropnl | `DcpRE3…` | closed | 5.3 | 0.0454 | 0.0288 | leader_sold_5%_keep10 $3.72; sl_-15% $0.40 | -1.04 | -1.05 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T15:59:35Z | Rilsio | `8KCPxe…` | closed | 5.4 | 0.0285 | 0.0170 | sl_-15% $4.11 | -0.99 | -1.05 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T16:13:13Z | Cented | `CHeF6o…` | closed | 3.6 | 0.0752 | 0.0032 | sl_-15% $3.87 | -1.23 | -1.29 | pass |
| 2026-10-24T16:25:23Z | KOREAN | `CHqk5U…` | closed | 20.9 | -0.4821 | 0.0112 | leader_sold_100%_keep10 $4.95; tp_leftover_+500% $3.04 | +2.84 | +2.67 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T16:30:28Z | decu | `8Jp1L6…` | closed | 9.6 | -0.0351 | 0.0162 | sl_-15% $4.01 | -1.09 | -1.15 | fail: liq_lt_min |
| 2026-10-24T16:41:00Z | KOREAN | `33BkVW…` | closed | 26.0 | -0.0139 | 0.0000 | leader_sold_100%_keep10 $3.62; sl_-15% $0.33 | -1.20 | -1.21 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T16:42:14Z | KOREAN | `ARiph2…` | closed | 8.7 | -0.1546 | 0.0350 | leader_sold_100%_keep10 $4.52; sl_-15% $0.42 | -0.21 | -0.25 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T16:51:40Z | decu | `8aUNQv…` | closed | 21.7 | -0.0174 | 0.0213 | leader_sold_60%_keep10 $3.82; sl_-15% $0.26 | -1.07 | -1.08 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:09:48Z | zeropnl | `DJTu7v…` | closed | 3.4 | -0.0115 | 0.0042 | close_session_end $4.99 | -0.11 | -0.21 | pass |
| 2026-10-24T17:10:20Z | Cented | `2DKQk3…` | closed | 5.3 | 0.1256 | 0.0000 | sl_-15% $3.83 | -1.28 | -1.33 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:15:57Z | zeropnl | `F1FRUA…` | closed | 5.8 | 0.0357 | 0.0448 | leader_sold_100%_keep10 $5.81; sl_-15% $0.42 | +1.08 | +0.98 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:16:02Z | KOREAN | `F1FRUA…` | closed | 7.3 | -0.1184 | 0.0000 | sl_-15% $4.24 | -0.86 | -0.92 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:38:51Z | KOREAN | `FeqaDU…` | closed | 34.9 | 0.1061 | 0.0013 | sl_-15% $2.19 | -2.91 | -2.90 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:44:21Z | KOREAN | `1Z66SN…` | closed | 15.9 | -0.5889 | 0.0158 | tp_+40%_25% $1.97; tp_+100%_25% $3.07; sl_trail_-25%_from_peak_2.57x $4.28 | +4.13 | +3.96 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T17:48:32Z | Rilsio | `8KifAw…` | closed | 12.6 | 0.0669 | 0.0016 | leader_sold_100%_keep10 $1.84; sl_-15% $0.20 | -3.10 | -3.03 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T18:03:56Z | KOREAN | `4gXYvz…` | closed | 8.1 | 0.1582 | 0.0185 | leader_sold_100%_keep10 $3.34; sl_-15% $0.30 | -1.52 | -1.51 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T18:13:10Z | zeropnl | `FaQQnT…` | closed | 3.5 | -0.1431 | 0.0104 | close_session_end $4.84 | -0.26 | -0.35 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T18:18:38Z | bystevenr | `tybY2L…` | closed | 3.9 | 0.0566 | 0.0067 | sl_-15% $4.19 | -0.91 | -0.98 | pass |
| 2026-10-24T19:00:33Z | KOREAN | `HKqFck…` | closed | 16.0 | -0.2196 | 0.0111 | sl_-15% $3.71 | -1.39 | -1.44 | fail: mcap_lt_min,liq_lt_min,age_lt_min,leader_buy_gt_2m_old |
| 2026-10-24T19:15:45Z | Cented | `CW8ZQe…` | closed | 3.7 | 0.1824 | 0.0233 | tp_+40%_and_+100%_25%+25% $5.12; sl_trail_-25%_from_peak_2.26x $4.08 | +4.05 | +3.84 | pass |
| 2026-10-24T19:16:28Z | KOREAN | `9Bdqqb…` | closed | 6.4 | -0.0543 | 0.0213 | leader_sold_25%_keep10 $3.69; sl_-15% $0.27 | -1.19 | -1.19 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T19:25:30Z | KOREAN | `Gk3mT9…` | closed | 6.1 | -0.0691 | 0.0129 | sl_-15% $3.07 | -2.03 | -2.05 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T19:27:44Z | zeropnl | `6GSXT4…` | closed | 5.4 | 0.0349 | 0.0000 | leader_sold_5%_keep10 $4.22; sl_-15% $0.40 | -0.54 | -0.57 | fail: mcap_lt_min,liq_lt_min,age_lt_min |
| 2026-10-24T19:28:29Z | Schoen | `HbXn9L…` | closed | 6.4 | 0.0541 | 0.0202 | close_session_end $5.13 | +0.03 | -0.07 | pass |
| 2026-10-24T19:29:54Z | KOREAN | `Cocu41…` | closed | 8.6 | -0.242 | 0.0308 | leader_sold_25%_keep10 $5.29; sl_-15% $0.32 | +0.46 | +0.39 | fail: mcap_lt_min,liq_lt_min,age_lt_min |

## Skipped leader buys (by reason)

- _benjitrades: not_first_buy 33
- bystevenr: chase_gt_15pct 4, mcap_lt_100k 1, no_entry_before_session_end 1, no_jupiter_route 7, not_first_buy 40, session_ended 6, topup_already_entered_this_session 1
- ExactTallTakin: not_first_buy 8, session_ended 3
- neodot: mcap_lt_100k 2, session_ended 1
- ypnn-day: avoid_mint 4, not_first_buy 367
- West: chase_gt_15pct 1, leader_buy_lt_min 20, not_first_buy 130, session_ended 33, topup_v2_fail 2
- KOREAN: chase_gt_15pct 6, leader_buy_lt_min 9, mcap_lt_100k 14, no_entry_before_session_end 6, not_first_buy 93, session_ended 96, topup_already_open_same_mint 5, topup_v2_fail 5
- Mel: leader_buy_lt_min 6, mcap_lt_100k 5, not_first_buy 16, session_ended 10, topup_already_open_same_mint 2
- Cented: chase_gt_15pct 5, mcap_lt_100k 12, mcap_unknown 1, not_first_buy 119, session_ended 13, topup_already_entered_this_session 1, topup_already_open_same_mint 3, topup_v2_fail 8
- Rilsio: chase_gt_15pct 1, leader_buy_lt_min 3, not_first_buy 53, session_ended 14, topup_v2_fail 1
- zeropnl: chase_gt_15pct 3, leader_buy_lt_min 2, mcap_lt_100k 20, no_entry_before_session_end 1, not_first_buy 17, session_ended 58
- decu: chase_gt_15pct 1, leader_buy_lt_min 5, not_first_buy 32, session_ended 5, topup_v2_fail 1
- KingSolomon: chase_gt_15pct 2, mcap_lt_100k 3, no_jupiter_route 1, session_ended 20
- Schoen: not_first_buy 10, session_ended 13
- Doji: leader_buy_lt_min 12, not_first_buy 237, session_ended 81
- bust: not_first_buy 78, session_ended 95, too_close_to_0800 7
- ew4ue-flip: not_first_buy 27, session_ended 12
- gr3g: not_first_buy 4, session_ended 6

## Endpoint calls

- dexscreener: ok 147
- jupiter: err_URLError 1, http_400 8, http_429 1602, ok 8896
- rpc:mainnet-beta: err_TimeoutError 15, err_URLError 4, http_413 56, http_429 2717, ok 76202
- rpc:publicnode: err_RemoteDisconnected 4, err_TimeoutError 12, err_URLError 11, http_403 1547, http_429 22, null_tx 249, ok 122448
- rugcheck: ok 89

## Leader roster and LIVE rotation

Mode **default**. LIVE slots (0/3): **none**. Last rank 2026-10-26T10:00 UTC.

Score = EV per trade after costs (mean paper net % of stake; Jupiter quotes + fees) over the last 72h of paper trades that pass the v2 live filters, open trades marked to market. Eligible: ≥4 qualifying trades and score > 0.

| rank | leader | source | qualifying trades (open) | EV/trade | EV $/trade | win rate | max DD $ | net $ | top-3 streak | last buy/sell seen | LIVE | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| – | ypnn-day | scout active-now.md near-miss (35 trades | 5 (0) | -0.9% | -0.04 | 40% | 0.22 | -0.22 | 0 | 27 min ago |  | score ≤ 0 |
| – | Cented | kolscan daily leaderboard 24 Oct (positi | 2 (0) | +28.2% | +1.41 | 50% | 1.23 | +2.82 | 0 | 386 min ago |  | needs ≥4 trades |
| – | Schoen | kolscan daily leaderboard 24 Oct (positi | 2 (0) | +48.9% | +2.44 | 100% | 0.00 | +4.89 | 0 | 385 min ago |  | needs ≥4 trades |
| – | bystevenr | onchain-intel leader_mappings.json (seed | 2 (0) | -18.8% | -0.94 | 0% | 1.88 | -1.88 | 0 | 362 min ago |  | needs ≥4 trades |
| – | zeropnl | kolscan daily leaderboard 24 Oct (positi | 2 (0) | -2.0% | -0.10 | 0% | 0.20 | -0.20 | 0 | 857 min ago |  | needs ≥4 trades |
| – | ExactTallTakin | onchain-intel leader_mappings.json (seed | 1 (0) | +24.9% | +1.25 | 100% | 0.00 | +1.25 | 0 | 294 min ago |  | needs ≥4 trades |
| – | Rilsio | kolscan daily leaderboard 24 Oct (positi | 1 (0) | +11.2% | +0.56 | 100% | 0.00 | +0.56 | 0 | 596 min ago |  | needs ≥4 trades |
| – | Doji | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 17 min ago |  | needs ≥4 trades |
| – | KOREAN | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 608 min ago |  | needs ≥4 trades |
| – | KingSolomon | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 520 min ago |  | needs ≥4 trades |
| – | Mel | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 684 min ago |  | needs ≥4 trades |
| – | West | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 1167 min ago |  | needs ≥4 trades |
| – | _benjitrades | onchain-intel leader_mappings.json (seed | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 962 min ago |  | needs ≥4 trades |
| – | bust | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 25 min ago |  | needs ≥4 trades |
| – | decu | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 613 min ago |  | needs ≥4 trades |
| – | ew4ue-flip | Scout quick-flip screen 2026-10-24 (near | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 32 min ago |  | needs ≥4 trades |
| – | gr3g | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 557 min ago |  | needs ≥4 trades |
| – | neodot | scout copy-candidates.md (Pulse lead, Sc | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 2175 min ago |  | needs ≥4 trades |
| – | pointfarmcap | onchain-intel leader_mappings.json (seed | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | none |  | needs ≥4 trades |

Full table and rotation log: roster-status.md

## LIVE (bot wallet, real fills)

Mode: **ON** (file `LIVE`). Wallet `9bp5LMtn5nmpNLJNAoLnXHPgmmsNKqjehco77W6xXXgX`. SOL 0.0; USDC 0.0; state needs_gas_sol; USDC→SOL conversions 0; value ≈ 0.0 SOL ($0.00) at 2026-10-26T10:06:42Z.
Caps (hard): size min($10, 15% wallet), keep 0.02 SOL, ≤3 open, chase ≤8%, impact ≤3%, leader ≥$50 and seen ≤2 min after it, mcap ≥$1M, liquidity ≥$100k, token/pool age ≥60 min, exits v3: SL −15% → breakeven after first TP, TP 25% at +40% and 25% at +100% (deferred while the leader adds), trail 25% below peak after TP1 (35% while adding); leader's first sell → sell all but 10% of original, leftover exits at +500% or its stop, no entries 07:45–08:00, flat by 08:00 Dublin, night loss limit −20%. SESSION day-2026-10-24: 2026-10-24 08:31Z → 2026-10-24 20:00Z, no entries from 2026-10-24 19:30Z, flat at 2026-10-24 20:00Z, −20% halt from the balance at session start; after the end no entries until session.json is removed. Priority fee 0.0001 SOL. Halted nights: none.

| opened | mint | status | SOL in | SOL out | net SOL | net $ (in/out at fill-time SOL px) | open mark $ | buy sig |
|---|---|---|---|---|---|---|---|---|
| – | no live trades yet | | | | | | | |
