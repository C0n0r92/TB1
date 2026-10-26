# copylive: signal watcher for Chunk's MANUAL Banana Gun copy book

watch.py never trades, signs, reads keys, or opens Telegram or a browser. It reads /workspace/selfcopy (read only) and public APIs (DexScreener, Jupiter lite-api quote/price, rugcheck.xyz, GeckoTerminal, Scout's launch check, and public RPC getBalance/getTokenSupply). It writes only to this folder.

## Loop
    cd /workspace/runner-radar/copylive
    python3 watch.py            # polls every ~5s; prints ONE JSON action line and exits 0 when a manual trade is needed
    # trade it by hand in Banana Gun, then record it:
    python3 record.py buy  <mint> <sol_in> <tokens> <entry_px_usd|auto> <leader> <leader_px> <leader_ts>
    python3 record.py sell <mint> <fraction_of_ORIGINAL> <sol_out> <reason>
    python3 record.py clear <mint|ALL>   # didn't trade it: drop the pending action
    python3 record.py status
    python3 watch.py            # restart
Other modes: `--once` runs one tick (exit 3 = nothing to do), `--dry-run` replays the paper signals, and `-v` prints skips to stderr. Run `python3 test_watch.py` for the offline tests.

SELL actions give `fraction` as a share of the ORIGINAL tokens, plus `sell_pct_of_holding`, the percentage to type into Banana Gun. Each action also includes a ready-made `record_cmd`.

## Files
state.json (cursor, handled signals, pendings, peaks), positions.json, actions.jsonl, skips.jsonl, fills.jsonl, night-start.json.

## 15:50Z change: continuous watcher
- watch.py now runs continuously under `run_watch.sh` (supervisor, pidfiles supervisor.pid / watch.pid, auto-restart 3 s after a crash). It does NOT exit after an action, so do NOT restart it after record.py.
- Outstanding actions with expiry times: `pending_actions.json`. All actions: `actions.jsonl` / `watch.out`.
- Single instance: a manual `python3 watch.py` exits with code 4 if one is already running. `--exit-on-action` = old one-shot mode.
- Halt = equity (free SOL + open positions at DexScreener price/SOL-USD; no price -> sol_in*0.85*fraction held) <= 0.9 x session start. Live value in state.json "equity".
