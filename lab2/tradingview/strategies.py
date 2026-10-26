"""Ports of 20 public open-source TradingView strategies (script defaults), long-only.
Each fn(d, tfmin) -> sig dict for tvlib.backtest. Long/short scripts: long on the long signal, flat on the short signal."""
import numpy as np
from tvlib import *
from tvlib import _s

def flawless_victory(d, tf):  # v1 default (no SL/TP)
    c = d['c']; b = sma(c, 20); dv = stdev(c, 20); r = rsi(c, 14)
    return dict(enter=(c < b - dv) & (r > 42), exit=(c > b + dv) & (r > 70))

def ut_bot(d, tf):  # a=1, ATR10, HA off
    c = d['c']; nl = 1 * atr(d['h'], d['l'], c, 10); n = len(c); ts = np.zeros(n)
    for i in range(1, n):
        p = ts[i-1]; L = nl[i] if not np.isnan(nl[i]) else 0.0
        if c[i] > p and c[i-1] > p: ts[i] = max(p, c[i] - L)
        elif c[i] < p and c[i-1] < p: ts[i] = min(p, c[i] + L)
        else: ts[i] = c[i] - L if c[i] > p else c[i] + L
    buy = (c > ts) & crossover(c, ts); sell = (c < ts) & crossover(ts, c)
    warm = np.isnan(nl); return dict(enter=buy & ~warm, exit=sell)

def tk_cross_ema200(d, tf):
    c, h, l = d['c'], d['h'], d['l']; conv = (highest(h, 20) + lowest(l, 20)) / 2; base = (highest(h, 60) + lowest(l, 60)) / 2
    return dict(enter=(conv > base) & (c > ema(c, 200)), exit=conv < base)

def joepegler_combined(d, tf):
    c = d['c']; e = [ema(c, k) for k in (8, 13, 21, 34, 55)]; r = rsi(c, 14); k = stoch(c, d['h'], d['l'], 14)
    le = (e[0] > e[1]) & (e[1] > e[2]) & (e[2] > e[3]) & (e[3] > e[4])
    return dict(enter=le & (r < 70) & (r > 40) & (k < 80), exit=(e[1] < e[4]) | (r > 70) | (k > 95))

def ema_slope_trend(d, tf):
    c = d['c']; out = ema(c, 130); slp = change(out) / out; f, s = ema(slp, 9), ema(slp, 21)
    return dict(enter=(f > s) & (c > ema(c, 200)), exit=f < s)

def trend_surfers_breakout(d, tf):
    c, h, l = d['c'], d['h'], d['l']; hh = shift(highest(h, 168)); ll = shift(lowest(l, 168)); a = atr(h, l, c, 10)
    return dict(enter=crossover(c, hh), exit=crossunder(c, ll), stop_fixed=c - 2 * a, trail=c - 8 * a, trail_from='signal')

def rsi_trend(d, tf):
    r = rsi(d['c'], 14); return dict(enter=crossover(r, 35), exit=crossunder(r, 75))

def bb_ao(d, tf):
    c = d['c']; hl2 = (d['h'] + d['l']) / 2; basis = sma(c, 5); fast = ema(c, 2); ao = sma(hl2, 5) - sma(hl2, 34); aop = shift(ao)
    AO = np.where(ao >= 0, np.where(ao > aop, 1, 2), np.where(ao > aop, -1, -2))
    return dict(enter=crossover(fast, basis) & (c > basis) & (np.abs(AO) == 1), exit=crossunder(fast, basis) & (c < basis) & (np.abs(AO) == 2))

def macd_stoch_rsi(d, tf):
    c = d['c']; m = ema(c, 12) - ema(c, 26); s = ema(m, 9); k = sma(stoch(c, d['h'], d['l'], 14), 3); r = rsi(c, 14)
    return dict(enter=(m > s) & (k > 50) & (r > 50), exit=m < s)

