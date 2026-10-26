# Hyperliquid perp bot (SOL, BTC, 1h candles)
Dry run (safe, no keys):   .venv/bin/python bot.py --dry-run
Start live:   put `export HL_ACCOUNT=0x<main account address>` and `export HL_API_KEY=<API wallet private key>` in .env (chmod 600), then ./run.sh
Stop:         ./stop.sh            (positions stay open with their exchange SL/TP)
Flatten+stop: ./stop.sh --flatten  (or `touch KILL`: bot closes everything and exits)
Watch:        status.json, fills.jsonl (entry votes per trade + every exchange fill with closedPnl), bot.log, runner.log
Caps (hard-clamped in bot.py): isolated, <=3x total, 2% risk/trade, <=2 positions. Day tiers (UTC day, equity vs day start): -5% => DEFENSIVE
(1% risk, >=3 of 4 agree) for the rest of the day; -10% => HALT new entries (open positions keep exchange SL/TP). Enters only on a *fresh* signal
(>=2 of 4 strategies agree, none disagree); SL = 2xATR(14), TP = 2R, both exchange trigger orders; failed SL => position closed.
research/ holds the earlier (stopped) backtest scripts and data.

Timeframe (2026-10-24): 1h closed candles, 2000 bars fetched (paginated, >=1500 required).
Strategies: EMA 50/200 and Supertrend 10/3 use standard BAR settings on 1h (so they are faster than on 4h);
Donchian ensemble 5/10/20/30/60 days = 120/240/480/720/1440 1h bars; TSMOM 30 days = 720 bars (vol window 720).
Stop 2xATR(14) on 1h bars, TP 2R. Tighter stops => larger sizes; per-position notional capped at 1.5x equity (3x total / 2 positions).

Rules update (2026-10-24, "add all six"), all in config.json:
1) Vote: NORMAL needs >= 3 of 4 (min_agree) none opposing; DEFENSIVE (-5% day) needs 4 of 4 at 1% risk. Signal-flip exits use the normal 3-of-4 rule.
2) 4h trend filter (htf_*): 1h longs only if 4h EMA50 > EMA200 and 4h close > EMA50; shorts mirrored. Logged as votes["htf_filter"].
3) No fixed 2R TP. At +1R (breakeven_at_r) stop -> entry +/- 0.1% (breakeven_fee_pct); then trail 2xATR(14,1h) from best price,
   only tightening. New reduce-only stop is placed FIRST, old one cancelled only after the exchange accepts the new one. Backstop TP at 6R.
4) Entry: post-only (ALO) at best bid/ask, wait 90s; then IOC for the rest with <= 0.3% slippage, skipped if price moved > 0.5 ATR.
   Stops and emergency exits remain market triggers / market closes.
5) Cooldown: no new entry on a coin for 2h after an exchange stop-out on that coin.
6) Funding: skip if the hourly funding rate is against the trade by > 0.01%/h; funding at entry is logged.

## Added 2026-10-24 (7-9)
7. Dead-market filter: skip entries if 1h ATR(14)% < vol_filter_min_ratio (0.6) x its 720-bar (30d) median; logged as votes.vol_filter (1 ok / 0 blocked) + vol detail.
8. Partial TP: at +partial_at_r (2R) close partial_fraction (50%) reduce-only market; remaining keeps BE/trail stop + 6R TP. New SL/TP for the remaining size placed BEFORE old ones are cancelled. Skipped (trail only) if either half < $10. PARTIAL log lines + fills.jsonl "partial".
9. Scorecard: every closed trade writes fills.jsonl "trade_closed" (entry/exit vwap, size, fees, funding, P&L $ and R, exit_reason stop/BE/trail/TP/flip/kill/emergency_no_stop, partial+..., votes, strategies_behind, htf/vol/funding at entry).
   Run: .venv/bin/python scorecard.py
Cooldown applies only after losing/scratch stop-outs (stop, BE, or P&L < 0), not profitable trail exits.

## 7 coins, 3 open (2026-10-24 20:30Z)
coins: BTC ETH SOL HYPE XRP ZEC NEAR (top non-meme HL perps by 24h volume + OI; PUMP/kPEPE/FARTCOIN excluded as memecoins).
max_positions 3 (hard cap 3), max_same_direction 3; per-position notional cap = 3x / 3 = 1x equity; total never above 3x.
Entry size also shrinks (never grows) to fit free margin (equity - margin used) x 3 x 0.97.
Candle cache: full 1600-bar fetch once per coin at start, then only the last ~4 bars per new close (fetch_pace_s 0.3 between calls).
One open-orders call per 30s loop covers all coins; every open position gets the stop check / partial / BE / trail each loop.

