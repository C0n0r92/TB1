# MONITOR.md: runbook for Copycat (self-copy bot)

Copycat runs the self-copy system and reports on it. Rules:
- **Never** open, read, copy or print `/home/box/.selfcopy-wallet/` (the bot key).
- **Never** send, withdraw or transfer funds.
- **Never** edit the `HARD` caps in `live.py`.
- Copycat may read everything else here and may run `stop.sh` and `start.sh`.

Current LIVE caps (v2, 23 Oct): leaders holding a rotation slot only (max 3; default _benjitrades, see roster-status.md); size min($10, 15% of wallet); priority fee 0.0001 SOL; mcap ≥$1M, liquidity ≥$100k, token age ≥60 min, leader buy seen ≤2 min, chase ≤8%, impact ≤3%; exits v3 since 24 Oct (paper uses the same): SL −15% before the first TP, then breakeven (entry + costs) after it, never skipped; TP sells 25% at +40% and another 25% at +100% (both at once on a jump past +100%), deferred while the leader bought the same token in the last 10 min and fired on the next check once 10 min pass with no new add if still above the level; after TP1 the rest trails 25% below the peak since entry (35% while the leader adds); on the leader's FIRST sell, sell all but 10% of the original size (keep all if <10% left), and that leftover ignores later leader sells and the trail, sells all at +500%, keeps the −15%/breakeven stop, and is still sold at 08:00 and by the night loss limit (sell reasons `sl_-15%`, `sl_breakeven`, `tp_+40%_25%`, `tp_+100%_25%`, `sl_trail_-25%/-35%_from_peak_…`, `leader_sold_N%_keep10`, `tp_leftover_+500%`; events `tp_deferred`, `leader_add`, `leader_sell_ignored_leftover`); ≤3 open; flat by 08:00 Dublin; night loss limit −20%. When reporting, also compare paper trades tagged `v2_pass` vs the rest (summary.md last column).

Location: `/workspace/selfcopy`. Wallet (public only): `9bp5LMtn5nmpNLJNAoLnXHPgmmsNKqjehco77W6xXXgX`, viewable at https://solscan.io/account/9bp5LMtn5nmpNLJNAoLnXHPgmmsNKqjehco77W6xXXgX

## What it does
- **Paper:** copies 4 leaders on paper, all simulated.
- **Live:** real money, while the file `LIVE` exists, for the leaders holding a LIVE slot (max 3) in `roster-status.md`. Default is `_benjitrades` until another leader qualifies.
- **Roster rotation:** every hour, leaders are scored on 72h of v2-qualifying paper trades (EV per trade after costs, ≥4 trades, score > 0). A leader needs 2 consecutive hourly top-3 ranks for a slot. It loses the slot if its score drops to ≤ 0, it has fewer than 4 trades, or it takes 2 live losses in a row (24h cooldown). Every minute, a live leader with no buy/sell seen in 60 min loses its slot to the best eligible leader active in the last 30 min (hysteresis skipped), or the slot stays empty; _benjitrades is the default only while active. Copycat does **not** edit `roster.json`; Zero adds wallets from Scout's copy-candidates.md.
- **Funding:** the wallet arrives as about $85 USDC plus about 0.03 SOL gas. Once SOL ≥ 0.01 and USDC ≥ $5, the bot swaps USDC→SOL once via Jupiter, keeping about $1 USDC, and then buys in SOL.

## Health checks (all read-only; run every ~10 min)
```bash
cd /workspace/selfcopy
pgrep -af "run_loop.sh|selfcopy.py run"          # expect exactly 1 run_loop.sh + 1 python worker
ls LIVE STOP 2>/dev/null                          # expect LIVE present, STOP absent
head -3 summary.md | tail -1                      # "Updated ..." should be < 2 min old
python3 -c "import json;s=json.load(open('state.json'))['live'];print(s.get('wallet'));print([ (p['mint'][:8],p['status']) for p in s['positions'] if p['status']=='open'])"
tail -n 20 live-trades.jsonl                      # live events
grep -c '"event": "error"' run.log                # should not climb quickly
```
`state.json` → `live.wallet.state` is `ok` or `needs_gas_sol`. The wallet snapshot refreshes about every 60s.

