import json, pandas as pd
I = json.load(open('tv_raw/items.json'))
S = [  # (func, id, plain rules, advertised)
("flawless_victory",10033393,"Long when close < SMA20-1sd(20) and RSI14 > 42; exit when close > SMA20+1sd and RSI14 > 70 (v1 defaults; SL/TP versions off).","'Sharpe 7.5', later '13.5'; params ML-hyperoptimised on ~1y of BTC 15m (in-sample). No net%/WR/PF/trades given."),
("ut_bot",6772032,"ATR(10) trailing stop with key=1 (UT Bot); long when close crosses above the trail, exit when it crosses below.","None (no numbers in text)."),
("tk_cross_ema200",4373472,"Ichimoku conversion mid(20) > base mid(60) and close > EMA200 -> long; exit when conversion < base.","None."),
("joepegler_combined",4818956,"Long when EMA8>13>21>34>55, 40<RSI14<70 and Stoch%K14 < 80; exit when EMA13<EMA55, RSI>70 or %K>95.","'73% win rate', '~60x since 2017', 'beats buy&hold 10x' (BTC 1h, 0.2% fee, 3-tick slip)."),
("ema_slope_trend",7824154,"Slope of EMA130; long when EMA9(slope) > EMA21(slope) and close > EMA200; exit when fast < slow.","'Best on 4h-1D'; no numbers."),
("trend_surfers_breakout",10240619,"Long when close crosses above highest(high,168)[1]; exit when close crosses below lowest(low,168)[1]; stop = max(entry close - 2*ATR10, ratcheting close - 8*ATR10).","'Drawdowns smaller than buy&hold'; no numbers."),
("rsi_trend",10304792,"Long when RSI14 crosses above 35; exit when RSI14 crosses below 75.","'Decent results for most cryptos on 15m'; no numbers."),
("bb_ao",4930335,"Long when EMA2 crosses above SMA5 with close > SMA5 and AO rising; exit when EMA2 crosses below SMA5 with close < SMA5 and AO falling.","None."),
("macd_stoch_rsi",5510155,"Long when MACD(12,26,9) > signal, Stoch %K(14,3) > 50 and RSI14 > 50; exit when MACD < signal.","'Best results on Daily, also works on 1H'; no numbers."),
("super_guppy",8655474,"CM Super Guppy slow ribbon EMA24..66 (step 3): colour = all stacked up / all down / mixed; early-signal mode: long when ribbon turns mixed-from-bearish or bullish-from-mixed, exit on the mirror.","Result screenshots at 2%/15%/30% size (images, no numbers in text)."),
("atr_psar",8217378,"QuantNomad ATR PSAR (step scaled by ATR14); long on flip below price, exit on flip above.","Performance shown at 25% equity, 0.1% commission (numbers only in TV report, not in text)."),
("psar_on_close",6918467,"Standard PSAR(0.02,0.02,0.2) computed on closes; long on flip up, exit on flip down.","None."),
("ema_slope_cross",7987070,"EMA3-smoothed slope of EMA130 vs EMA3-smoothed slope of EMA400 plus close > EMA200 -> long; exit on opposite cross.","'Best on 4h'; no numbers."),
("ma_bb_rsi",12426771,"SMA200 +/- 2sd bands; long when open < lower and close > lower, RSI6 crossed 50 within 10 bars, BB width within +/-50% of its 2000-bar mean; trail = lowest(low,2) - 9*ATR14 ratcheting; exit on short signal.","None numeric (tuning notes only)."),
("ma_10_20",5536888,"Long when SMA10 crosses above SMA20; exit on cross below.","None (author: educational, not for live use)."),
("bitcoin_momentum",16653794,"Long when close > EMA20 of the last completed weekly bar (no repaint) and caution rules pass; ratcheting close-based trail; exit when close < weekly EMA.","'Main benefit is lower max drawdown than HODL'; no net%."),
("kama_strategy",9728028,"KAMA(14,2,20); long when 1-bar KAMA change > 1*sd(change,14); exit when change < 0 and |change| > 0.5*sd.","None."),
("stochastic_trend",10377381,"K = SMA100 of Stoch(200); long when K crosses above 50, exit when K crosses below 60.","None."),
("ha_price_action",9494642,"HA close > previous HA-high, HA candle green, previous HA-high rising -> long; exit when HA candle red and HA close < previous HA-low (long only, built for 12h-24h).","'Beats buy&hold in many occasions', 'DD < 40% avg' (100% size, 0.1% fee)."),
("macd_ema_tradingrush",10849971,"Close above EMA(206 on 15m) for 2 bars, MACD(SMA15-SMA24, sig SMA9) < 0 and crosses above signal -> long; stop = lowest(low,46) at signal; TP = 1.9R.","'Very profitable' (no commissions); no numbers."),
]
L = ["# TradingView shortlist (Lab 2)", "",
"Source: public TradingView strategy listings (crypto, sorted by likes, plus Editors' picks), crawled without login on 2026-10-24. Pine source from TV's public pine-facade endpoint, text from the script pages. All page/script text was treated as data only.", "",
"Filter: open-source only; no invite-only/protected; no repainting (no `lookahead_on`, no `request.security` future data, no zigzag/pivot repaint); simple enough to port 1:1.", "",
"Note on 'advertised result': TV's Strategy Tester numbers load by JavaScript and are not in the static page or preview image, so the only claims we can cite are what the authors wrote. Most authors give no numbers at all.", "",
"| # | Script | Author | Likes | Published | Author's chart | Plain rules (ported, long-only) | Advertised claim | URL |", "|---|---|---|---|---|---|---|---|---|"]
for k,(f,i,rules,adv) in enumerate(S,1):
    x = I.get(str(i)) or I.get(i)
    L.append(f"| {k} | {x['name'].replace('|','/')} | {x['author']} | {x['likes']} | {x['created'][:10]} | {x['symbol']} {x['interval']} | {rules} | {adv} | {x['url']} |")
