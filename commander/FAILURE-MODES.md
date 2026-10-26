# Team failure-mode sheet (Zero, 2026-10-23)
Severity, likelihood and detection are each scored 1-5 (5 = worst, or hardest to notice). The fix column is the hard rule in place or planned.

| Bot | Edge | Failure mode | Sev | Lik | Det | Hard rule / fix |
|---|---|---|---|---|---|---|
| Chunk | radar momentum | buys an operator-built rug | 5 | 5 | 2 | rugguard hard rejects + 20-min survival check; live buys PAUSED until Lab shows an edge |
| Chunk | | stop skipped in a crash (gap-through) | 4 | 4 | 2 | 5% stake; Lab models gap fills; liquidity-drop exit (testing) |
| Chunk | | stale data -> trades on old prices | 4 | 2 | 4 | stale-data breaker (>15 min: no buys) |
| Copycat | borrowed trader edge | copy lag: buys what leader is already up on | 4 | 4 | 4 | log leader vs our entry; chase limit (testing, 15%) |
| Copycat | | trader goes cold / becomes exit liquidity | 4 | 3 | 3 | demote after 3 losing copies (proposed); X rug watch |
| Copycat | | Telegram signs out, so no monitoring or close | 5 | 2 | 3 | heartbeat line each watch run + Guard alert; user signs in |
| All | | night loss runs away | 5 | 2 | 1 | 20% nightly limit, $30 floor, flat by 8am, Guard checks |
| All | | sizing tied to last result (martingale) | 5 | 1 | 2 | fixed fraction of current balance, max 15% |
| Lab | | backtest flatters (look-ahead, one night) | 3 | 4 | 4 | out-of-sample split, 50 trades, 18/25 score, Monte Carlo, nearby-settings sweep |
| Scout/Pulse | | bad or late data fed to traders | 3 | 3 | 4 | unknown != reject; timestamps on everything; Lab grades usefulness |
