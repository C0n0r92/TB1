# HANDOFF — Polymarket 1h/4h BTC-ETH Up-or-Down complete-set track (from Lab to Oracle), 2026-10-23

Paper sim only. Public Gamma and data-api taker tape. No loop and no running process; this was a one-off historical simulation.
Full write-up, including WHY THIS COULD FAIL and who is on the other side: `README.md`.

- Built:
  - `fetch.py`: 418 closed markets (Oct 16–23), each with its taker tape, saved to `data/markets.json`, plus a live book snapshot in `data/book_snapshots.jsonl`.
  - `sim.py`: passive two-leg state machine with touch, queue(50/200) and through fill models, checking every 5/10/15 min.
  - `run_ud.py`: 360-variant grid, rubric scoring, `out/grid.json`, `out/scorecard.md`, and leaderboard rows `PMUD_*` (10 headline rows, variants_tried = 360).
- Result: 0 of 360 variants profitable.
  - Completed pairs did cost 0.90–0.95 combined, which matches the unverified "0.91–0.97" claim.
  - But ~40–45% of markets leave an unmatched leg, and those legs almost always lose because of adverse selection: 7 of 141 leftovers won on 1h, 0 of 38 on 4h.
  - Net over the week: 1h headline −$216 and 4h −$102 (10-share legs). Scores 8–9/25; not a candidate.
- Re-run: `python3 fetch.py && python3 run_ud.py`.
- Open questions:
  - Fast-requote or market-maker variants with rebates are untested, as are early stop-out or hedge of leftovers.
  - The queue size is assumed, not historical.
  - Only 7 days of data.
- Ireland: see `../polymarket-weather/HANDOFF.md`. Ireland is restricted, so trading is not permitted.
