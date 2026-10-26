# Roster status (PAPER scoring → LIVE slots)

Updated 2026-10-26T10:04:40Z (Dublin 2026-10-26 10:04). Roster: 19 wallets (max 20), from roster.json (Zero) + roster_inbox.json (Scout, merged every minute; when full the idlest low-confidence wallet is dropped).

**LIVE now:** none (no live leader: _benjitrades is inactive (no buy/sell seen in 60 min) or in loss cooldown, and no eligible leader is active).

Daytime session fill (off): while session.json is open for entries, up to 3 LIVE slots (Chunk's own ≤3 open positions stays the risk cap; this bot's own live wallet stays at 3 slots); an empty LIVE slot goes to a roster wallet with confidence medium or better that had a buy/sell seen in the last 60 min and no clearly negative record (≥2 trades with negative EV/net), most recently active first, then score; the ≥4-trade rule and 2-rank hysteresis are skipped for it (hysteresis is 1 rank for everyone). session.json manual_live (none) is user-approved: it may take a slot regardless of confidence and the paper 'clearly negative' rule does not apply to it; it is judged only by REAL copies (2 losses in a row, last 4 net < 0, fast −15% stop) and the 60-min idle demotion. An idle-demoted wallet regains a free slot within a minute of its next buy/sell. 60-min idle demotion, 2-loss demotion and all exits are unchanged.

Rules: up to 3 LIVE leaders outside a daytime session. Promote: eligible and in the top 3 for 2 consecutive hourly ranks (fills a free slot, or replaces a live leader that fell out of the top 3). Demote: score ≤ 0, fewer than 4 qualifying trades, removed from roster, or 2 live losses in a row (then 24h cooldown). Inactivity (checked every minute): a live leader with no buy/sell seen in 60 min loses its slot (no cooldown) and it goes straight to the best eligible leader that traded in the last 30 min (hysteresis skipped), else the slot stays empty; the default _benjitrades slot holds only while he is active. Demotion only stops new entries; open live positions keep their exits and still mirror the leader's sells. All live caps are unchanged (size min($10, 15%), ≤3 open live positions in total, night −20% limit, 07:45/08:00, every filter).

Session prune rules (on top of the 2-losses-in-a-row demotion, while the daytime session is open): (a) a LIVE leader whose last 4 closed copies (Chunk / live / paper, deduped) net below 0 after costs is demoted; (b) a leader whose last copy hit the −15% stop within 15 min of entry is demoted (or kept out if not live). Both: 12h cooldown. Every prune is in prune-log.jsonl.

## Prune log (newest first)

- none yet

## Ranking

Mode **default**. LIVE slots (0/3): **none**. Last rank 2026-10-26T10:00 UTC.

Score = EV per trade after costs (mean paper net % of stake; Jupiter quotes + fees) over the last 72h of paper trades that pass the v2 live filters, open trades marked to market. Eligible: ≥4 qualifying trades and score > 0.