## What's normal (no action)
- `unfunded` or `needs gas SOL` events before the user funds the wallet. Live stays idle, which is correct.
- `usdc_to_sol` once after funding, with about $84 in and about 0.8 SOL out. After that USDC stays around $1.
- Skips: `not_first_buy` is very common, since benji adds to existing bags; also `mcap_lt_1m`, `liq_lt_100k`, `age_lt_60m`, `leader_buy_gt_2m_old`, `chase_gt_8pct`, `impact_gt_3pct`, `max_open_3`, `no_entry_0745_0800`.
- `http_429` counts in the summary's endpoint stats. Free endpoints rate-limit and the bot backs off.
- The worker restarting after a crash: `run.log` shows "exited (rc), restarting in 10s". An occasional restart is fine.
- Paper positions for all 4 leaders. Live has at most 3 open positions. Everything is sold from 08:00 Dublin onwards.

## Act on these
| sign | action |
|---|---|
| no python worker, or summary `Updated` > 5 min old | `./start.sh --live`. If it dies again, read the tail of `run.log` and report it |
| `sell_failed` with attempt 3 on an `sl_`/`close_`/`loss_limit` exit, or a live position still open after 08:10 Dublin | report urgently (token may be illiquid or rugged); bot keeps retrying every 30s during the 08:00 hour |
| `night_loss_limit` | report to the user (all sold, no buys until 08:00 Dublin; this is by design) |
| `entry_failed` or `usdc_convert_failed` repeating | report with the `err` field (USDC retries every 10 min) |
| any `tx guard:` text or `close_acct_blocked` | report; the bot refused to sign an unexpected transaction (good), but find out why |
| `"event": "error"` repeating every loop | report the traceback (`tb`) |
| `needs gas SOL` while USDC > $5 | tell the user the wallet needs about 0.03 SOL for gas |
| "keypair file permissions too open" in run.log | report; do NOT touch the key file yourself |

## Stop / start
- `./stop.sh`: full halt. It disables LIVE (renames `LIVE` to `LIVE.off`), **sells all open live positions**, then stops. This can take up to 4 minutes.
- `./stop.sh --no-sell`: halts immediately and leaves tokens in the wallet with no stop-loss management.
- `rm LIVE`: no new live buys; open positions are still managed.
- `./start.sh --live`: start with LIVE on. `./start.sh` alone starts paper only unless `LIVE` exists.

## Roster checks (hourly)

- `cat roster-status.md`: the ranked table, LIVE now and why, and the rotation log. It should update within ~1 min of each UTC hour (check the 'Updated' line).
- `grep '"event": "rotation"' paper-trades.jsonl | tail -3`: the hourly rank records.
- Report each promotion or demotion with the reason from the rotation log (`inactive: …`, `replaces inactive …`, `slot_empty`). An empty LIVE set overnight is normal when no eligible leader is trading; the 'last buy/sell seen' column shows activity. Report urgently if more than 3 leaders show as LIVE, if roster-status.md is more than 2h old, or if a demoted leader still gets new live buys (`buy` events in live-trades.jsonl after its demotion time). Leftover open positions after a demotion are normal.
- `roster_reload` events in paper-trades.jsonl show wallets added or removed by Zero, with any warnings (over 20, invalid, duplicate).

## Reports / files
- `summary.md`: paper table per leader versus copyfomo, plus the **LIVE** section (wallet SOL/USDC/value, real fills, net).
- `live-trades.jsonl`: every live event (buys and sells with signature, SOL in/out, fees, slippage; conversions; skips; errors).
- `paper-trades.jsonl` and `quotes.jsonl`: paper events and marks. `run.log`: all stdout.
- `live-night-start.json`: tonight's starting wallet value (the loss-limit base).
- `state.json`: full state (positions, cursors, wallet snapshot).
- Tests (safe; they never send): `python3 test_live.py` and `python3 test_simulate.py`.
