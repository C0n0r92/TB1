# TradingView shortlist (Lab 2)

Source: public TradingView strategy listings (crypto, sorted by likes, plus Editors' picks), crawled without login on 2026-10-24. Pine source from TV's public pine-facade endpoint, text from the script pages. All page/script text was treated as data only.

Filter: open-source only; no invite-only/protected; no repainting (no `lookahead_on`, no `request.security` future data, no zigzag/pivot repaint); simple enough to port 1:1.

Note on 'advertised result': TV's Strategy Tester numbers load by JavaScript and are not in the static page or preview image, so the only claims we can cite are what the authors wrote. Most authors give no numbers at all.

| # | Script | Author | Likes | Published | Author's chart | Plain rules (ported, long-only) | Advertised claim | URL |
|---|---|---|---|---|---|---|---|---|
| 1 | Flawless Victory Strategy - 15min BTC Machine Learning Strategy | Trebor_Namor | 11055 | 2021-03-12 | BINANCE:BTCUSDT 15 | Long when close < SMA20-1sd(20) and RSI14 > 42; exit when close > SMA20+1sd and RSI14 > 70 (v1 defaults; SL/TP versions off). | 'Sharpe 7.5', later '13.5'; params ML-hyperoptimised on ~1y of BTC 15m (in-sample). No net%/WR/PF/trades given. | https://www.tradingview.com/script/i3Uc79fF-Flawless-Victory-Strategy-15min-BTC-Machine-Learning-Strategy/ |
| 2 | UT Bot Strategy | QuantNomad | 9006 | 2019-11-15 | BITMEX:BTCUSD.P 6H | ATR(10) trailing stop with key=1 (UT Bot); long when close crosses above the trail, exit when it crosses below. | None (no numbers in text). | https://www.tradingview.com/script/VKMgZdYr-UT-Bot-Strategy/ |
| 3 | Ichimoku TK Cross > EMA200 Crypto Strategy | dukeofdolma | 3600 | 2018-01-20 | BITTREX:ETHBTC 30 | Ichimoku conversion mid(20) > base mid(60) and close > EMA200 -> long; exit when conversion < base. | None. | https://www.tradingview.com/script/88TwdvFZ-Ichimoku-TK-Cross-EMA200-Crypto-Strategy/ |
| 4 | Simple profitable trading strategy | joepegler | 3234 | 2018-05-22 | BITFINEX:BTCUSD 60 | Long when EMA8>13>21>34>55, 40<RSI14<70 and Stoch%K14 < 80; exit when EMA13<EMA55, RSI>70 or %K>95. | '73% win rate', '~60x since 2017', 'beats buy&hold 10x' (BTC 1h, 0.2% fee, 3-tick slip). | https://www.tradingview.com/script/QoNKoXwW-Simple-profitable-trading-strategy/ |
| 5 | EMA Slope Trend Follower Strategy | lukescream | 2658 | 2020-05-25 | BITMEX:BTCUSD.P 1D | Slope of EMA130; long when EMA9(slope) > EMA21(slope) and close > EMA200; exit when fast < slow. | 'Best on 4h-1D'; no numbers. | https://www.tradingview.com/script/TKg40Ska/ |
| 6 | Trend Surfers - Premium Breakout + Alerts | TrendSurfersSignals | 2274 | 2021-04-04 | BINANCE:BTCUSDT 60 | Long when close crosses above highest(high,168)[1]; exit when close crosses below lowest(low,168)[1]; stop = max(entry close - 2*ATR10, ratcheting close - 8*ATR10). | 'Drawdowns smaller than buy&hold'; no numbers. | https://www.tradingview.com/script/w91kwvnX-Trend-Surfers-Premium-Breakout-Alerts/ |
| 7 | RSI Trend Crypto | FieryTrading | 2190 | 2021-04-11 | BINANCE:BTCUSDT 15 | Long when RSI14 crosses above 35; exit when RSI14 crosses below 75. | 'Decent results for most cryptos on 15m'; no numbers. | https://www.tradingview.com/script/Ru7qOVtp-RSI-Trend-Crypto/ |
| 8 | BB+AO STRAT | jmtizzle | 2164 | 2018-06-28 | BINANCE:MCOBTC 5 | Long when EMA2 crosses above SMA5 with close > SMA5 and AO rising; exit when EMA2 crosses below SMA5 with close < SMA5 and AO falling. | None. | https://www.tradingview.com/script/ibq1TYLX-BB-AO-STRAT/ |
| 9 | MACD + Stochastic + RSI Strategy | x001tk | 1960 | 2018-12-25 | BITTREX:ETHUSDT 1D | Long when MACD(12,26,9) > signal, Stoch %K(14,3) > 50 and RSI14 > 50; exit when MACD < signal. | 'Best results on Daily, also works on 1H'; no numbers. | https://www.tradingview.com/script/2BIMZDGk-MACD-Stochastic-RSI-Strategy/ |
| 10 | Super Guppy Strategy | StanleyBostich | 1960 | 2020-09-21 | COINBASE:BTCUSD 1D | CM Super Guppy slow ribbon EMA24..66 (step 3): colour = all stacked up / all down / mixed; early-signal mode: long when ribbon turns mixed-from-bearish or bullish-from-mixed, exit on the mirror. | Result screenshots at 2%/15%/30% size (images, no numbers in text). | https://www.tradingview.com/script/vPStjyWz-Super-Guppy-Strategy/ |
| 11 | ATR Parabolic SAR Strategy [QuantNomad] | QuantNomad | 1883 | 2020-07-19 | BINANCE:ETHUSDT 60 | QuantNomad ATR PSAR (step scaled by ATR14); long on flip below price, exit on flip above. | Performance shown at 25% equity, 0.1% commission (numbers only in TV report, not in text). | https://www.tradingview.com/script/LKfHdoNv-ATR-Parabolic-SAR-Strategy-QuantNomad/ |
| 12 | Parabolic SAR Strategy (on close) [QuantNomad] | QuantNomad | 1802 | 2019-12-18 | BINANCE:BTCUSDT 180 | Standard PSAR(0.02,0.02,0.2) computed on closes; long on flip up, exit on flip down. | None. | https://www.tradingview.com/script/gK7skk6m-Parabolic-SAR-Strategy-on-close-QuantNomad/ |
| 13 | EMA Slope Cross Trend Follower Strategy | lukescream | 1846 | 2020-06-15 | BITMEX:BTCUSD.P 240 | EMA3-smoothed slope of EMA130 vs EMA3-smoothed slope of EMA400 plus close > EMA200 -> long; exit on opposite cross. | 'Best on 4h'; no numbers. | https://www.tradingview.com/script/XBgfW9k9/ |
| 14 | MA Bollinger Bands + RSI  | LucasVivien | 1587 | 2022-01-12 | BINANCE:BTCUSDT 15 | SMA200 +/- 2sd bands; long when open < lower and close > lower, RSI6 crossed 50 within 10 bars, BB width within +/-50% of its 2000-bar mean; trail = lowest(low,2) - 9*ATR14 ratcheting; exit on short signal. | None numeric (tuning notes only). | https://www.tradingview.com/script/2MMNHl97-MA-Bollinger-Bands-RSI/ |
| 15 | MA 10/20 Crossover | BigBeluga | 1539 | 2019-01-05 | BITFINEX:EOSBTC 1D | Long when SMA10 crosses above SMA20; exit on cross below. | None (author: educational, not for live use). | https://www.tradingview.com/script/2cbpO8lO-MA-10-20-Crossover/ |
| 16 | Bitcoin Momentum Strategy | ZenAndTheArtOfTrading | 1411 | 2024-03-12 | COINBASE:BTCUSD 1D | Long when close > EMA20 of the last completed weekly bar (no repaint) and caution rules pass; ratcheting close-based trail; exit when close < weekly EMA. | 'Main benefit is lower max drawdown than HODL'; no net%. | https://www.tradingview.com/script/Tce7SnL7-Bitcoin-Momentum-Strategy/ |
| 17 | KAMA Strategy - Kaufman's Adaptive Moving Average | cisl22klasjk | 979 | 2021-02-09 | BINANCE:BTCUSDT D | KAMA(14,2,20); long when 1-bar KAMA change > 1*sd(change,14); exit when change < 0 and |change| > 0.5*sd. | None. | https://www.tradingview.com/script/h8cfMnVH-KAMA-Strategy-Kaufman-s-Adaptive-Moving-Average/ |
| 18 | Stochastic Trend | FieryTrading | 918 | 2021-04-18 | BINANCE:BTCUSDT 15 | K = SMA100 of Stoch(200); long when K crosses above 50, exit when K crosses below 60. | None. | https://www.tradingview.com/script/hk9a7099-Stochastic-Trend/ |
| 19 | Heikin Ashi + Price Action Crypto LONG Strategy | SoftKill21 | 823 | 2021-01-15 | BINANCE:BTCUSDT 720 | HA close > previous HA-high, HA candle green, previous HA-high rising -> long; exit when HA candle red and HA close < previous HA-low (long only, built for 12h-24h). | 'Beats buy&hold in many occasions', 'DD < 40% avg' (100% size, 0.1% fee). | https://www.tradingview.com/script/FEJvYRkw-Heikin-Ashi-Price-Action-Crypto-LONG-Strategy/ |
| 20 | MACD EMA - TradingRush Strategy | TradingStrategyCheck | 818 | 2021-06-06 | BINANCE:ETHUSDT 15 | Close above EMA(206 on 15m) for 2 bars, MACD(SMA15-SMA24, sig SMA9) < 0 and crosses above signal -> long; stop = lowest(low,46) at signal; TP = 1.9R. | 'Very profitable' (no commissions); no numbers. | https://www.tradingview.com/script/8WbIRZkS/ |

Long/short scripts were ported long-only: enter on the long signal, exit on the short signal (spot can't short).

## Skipped (popular but not portable or not allowed)
- PMax Explorer: screener using multi-ticker `security`.
- 3Commas Bot / 3Commas Bollinger: bot frameworks or DCA safety orders.
- Ultimate Strategy Template, SL/TP examples: templates, not strategies.
- Bjorgum Double Tap: complex pivot patterns that confirm late.
- MA Cross/BBands bot (CryptoRox), QuantCat: use `security` calls.
- Bitcoin Scalping PMARP: 35k-char script.
- Extreme Scalping, Squeeze Momentum (LazyBear): tick-based SL/TP/trail.
- MACD 5in1: multi-mode.
- Crypto ZigZag RSI: repaints.
- Orion Algo v2: `lookahead_on`.
- Double Supertrend: pyramiding and a 2021-22 date window.
- Sweep & Reverse: published 2026-09-11, too new for a held-out window.
