## How the universe was built (and its bias)

- Discovery: GeckoTerminal top Solana pools by 24 h volume and by 24 h tx count (pages 1-10 each, today's snapshot), SOL/USDC/USDT-quoted, stables/LSTs/wrapped majors removed, best-liquidity pool per token; DexScreener /tokens/v1 for total liquidity, mcap and first-pair date. Loose pre-filter ($1.5M-$600M mcap, > $150k liq today) so tokens that were in range earlier but drifted are still fetched.
- Point-in-time membership at every signal bar: age > 7 d (earliest of first candle, pool creation, DexScreener first pair), mcap = close x supply (supply = today's mcap / today's price, i.e. constant supply), liquidity = today's liq x sqrt(price then / price now) (constant-product pool with unchanged LP). Only the price is truly point-in-time; supply and LP are anchored on today.
- SURVIVORSHIP BIAS: the list is today's most-traded tokens. Tokens that were mid-caps two months ago and died/rugged/delisted are missing, so buy-and-hold and any long-only rule look better than they were. Momentum is helped less than buy-and-hold (it exits on stops/EMA), but its entries into later-dead tokens are still missing.
- 1h candles: GeckoTerminal OHLCV, up to 3 x 1000 bars per pool (~125 days max, less for younger pools). GT skips no-trade hours; a signal whose next bar is > 3 h later is dropped. All requests <= 6/min total (one 10.5 s global gap), cached in data/midcap/ (resumable; requests.log).

## WHY THIS COULD FAIL

- Universe survivorship (above) and anchored supply/liquidity: a token that unlocked supply or added LP looks bigger/deeper in the past than it was.
- One market regime (~2-4 months); momentum on alt-coins is strongly regime-dependent (works in broad risk-on, bleeds in chop). The holdout is short, so the OOS mean has a wide CI.
- Breakout fills: entry at next-bar open after a breakout is often a local spike on thin hours; 0.3-0.5%/side may understate slippage on a $5M-mcap token at a $100 ticket it is fine, at real size it is not.
- Stops are filled at the stop or a gapped open; 1h bars hide intrabar wicks/order of high and low within the bar.
- Many variants (108) on one data set: the best in-sample setting is biased upward; the neighbour sweep and holdout are the only guards.
- Correlation: all tokens move with SOL; 3 open positions are effectively one bet on SOL beta in sell-offs.

## Who is on the other side

- Early holders/teams/whales distributing into breakouts (the classic momentum seller), mean-reversion market makers and LPs (the pool itself sells to us at the breakout price), and MEV/sandwich bots on swaps without tight slippage. In a trend we buy from patient sellers; in chop we provide exit liquidity to them.