| rank | leader | source | qualifying trades (open) | EV/trade | EV $/trade | win rate | max DD $ | net $ | top-3 streak | last buy/sell seen | LIVE | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| – | ypnn-day | scout active-now.md near-miss (35 trades | 5 (0) | -0.9% | -0.04 | 40% | 0.22 | -0.22 | 0 | 36 min ago |  | score ≤ 0 |
| – | Cented | kolscan daily leaderboard 24 Oct (positi | 2 (0) | +28.2% | +1.41 | 50% | 1.23 | +2.82 | 0 | 384 min ago |  | needs ≥4 trades |
| – | Schoen | kolscan daily leaderboard 24 Oct (positi | 2 (0) | +48.9% | +2.44 | 100% | 0.00 | +4.89 | 0 | 382 min ago |  | needs ≥4 trades |
| – | bystevenr | onchain-intel leader_mappings.json (seed | 2 (0) | -18.8% | -0.94 | 0% | 1.88 | -1.88 | 0 | 360 min ago |  | needs ≥4 trades |
| – | zeropnl | kolscan daily leaderboard 24 Oct (positi | 2 (0) | -2.0% | -0.10 | 0% | 0.20 | -0.20 | 0 | 855 min ago |  | needs ≥4 trades |
| – | ExactTallTakin | onchain-intel leader_mappings.json (seed | 1 (0) | +24.9% | +1.25 | 100% | 0.00 | +1.25 | 0 | 291 min ago |  | needs ≥4 trades |
| – | Rilsio | kolscan daily leaderboard 24 Oct (positi | 1 (0) | +11.2% | +0.56 | 100% | 0.00 | +0.56 | 0 | 594 min ago |  | needs ≥4 trades |
| – | Doji | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 50 min ago |  | needs ≥4 trades |
| – | KOREAN | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 605 min ago |  | needs ≥4 trades |
| – | KingSolomon | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 517 min ago |  | needs ≥4 trades |
| – | Mel | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 682 min ago |  | needs ≥4 trades |
| – | West | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 1165 min ago |  | needs ≥4 trades |
| – | _benjitrades | onchain-intel leader_mappings.json (seed | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 959 min ago |  | needs ≥4 trades |
| – | bust | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 35 min ago |  | needs ≥4 trades |
| – | decu | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 610 min ago |  | needs ≥4 trades |
| – | ew4ue-flip | Scout quick-flip screen 2026-10-24 (near | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 52 min ago |  | needs ≥4 trades |
| – | gr3g | kolscan daily leaderboard 24 Oct (positi | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 554 min ago |  | needs ≥4 trades |
| – | neodot | scout copy-candidates.md (Pulse lead, Sc | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | 2172 min ago |  | needs ≥4 trades |
| – | pointfarmcap | onchain-intel leader_mappings.json (seed | 0 (0) | – | – | – | 0.00 | +0.00 | 0 | none |  | needs ≥4 trades |

## Rotation log (newest first)

- 2026-10-25T19:06:03Z **slot_empty** _benjitrades: no eligible leader traded in the last 30 min; slot left empty
- 2026-10-25T19:06:03Z **demoted** _benjitrades: inactive: no buy/sell seen in 60 min (last 2026-10-25T18:05:08Z)
- 2026-10-25T18:05:28Z **default_live** _benjitrades: no leader qualifies yet; default leader keeps the slot
- 2026-10-25T16:24:17Z **slot_empty** _benjitrades: no eligible leader traded in the last 30 min; slot left empty
- 2026-10-25T16:24:17Z **demoted** _benjitrades: inactive: no buy/sell seen in 60 min (last 2026-10-25T15:16:26Z)
- 2026-10-25T15:16:25Z **default_live** _benjitrades: no leader qualifies yet; default leader keeps the slot
- 2026-10-25T00:58:38Z **slot_empty** _benjitrades: no eligible leader traded in the last 30 min; slot left empty
- 2026-10-25T00:58:38Z **demoted** _benjitrades: inactive: no buy/sell seen in 60 min (last 2026-10-24T23:33:33Z)
- 2026-10-24T23:57:50Z **default_live** _benjitrades: no leader qualifies yet; default leader keeps the slot
- 2026-10-24T21:05:42Z **slot_empty** _benjitrades: no eligible leader traded in the last 30 min; slot left empty
- 2026-10-24T21:05:42Z **demoted** _benjitrades: inactive: no buy/sell seen in 60 min (last 2026-10-24T20:04:59Z)
- 2026-10-24T20:00:45Z **default_live** _benjitrades: no leader qualifies yet; default leader keeps the slot
- 2026-10-24T20:00:45Z **demoted** ypnn-day: score <= 0
- 2026-10-24T19:30:13Z **demoted** Doji: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** Mel: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** West: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** ew4ue-flip: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** ExactTallTakin: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** Schoen: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** KingSolomon: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** gr3g: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** Rilsio: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** decu: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** Cented: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** zeropnl: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** bystevenr: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:30:13Z **demoted** KOREAN: daytime session closed for entries: session-fill slot ends
- 2026-10-24T19:00:38Z **promoted** Doji: session fill (manual_live, this session only): medium confidence, active (last buy/sell ?), record not negative (0 qualifying, 0 paper trades, net $+0.00); empty slot
- 2026-10-24T19:00:38Z **promoted** Mel: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T15:17:32Z), record not negative (0 qualifying, 2 paper trades, net $-1.55); empty slot
- 2026-10-24T19:00:38Z **promoted** West: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T15:20:07Z), record not negative (0 qualifying, 0 paper trades, net $+0.00); empty slot
- 2026-10-24T19:00:38Z **promoted** ew4ue-flip: session fill (manual_live, this session only): low confidence, active (last buy/sell 2026-10-24T15:24:03Z), record not negative (0 qualifying, 0 paper trades, net $+0.00); empty slot
- 2026-10-24T19:00:38Z **promoted** ExactTallTakin: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T15:25:28Z), record not negative (1 qualifying, 1 paper trades, net $+1.26); empty slot
- 2026-10-24T19:00:38Z **promoted** Schoen: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T15:40:44Z), record not negative (1 qualifying, 1 paper trades, net $+4.86); empty slot
- 2026-10-24T19:00:38Z **promoted** KingSolomon: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T17:16:28Z), record not negative (0 qualifying, 0 paper trades, net $+0.00); empty slot
- 2026-10-24T19:00:38Z **promoted** gr3g: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T18:29:36Z), record not negative (0 qualifying, 0 paper trades, net $+0.00); empty slot
- 2026-10-24T19:00:38Z **promoted** Rilsio: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T18:31:11Z), record not negative (1 qualifying, 3 paper trades, net $-3.40); empty slot
- 2026-10-24T19:00:38Z **promoted** decu: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T18:31:18Z), record not negative (0 qualifying, 2 paper trades, net $-2.16); empty slot
- 2026-10-24T19:00:38Z **promoted** Cented: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T18:33:49Z), record not negative (1 qualifying, 2 paper trades, net $-2.51); empty slot
- 2026-10-24T19:00:38Z **promoted** zeropnl: session fill (manual_live, this session only): medium confidence, active (last buy/sell 2026-10-24T18:58:18Z), record not negative (2 qualifying, 5 paper trades, net $-0.25); empty slot
- 2026-10-24T19:00:38Z **promoted** bystevenr: session fill (manual_live, this session only): low confidence, active (last buy/sell 2026-10-24T18:58:24Z), record not negative (2 qualifying, 2 paper trades, net $-1.88); empty slot