def super_guppy(d, tf):  # early signals ON (default), long-only
    c = d['c']; E = [ema(c, k) for k in range(24, 67, 3)]  # ema8..ema22 = 24..66
    L = np.all([E[j] > E[j+1] for j in range(len(E)-1)], axis=0); S = np.all([E[j] < E[j+1] for j in range(len(E)-1)], axis=0)
    col = np.where(L, 1, np.where(S, -1, 0)); n = len(c); en = np.zeros(n, bool); ex = np.zeros(n, bool); isL = isS = False
    for i in range(1, n):
        lg = (not isL) and ((col[i] == 1 and col[i-1] == 0) or (col[i] == 0 and col[i-1] == -1))
        sh = (not isS) and ((col[i] == 0 and col[i-1] == 1) or (col[i] == -1 and col[i-1] == 0))
        if lg: isL, isS = True, False
        if sh: isL, isS = False, True
        en[i], ex[i] = lg, sh
    return dict(enter=en, exit=ex)

def _psar(d, atr_mode):
    o, h, l, c = d['o'], d['h'], d['l'], d['c']; n = len(c); A = atr(h, l, c, 14); T = tr(h, l, c); A = np.where(np.isnan(A), T, A)
    ps = np.zeros(n); af = np.zeros(n); td = np.zeros(n, int); ep = np.zeros(n); tb = np.zeros(n, int)
    for i in range(1, n):
        first = (i == 1); l2s = td[i-1] == 1 and c[i] <= ps[i-1]; s2l = td[i-1] == -1 and c[i] >= ps[i-1]; chg = first or l2s or s2l
        td[i] = (1 if c[i-1] > o[i-1] else -1) if first else (-1 if l2s else 1 if s2l else td[i-1])
        tb[i] = -1 if l2s else 1 if s2l else (tb[i-1] + 1 if td[i] == 1 else tb[i-1] - 1 if td[i] == -1 else tb[i-1])
        af[i] = 0.02 if chg else (min(0.2, af[i-1] + 0.02) if ((td[i] == 1 and h[i] > ep[i-1]) or (td[i] == -1 and l[i] < ep[i-1])) else af[i-1])
        ep[i] = h[i] if (chg and td[i] == 1) else l[i] if (chg and td[i] == -1) else (max(ep[i-1], h[i]) if td[i] == 1 else min(ep[i-1], l[i]))
        if first: ps[i] = l[i-1] if c[i-1] > o[i-1] else h[i-1]
        elif chg: ps[i] = ep[i-1]
        elif atr_mode: ps[i] = ps[i-1] + af[i] * A[i] if td[i] == 1 else ps[i-1] - af[i] * A[i]
        else: ps[i] = ps[i-1] + af[i] * (ep[i] - ps[i-1]) if td[i] == 1 else ps[i-1] - af[i] * (ps[i-1] - ep[i])
    w = np.arange(n) > 50
    return dict(enter=(tb == 1) & w, exit=tb == -1)
def atr_psar(d, tf): return _psar(d, True)
def psar_on_close(d, tf): return _psar(d, False)

def ema_slope_cross(d, tf):
    c = d['c']; m1, m2 = ema(c, 130), ema(c, 400); e1 = ema((m1 - shift(m1)) / m1, 3); e2 = ema((m2 - shift(m2)) / m2, 3)
    return dict(enter=(e1 > e2) & (c > ema(c, 200)), exit=e1 < e2)

def ma_bb_rsi(d, tf):  # defaults: SMA200, BB 2.0/200, RSI6 x50 within 10 bars, vol filters, ATR(14)*9 trailing stop
    o, h, l, c = d['o'], d['h'], d['l'], d['c']; MA = sma(c, 200); dev = stdev(c, 200) * 2; up, lo = MA + dev, MA - dev
    r = rsi(c, 6); co, cu = crossover(r, 50), crossunder(r, 50)
    rb = np.zeros(len(c), bool); rs = np.zeros(len(c), bool)
    for k in range(11): rb |= shift(co.astype(float), k) == 1; rs |= shift(cu.astype(float), k) == 1
    bv = up - lo; base = sma(bv, 2000); vh = bv > base * 1.5; vl = bv < base * 0.5
    ok = ~vh & ~vl & ~np.isnan(base)
    vL = (o < lo) & (c > lo) & rb & ok; vS = (o > up) & (c < up) & rs & ok
    a = atr(h, l, c, 14)
    return dict(enter=vL, exit=vS, trail=lowest(l, 2) - a * 9, trail_from='signal')

