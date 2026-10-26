# selfcopy: self-run Solana copy-trading bot (paper roster + LIVE rotation)



> ## ⚠️ PAPER for every roster leader + optional LIVE for up to 3 rotating leaders (default `_benjitrades`)
> LIVE trades real SOL from the dedicated bot wallet `9bp5LMtn5nmpNLJNAoLnXHPgmmsNKqjehco77W6xXXgX` (see WALLET.md).
> It is ON only while the file `./LIVE` exists. **Full halt: `./stop.sh`** sells all live positions, disables LIVE and stops the bot.
> `./stop.sh --no-sell` stops without selling. `rm LIVE` blocks new live buys but keeps managing open ones.

## LIVE mode (live.py)
- Only leaders holding a LIVE slot from the roster rotation (below) are live. By default that is `_benjitrades`. Every entry is recorded as paper; if its leader holds a live slot and it passes the live gate, it is also bought for real.
- **Hard caps** (the `HARD` constants are read-only; `live-config.json` can only tighten them):
  - size min($10, 15% of wallet value); keep ≥0.02 SOL; ≤3 open live positions (v2, 23 Oct: was $6)
  - first buys only; leader buy ≥$50 and seen ≤2 min after its block time; mcap ≥$1M; liquidity ≥$100k; token age ≥60 min (creation of its deepest DexScreener pool, i.e. the graduation pool for pump tokens); avoid list (mint and creator); chase ≤8%; Jupiter price impact ≤3%; filter overrides never go live
  - Exits v3 (24 Oct, same code for paper and LIVE: `live.exit_plan`): SL −15% before the first TP, then breakeven (entry + costs) after it, never skipped; TP sells 25% at +40% and another 25% at +100% (both at once on a jump past +100%), deferred while the leader bought the same token in the last 10 min and fired on the next check once 10 min pass with no new add if still above the level; after TP1 the rest trails 25% below the peak since entry (35% while the leader adds); on the leader's FIRST sell, sell all but 10% of the original size (keep all if <10% left), and that leftover ignores later leader sells and the trail, sells all at +500%, keeps the −15%/breakeven stop, and is still sold at 08:00 and by the night loss limit. Sell reasons: `sl_-15%`, `sl_breakeven`, `tp_+40%_25%`, `tp_+100%_25%`, `tp_+40%_and_+100%_25%+25%`, `sl_trail_-25%…`/`sl_trail_-35%…`, `leader_sold_N%_keep10`, `tp_leftover_+500%`; `tp_deferred` / `leader_add` events log deferrals.
  - no entries 07:45–08:00 Dublin; close-out from 08:00 Dublin, retried every 30s until flat
  - nightly loss limit: if wallet value (SOL + tokens at Jupiter sell quotes, measured in SOL) falls 20% below the night start in `live-night-start.json`, sell everything and make no more buys until 08:00
- Execution: Jupiter lite-api `/swap/v1/quote` → `/swap/v1/swap`, then signed locally with solders.
  - Priority fee 0.0001 SOL (hard max 0.0001; config can only lower it). Entries use dynamic slippage capped at 5%.
  - Sent to all public RPCs, then confirmed by polling.
  - Sells get up to 3 tries. Stops and close-outs escalate slippage 5% → 10% → 15%.
  - Emptied token accounts are closed, returning rent to the wallet.
- **Transaction guard:** before signing, every instruction is checked.
  - Allowed programs: Jupiter, ComputeBudget, System, Token, Token-2022, ATA and Memo.
  - System instructions may only transfer to our own wSOL account.
  - Token closeAccount may only pay this wallet. Any other top-level token instruction is rejected.
  - The fee payer must be the bot wallet.
- Real fills (sig, SOL in/out including fees and rent, tokens, slippage, priority fee) go to `live-trades.jsonl` and to the LIVE section of `summary.md`.
- When the wallet is unfunded or too small: no trade, logged as `unfunded`.
- USDC funding (copyfomo withdraws USDC): USDC counts at face value in wallet value. Once USDC ≥ $5 and SOL ≥ 0.01, it swaps USDC→SOL once via Jupiter (same guard, 1% slippage cap), keeping about $1 USDC. If SOL < 0.01 it logs `needs gas SOL` and idles.
- Copycat runbook: MONITOR.md.
- Tests: `python3 test_live.py` (41 cap and logic tests, fake prices) and `python3 test_simulate.py` (build, sign and simulateTransaction only, never sends).

## Leader roster and LIVE rotation (roster.py)

- `roster.json` lists the leader wallets (label, wallet, source, confidence, active). It was seeded with the original four. **Only Zero edits it** (from `/workspace/scout/copy-candidates.md`); the bot never adds wallets. It reloads within 60s of a change. At most 20 active wallets; invalid, duplicate or extra entries are skipped and logged. A dropped leader with open paper positions keeps being polled until those close.
- Every roster wallet is paper-traded with the same paper rules. Polling is 8s per wallet up to 16 wallets, then 0.5s × the number of wallets (20 → 10s). Paper marks are spaced at max(12s, 3s × open paper positions) so the shared Jupiter budget (~4.5 calls/10s) holds.
- **Hourly score** (once per UTC hour): uses paper trades from the last 72h that pass the v2 live filters (forced overrides excluded), with open trades marked at the latest Jupiter sell quote. Score = EV per trade after costs, i.e. mean net % of stake (Jupiter route fees + impact + fees). Win rate and max drawdown are recorded too. Eligible = at least 4 qualifying trades and score > 0.
- **LIVE slots:** at most 3 leaders (hard cap `max_live_leaders` in live.py).
  - **Promotion:** an eligible leader must be in the top 3 for 2 consecutive hourly ranks. It fills a free slot, or replaces the lowest-scoring live leader that has fallen out of the top 3.
  - **Demotion:** score ≤ 0, fewer than 4 qualifying trades, removed from the roster, or 2 live losses in a row since it got the slot. The loss check runs every minute, and a loss demotion adds a 24h cooldown.
  - **Inactivity (every minute):** a live leader with no buy or sell seen in 60 min loses its slot (new entries only, no cooldown). The slot goes straight, skipping hysteresis, to the best-scoring eligible leader (≥4 trades, score > 0, latest hourly scores, not in cooldown) that traded in the last 30 min; otherwise it stays empty. `_benjitrades` holds the default slot only while active. An inactive leader can't be promoted until it trades again, then earns the slot normally.
  - Losing a slot only blocks new entries. Open live positions keep their exits and still mirror that leader's sells.