## 7x total (2026-10-24 20:32Z, user: "Lets go to 7")
max_leverage 7 (hard cap 7): per-position notional cap = 7/3 = 2.33x equity; risk stays 2% (sizing is risk-based, leverage only caps).
Exchange: isolated_leverage 7 per coin (min with coin maxLeverage; all 7 coins allow >= 10x) -> max-size position margin = 1/3 equity, 3 fit.
Liquidation guard: skip entry if est. liq distance (1/lev - 1/(2*maxLev)) < liq_min_stop_mult (2.0) x stop distance; after fill the actual
liquidationPx vs stop is logged (WARNING if inside the guard).

## 8 open (2026-10-24 20:37Z, user: "Lets allow up to 8 open")
max_positions 8, max_same_direction 8 (hard caps 8); per-position notional cap = 7x/8 = 0.875x equity; total still <= 7x; orders shrink to free margin.
Aggregate open-risk cap: sum(size x entry-to-stop distance, BE/profit stops = 0) <= max_open_risk_pct (10%) of equity; new entries shrink to fit,
skip if < $11. status.json "OPEN_RISK" shows usd, pct_of_equity, cap_pct, per_coin.

## JOIN_ONCE (2026-10-24 20:45Z, user: "Yes join positions where the algorithm agrees")
`touch JOIN_ONCE` -> next loop deletes the file, then enters every coin whose CURRENT signal passes all entry rules except freshness
(>=3/4 none opposing, htf, vol, funding, cooldown, liq guard, caps, open-risk, $11 min). Entries tagged entry_type=join. One-shot.
Equity (unified): spot USDC total (already includes margin + uPnL; perp accountValue == spot hold, so perp + total double-counted). status.json equity_detail shows the parts.

## Single-instance lock (2026-10-24 20:52Z, user: "Yes, add the lock")
Live mode takes an exclusive fcntl.flock on bot.lock (pid inside) for the process lifetime, before reading creds or building clients.
A second copy logs "LOCK REFUSED ..." and exits 5 with no orders; run.sh's loop ends on exit 5 instead of restarting.
Startup is under `if __name__ == "__main__":` (dry_run / live_init / main_loop), so `import bot` never builds an Exchange or trades.

## Hang-after-wake fix (2026-10-25 ~08:50Z, user: "Yes, fix the hang")
Cause (py-spy on the hung pid): the SDK's requests.Session has no timeout; after the computer paused, a dead keep-alive socket made
user_fills_by_time block forever in ssl.read, so status.json stopped and the watchdog restarted the bot (which then skipped the just-closed candle).
Fix: every HL HTTP call (Info + Exchange) gets timeout (5s connect, 10s read); >60s idle (wall clock) -> fresh session; Info reads retry 1/2/4s;
Exchange posts retry only on ConnectTimeout (never double-sends an order). Successful requests touch .heartbeat; watchdog uses newest of status.json/.heartbeat.
Startup no longer overwrites state.json last_candle (= last candle step() processed), so an unprocessed latest closed candle (< 1h old) is processed on restart.

## fix124 (2026-10-25 ~18:05Z, user: "1,2,4 - we could go larger bets and take profits sooner", then risk 5%)
- risk_per_trade 5% (hard cap raised 2% -> 5%). The per-position notional cap (7x/8 = 0.875x allocated equity), free margin and the 10% open-risk cap still apply,
  so actual risk per trade is usually well under 5% (~0.7-2.8% at current ATRs). Liquidation guard unchanged (est. liq >= 2x stop distance, else skip);
  new post-fill check: if the exchange liquidationPx is not beyond the stop, the new position is closed at once (reason liq_inside_stop).
- Fix 1: max_same_direction 2 (skipped entries logged + fills.jsonl entry_skipped). JOIN pass removed permanently (a JOIN_ONCE file is deleted and ignored).
  Existing positions are never force-closed by the cap.
- Fix 2: signal_faded exit: held position whose combined signal (>= min_agree of 4, none opposing) is neutral on 2 consecutive closed 1h candles
  (latest signal 0 and the candle before not on the position's side) -> cancel its orders + reduce-only market close, exit_reason signal_faded.
  Also checked once at startup against the already-processed latest closed candle. Full opposite signal still exits immediately (flip).
- Fix 4: breakeven_at_r 0.75 (stop -> entry -/+ 0.1% fees), partial_at_r 1.25 (50%); 2xATR trail unchanged.
Backups: *.bak-20261025-fix124