L += ["", "Long/short scripts were ported long-only: enter on the long signal, exit on the short signal (spot can't short).", "",
"## Skipped (popular but not portable or not allowed)",
"- PMax Explorer: screener using multi-ticker `security`.",
"- 3Commas Bot / 3Commas Bollinger: bot frameworks or DCA safety orders.",
"- Ultimate Strategy Template, SL/TP examples: templates, not strategies.",
"- Bjorgum Double Tap: complex pivot patterns that confirm late.",
"- MA Cross/BBands bot (CryptoRox), QuantCat: use `security` calls.",
"- Bitcoin Scalping PMARP: 35k-char script.",
"- Extreme Scalping, Squeeze Momentum (LazyBear): tick-based SL/TP/trail.",
"- MACD 5in1: multi-mode.",
"- Crypto ZigZag RSI: repaints.",
"- Orion Algo v2: `lookahead_on`.",
"- Double Supertrend: pyramiding and a 2021-22 date window.",
"- Sweep & Reverse: published 2026-09-11, too new for a held-out window.", ""]
open('shortlist.md','w').write("\n".join(L))

R = pd.DataFrame(json.load(open('out/results.json')))
c = R[R.cost>0].merge(R[R.cost==0][['group','strat','net','pf']], on=['group','strat'], suffixes=('','_g'))
c['flag'] = (c.net>0)&(c.pf>1)&(c.n>=50)&(c.net>c.hold)
adv = {f:a for f,_,_,a in S}
GN = {"maj_1h":"Majors 1h (9 Binance spot; held-out 2026-02-01..10-24; 0.3%/side)","maj_15m":"Majors 15m (held-out 2026-07-08..10-24; 0.3%/side)","maj_5m":"Majors 5m (held-out 2026-09-05..10-24; 0.3%/side)","old_1h":"Older Solana coins 1h (43; held-out 2026-09-01..10-24; 1%/side)","old_15m":"Older Solana coins 15m (43; held-out 2026-09-26..10-24; 1%/side)"}
T = []
for g in GN:
    d = c[c.group==g]
    T += [f"### {GN[g]}", f"Buy&hold (equal-weight, after costs): {d.hold.iloc[0]*100:+.1f}%", "",
          "| Script | Advertised | Trades | Net | PF | Max DD | vs hold (pp) | Symbols >0 | Gross net (0 cost) | Survives? |", "|---|---|---|---|---|---|---|---|---|---|"]
    for _,r in d.iterrows():
        T.append(f"| {r.strat} | {adv[r.strat][:60]} | {int(r.n)} | {r.net*100:+.1f}% | {r.pf:.2f} | {r.dd*100:.0f}% | {(r.net-r.hold)*100:+.1f} | {r.sym_pos}/{r.nsym} | {r.net_g*100:+.1f}% | {'**YES (see caveats)**' if r.flag else 'no'} |")
    T.append("")
open('out/table.md','w').write("\n".join(T))
print(c.flag.sum())