- **Default:** until any leader qualifies (and again if every rotation leader gets demoted), `_benjitrades` alone is live, which is the old behaviour. If benji takes 2 live losses in a row, nobody is live until someone qualifies.
- All live caps are unchanged: size min($10, 15%), at most 3 open live positions in total across all leaders, night −20% limit, 07:45/08:00 rules and every filter.
- `roster-status.md` is rewritten every hour (and on every rotation change). It has the ranked table, who's live and why, and the rotation log. A short version is in summary.md.

## What it measures
It shows what copying 4 copyfomo leaders would earn if **we** copied them through Jupiter, compared with copyfomo's fees (2% per side, about 5.3% all-in per round trip).

| leader | wallet | mapping confidence |
|---|---|---|
| _benjitrades | 9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc | low |
| bystevenr | AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx | low |
| pointfarmcap | Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit | medium-low |
| ExactTallTakin | AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v | medium |

The wallets come from /workspace/onchain-intel/data/leader_mappings.json and are cross-checked against /workspace/trader-analysis/wallets.json at startup. A low-confidence mapping means the wallet may not belong to that person.

## Rules (`CFG` in selfcopy.py)
- **Polling.** Each leader wallet is polled every 8s with `getSignaturesForAddress(until=last seen)`. Every new successful transaction is fetched and parsed into a swap: the wallet's token delta against its SOL, WSOL, USDC or USDT delta.
- **Entry filter.** We enter only on the leader's **first buy** of a token. That means the on-chain pre-balance was 0, the bot hasn't seen the mint before, and the mint isn't in the leader's 30-day history in trader_swaps.csv. The buy must also pass:
  - leader buy ≥ $50
  - mcap ≥ $100k (DexScreener, falling back to Jupiter price × supply)
  - mint, address or creator (from rugcheck.xyz) not in onchain-intel/avoid.csv, which is reloaded when it changes
  - our quoted price no more than 15% above the leader's fill
- **Paper keeps the old entry filters** so it logs everything, but since 24 Oct it uses the same v3 exits as LIVE (before that: −25%/+100% half), so roster scores match live exits. Each paper trade is tagged `v2_pass` / `v2_fails` showing whether it would pass the new LIVE filters (see the last column in summary.md).
- **Entry.** After a 3s delay, the bot gets a live Jupiter quote for **$5 of SOL → token**. The paper entry is recorded at the quoted outAmount, which includes route fees and price impact. A 0.0005 SOL priority fee plus a 0.000005 SOL base fee is added to costs.
- **Exits.** Open positions are re-quoted on the SELL side (token → SOL) every ~12s.
  - Exits v3, same as LIVE (see above); paper breakeven = cost + entry and exit tx fees.
  - **08:00 Europe/Dublin:** everything is closed at the quoted price. A position with no route is booked at $0. No new entries are taken from 07:45 to 08:00.
- **Copyfomo comparison.** This uses the same quoted fills with a 2% fee on each side and no priority fee. A second column applies a flat 5.3% of stake.

## Run / stop
```
cd /workspace/selfcopy
./start.sh        # nohup ./run_loop.sh (restarts selfcopy.py if it dies), writes loop.pid
./stop.sh         # touches STOP -> bot writes final summary and exits; loop exits
rm STOP && ./start.sh   # resume (state.json keeps cursors, positions, P&L)
```
- Status: `cat loop.pid; pgrep -af "selfcopy.py run"; tail -f run.log`
- Dry run against a historical swap: `python3 selfcopy.py dryrun --leader bystevenr --with-sell [--force] [--sig SIG]`. It writes to `dryrun-*` files only. `--force` overrides the filters, and those overrides are marked "forced".
- Rebuild the summary: `python3 selfcopy.py summary`.
- Helius: the bot uses it only if the `HELIUS_API_KEY` env var is set when it starts. The key is never printed or logged. Without it, the bot uses publicnode plus api.mainnet-beta.

## Files
- `paper-trades.jsonl`: every event (start, cursor_init, leader_swap, skip with reason, entry, leader_sell_mirror, exit, error).
- `quotes.jsonl`: every mark-to-market sell quote.
- `summary.md`: per leader, trades, wins and losses, our net $ and %, and the copyfomo-fee equivalent side by side. It also covers skip reasons and endpoint call and 429 counts. It's rewritten every 30s.
- `state.json`: the restart-safe state. `run.log`: stdout and restarts.

## Caveats
- A quote isn't a fill. Real fills after landing will often be worse on fast pump.fun coins.
- With public RPC, detection lags by roughly 5 to 20s, plus the 3s delay.
- The SOL price comes from Jupiter's price API and is refreshed every 2 min.
- At $5 a trade, the 0.0005 SOL priority fee is about 1% per side when SOL is around $100. Raise the stake or lower the fee in CFG to see how that changes the result.
