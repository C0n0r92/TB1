# hlscalp — PAPER-ONLY Hyperliquid 15m scalper
No orders, no keys, no AI. Public info endpoints only. Cron every minute (flock + 55s timeout).
- Universe: HL perps excl BTC/ETH/SOL/HYPE/XRP/ZEC/NEAR, 24h ntl vol >= $20M, top-of-book spread <= 0.05%, top 20, refreshed every 3h.
- Signals (15m closed bars, fresh trigger within 3 bars): SQZMOM (LazyBear), EMA_ST (EMA9/21 cross + Supertrend 10,3), VWAP_RSI (UTC VWAP reclaim + RSI14 band), UTBOT (key 1, ATR10).
  Entry needs >=2 agreeing, 0 opposing, same side as 1h trend (close & EMA20 vs EMA50). Skip funding > 0.005%/h against trade.
- Paper $84, 1% risk, stop 1.5x ATR14(15m), max 5x isolated, max 4 open, 2-bar coin cooldown.
- Costs: taker 0.045% + half-spread on entry/stop/trail/time exits; TP1 as maker 0.015%; hourly funding at entry rate.
- Exits: TP1 50% @1.5R -> stop to BE, trail rest 1x ATR, 6h time stop; day stop -6% flattens + halts.
- Gaps: managed via 1m candles since last check (stop checked before TP); entries skipped if bar closed >5 min ago. Gaps -> gaps.jsonl.
Files: state.json, trades.jsonl, decisions.jsonl, gaps.jsonl, summary.json, hlscalp.log
