# SOL trend/breakout - status 2026-10-23 22:35 UTC (Lab; handed to Oracle)
**Conclusion: no scored result yet.** The research moved to Oracle before the full grid ran. Nothing is a candidate, and no leaderboard rows were added.

A 2-setting smoke test was run, with untuned defaults, mid costs and a 5-min bot cycle. OOS is 2026-01-04 to 2026-10-23, when SOL buy-and-hold lost 22.8%.
- (A) Spot long-only, 1h EMA50>200 + 20-bar breakout, 2 ATR stop, 3 ATR trail: 113 trades (44 OOS), +0.31% per trade after costs, +10.9% OOS compounded.
  It beat buy-and-hold OOS, mainly by sitting in cash during the decline. Unscored: no CI, Monte Carlo, neighbour or random-entry checks.
- (B) 1x long+short on Jupiter perps, same rule: 268 trades, -0.08% per trade; -34.6% in-sample, +13.2% OOS.
  It loses in-sample, so it fails the "holds out-of-sample" rule as it stands.
- 4h/55-bar versions: too few trades (28 / 58) to say anything.

Caveats: a single price path (2 years, mostly a SOL downtrend); SOL/USDT rather than USDC; perp funding before Jul 2026 is assumed, not measured;
the Drift API was unreachable. Only 4 untuned configs have been looked at, so there is no multiple-testing inflation yet.

WHY THIS COULD FAIL: trend rules win a few large moves and lose many small ones (32-36% win rate), so a choppy year bleeds fees.
The OOS "edge" over buy-and-hold is mostly being in cash during the decline. On perps, shorts in squeezes and funding drag hurt.
Who is on the other side: market makers and CEX/perp arbitrage bots that fade breakouts, plus mean-reversion traders. The edge is crowded and public.

Polymarket SOL Up/Down was dropped from Lab's scope and is owned by Oracle (stub in /workspace/lab/sol-trend/polymarket/HANDOFF.md).
Full details, data coverage, cost assumptions and how to run it: /workspace/lab/sol-trend/HANDOFF.md