def ma_10_20(d, tf):
    c = d['c']; a, b = sma(c, 10), sma(c, 20); x = cross(a, b); return dict(enter=x & (a > b), exit=x & (a < b))

def bitcoin_momentum(d, tf):
    t, h, l, c = d['t'], d['h'], d['l'], d['c']; import pandas as pd
    s = pd.Series(c, index=pd.to_datetime(t, unit='s', utc=True)); wk = s.resample('W-SUN', label='left', closed='left').last()
    we = pd.Series(ema(wk.values, 20), index=wk.index)  # EMA20 of completed weekly closes
    wprev = we.shift(1)  # in week W use value of completed week W-1
    htf = wprev.reindex(s.index, method='ffill').values; htf = shift(htf, 1)
    A = atr(h, l, c, 5); e = ema(c, 20); bull = c > htf
    caut = bull & (((highest(h, 7) - l) > A * 1.5) | (c < e))
    cand = highest(l, 7) - np.where(shift(caut.astype(float)) == 1, A * 0.2, A)
    return dict(enter=bull & ~caut, exit=c < htf, trail=cand, trail_from='fill', trail_on_close=True)

def kama_strategy(d, tf):
    c = d['c']; n = len(c); mom = np.abs(change(c, 14)); vol = _s(np.abs(change(c))).rolling(14).sum().values
    er = np.where(vol != 0, mom / vol, 0); er = np.nan_to_num(er); fa, sa = 2 / 3, 2 / 21; sc = (er * (fa - sa) + sa) ** 2
    k = np.zeros(n)
    for i in range(n): k[i] = sc[i] * c[i] + (1 - sc[i]) * (k[i-1] if i else 0)
    dl = change(k); sd = stdev(dl, 14); w = np.arange(n) > 200
    return dict(enter=(dl > 0) & (dl > sd) & w, exit=(dl < 0) & (np.abs(dl) > 0.5 * sd))

def stochastic_trend(d, tf):
    k = sma(stoch(d['c'], d['h'], d['l'], 200), 100); return dict(enter=crossover(k, 50), exit=crossunder(k, 60))

def ha_price_action(d, tf):
    o, h, l, c = d['o'], d['h'], d['l'], d['c']; n = len(c); hc = (o + h + l + c) / 4; ho = np.zeros(n); ho[0] = (o[0] + c[0]) / 2
    for i in range(1, n): ho[i] = (ho[i-1] + hc[i-1]) / 2
    hh = np.maximum(h, np.maximum(ho, hc)); hl = np.minimum(l, np.minimum(ho, hc))
    return dict(enter=(hc > shift(hh)) & (hc > ho) & (shift(hh) > shift(hh, 2)), exit=(hc < ho) & (hc < shift(hl)))

def macd_ema_tradingrush(d, tf):  # EMA206 on 15m; approximated on other TFs by chart EMA of 206*15/tf bars
    c, l = d['c'], d['l']; L = max(2, int(round(206 * 15 / tf))); E = ema(c, L)
    m = sma(c, 15) - sma(c, 24); s = sma(m, 9)
    up = (c > E) & (shift(c) > shift(E))
    return dict(enter=up & (m < 0) & crossover(m, s), exit=np.zeros(len(c), bool), stop_fixed=lowest(l, 46), tp_rr=1.9)

STRATS = dict(flawless_victory=flawless_victory, ut_bot=ut_bot, tk_cross_ema200=tk_cross_ema200, joepegler_combined=joepegler_combined,
  ema_slope_trend=ema_slope_trend, trend_surfers_breakout=trend_surfers_breakout, rsi_trend=rsi_trend, bb_ao=bb_ao,
  macd_stoch_rsi=macd_stoch_rsi, super_guppy=super_guppy, atr_psar=atr_psar, psar_on_close=psar_on_close,
  ema_slope_cross=ema_slope_cross, ma_bb_rsi=ma_bb_rsi, ma_10_20=ma_10_20, bitcoin_momentum=bitcoin_momentum,
  kama_strategy=kama_strategy, stochastic_trend=stochastic_trend, ha_price_action=ha_price_action, macd_ema_tradingrush=macd_ema_tradingrush)
