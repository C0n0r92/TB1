# Track A: SMC long-only rules (written 2026-10-24 ~00:40Z, BEFORE any test was run). PAPER ONLY.

Notation: bar i has open/high/low/close O,H,L,C and is indexed by its CLOSE time. ATR = ATR14 (simple mean of true range) known at that close.
A zone is a price band [zb, zt]. **A zone exists only from the close of the bar that confirms it; the earliest bar that can retest it is the next one.**
Every zone gives at most one trade and expires 100 bars after confirmation. If a bar closes below zb before the zone is retested, the zone is dead.
Zones must be at least 0.25 x ATR wide; narrower ones are ignored.

## Zones (bullish only, for longs)
1. **FVG**: three bars a=i-2, b=i-1, c=i with L[c] > H[a]. Zone = [H[a], L[c]]. Confirmed at the close of c.
2. **Inverse FVG (IFVG)**: a bearish FVG (H[c] < L[a], band [H[c], L[a]]) is invalidated when a later bar k (within 100 bars) closes above L[a].
   It then flips to a bullish zone [H[c], L[a]], confirmed at the close of k.
3. **Order block (OB)**: the last down-close bar k (C<O) before a break of structure. BOS = one of the next 3 bars (k+1..k+3) closes above the highest high of bars k-10..k.
   Zone = [L[k], H[k]], confirmed at the close of the BOS bar.
4. **Breaker block**: a bearish OB is the last up-close bar k (C>O) where one of k+1..k+3 closes below the lowest low of k-10..k.
   When a later bar m (within 100 bars of that break) closes above H[k], the band [L[k], H[k]] becomes a bullish breaker, confirmed at the close of m.
5. **Volume imbalance (VI)**: two consecutive up-close bars a, b (C>O) whose bodies don't overlap: O[b] > C[a]. Zone = [C[a], O[b]]. Confirmed at the close of b.

## Trade
- **Retest / signal**: the first bar j after confirmation with L[j] <= zt and C[j] >= zb (it trades into the zone and doesn't close below it).
- **Entry**: market at O[j+1], the next bar's open.
- **Stop**: zb - 0.25 x ATR(at j). If the stop distance from entry is less than 2 x the round-trip cost, or more than 10%, the trade is skipped. If entry <= stop, it is skipped.
- **Target**: entry + R x (entry - stop). R is picked on TRAIN only from {1.5, 2, 3}, once per (setup, timeframe, universe, trend filter).
- **Exit order inside a bar**: the stop is checked first, then the target. A gap through the stop fills at that bar's open; a gap through the target fills at the target (conservative).
- **Timeout**: 48 bars after entry, exit at that bar's close.
- **Trend filter (on/off)**: on = C[j] > EMA200 and EMA50 > EMA200 on the same timeframe at the signal bar.
- **One open position per token per variant**: signals while a position is open are skipped.
- **Costs per side**, applied to entry and exit: 0.3% on Binance majors (SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP BOME), 1% on Lab's older-coins universe.
- **Regime** at the signal bar (src/regime.py, closed 4h bars only). Gate rule: if TRAIN shows a regime with mean net > 0 and >= 20 trades, the variant is re-run on TEST with only that regime (or regimes) allowed.

## Data, windows, universe
- **Majors** (Binance public klines): SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP BOME. No POPCAT on Binance spot; POPCAT is in the old-coins set.
  - 5m: 2026-05-27..08-15 train / 08-15..10-23 test.
  - 15m: 04-08..08-15 train / 08-15..10-23 test.
  - 1h: 2025-09-20..2026-08-15 train / 08-15..10-23 test.
- **Old coins** (Lab's GeckoTerminal cache, read only), with stables, tokenized stocks and wrapped coins removed: Pnut PENGU RAY TRUMP POPCAT ZEREBRO Fartcoin Ban CARDS ANTFUN pippin USELESS MOODENG $WIF jellyjelly ALCH MPLX MEW BOME arc (Lab old-coin pairs universe minus SOL and the stable CASH).
  - 1h: 06-22..08-31 train / 08-31..10-23 test.
  - 15m: 09-12..10-05 train / 10-05..10-23 test.
  - No 5m for old coins: Lab's 5m cache is only short pump.fun series, and a GeckoTerminal backfill would eat into the radar's shared rate limit.
- **Variants**: 5 setups x 5 (universe, timeframe) cells x trend on/off = 50 variants, each with R picked from 3 values on train (150 train configs). Regime gates come on top and are counted.
- **Claim bar**: >= 50 test trades, test mean net/trade bootstrap 95% CI above 0, and beating buy-and-hold of the same tokens over the test window.
  With 50+ variants, about 2-3 would show a CI above 0 by luck at 5%, so a single pass is a lead, not an edge.
