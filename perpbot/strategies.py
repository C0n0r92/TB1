"""The 4 signal strategies. Each returns +1/0/-1 per CLOSED candle (no lookahead: only uses data up to that bar)."""
import numpy as np, pandas as pd

BARS_PER_DAY = 24   # set from config interval by bot.py (1h -> 24, 4h -> 6); Donchian/TSMOM lookbacks are in calendar days

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(df, n=14):
    pc = df.close.shift()
    tr = pd.concat([df.high-df.low, (df.high-pc).abs(), (df.low-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()
def rsi(s, n):
    d = s.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn.replace(0, 1e-12))

def ema_trend(df, fast=50, slow=200):
    ef, es = ema(df.close, fast), ema(df.close, slow)
    return pd.Series(np.where((ef > es) & (df.close > es), 1, np.where((ef < es) & (df.close < es), -1, 0)), df.index)

def rsi2_mr(df, lo=10, ema_n=200):
    """Long when above 200 EMA and RSI(2)<lo; short mirrored. Holds until close crosses SMA5 or RSI(2) recovers."""
    r, e, sma5, c = rsi(df.close, 2).values, ema(df.close, ema_n).values, df.close.rolling(5).mean().values, df.close.values
    out = np.zeros(len(df)); st = 0
    for i in range(len(df)):
        if st == 1 and (c[i] > sma5[i] or r[i] > 70): st = 0
        elif st == -1 and (c[i] < sma5[i] or r[i] < 30): st = 0
        if st == 0:
            if c[i] > e[i] and r[i] < lo: st = 1
            elif c[i] < e[i] and r[i] > 100-lo: st = -1
        out[i] = st
    return pd.Series(out, df.index)

def supertrend(df, n=10, mult=3.0):
    a = atr(df, n).values; hl2 = ((df.high+df.low)/2).values; c = df.close.values
    ub, lb = hl2+mult*a, hl2-mult*a; fu, fl = ub.copy(), lb.copy(); d = np.ones(len(df))
    for i in range(1, len(df)):
        fu[i] = ub[i] if (ub[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = lb[i] if (lb[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        d[i] = 1 if c[i] > fu[i-1] else (-1 if c[i] < fl[i-1] else d[i-1])
    return pd.Series(d, df.index)

def bb_breakout(df, n=20, k=2.0):
    """Long on close above upper band, hold until close < middle; short mirrored."""
    m, sd, c = df.close.rolling(n).mean().values, df.close.rolling(n).std().values, df.close.values
    out = np.zeros(len(df)); st = 0
    for i in range(len(df)):
        if np.isnan(m[i]): continue
        if st == 1 and c[i] < m[i]: st = 0
        if st == -1 and c[i] > m[i]: st = 0
        if st == 0:
            if c[i] > m[i]+k*sd[i]: st = 1
            elif c[i] < m[i]-k*sd[i]: st = -1
        out[i] = st
    return pd.Series(out, df.index)

def donchian_ensemble(df, days=(5, 10, 20, 30, 60), bars_per_day=None, thresh=0.5):
    """Zarattini/Pagani/Barbon-style ensemble: each lookback is long when close breaks its N-day high and
    stays long until close falls below the channel midline; shorts mirrored. Vote = sign of the average state
    when |avg| >= thresh (i.e. clear majority of lookbacks agree)."""
    bars_per_day = bars_per_day or BARS_PER_DAY; c = df.close.values; states = []
    for d in days:
        n = d*bars_per_day
        hi = df.high.rolling(n).max().shift(1).values; lo = df.low.rolling(n).min().shift(1).values; mid = (hi+lo)/2
        st = 0; out = np.zeros(len(df))
        for i in range(len(df)):
            if np.isnan(hi[i]): continue
            if st == 1 and c[i] < mid[i]: st = 0
            if st == -1 and c[i] > mid[i]: st = 0
            if st == 0:
                if c[i] > hi[i]: st = 1
                elif c[i] < lo[i]: st = -1
            out[i] = st
        states.append(out)
    avg = np.mean(states, axis=0)
    return pd.Series(np.where(avg >= thresh, 1, np.where(avg <= -thresh, -1, 0)), df.index)

def tsmom(df, days=30, bars_per_day=None, vol_days=30, min_z=0.5):
    """Time-series momentum: sign of the 30-day return, only when it is large vs recent volatility (z >= 0.5)."""
    bars_per_day = bars_per_day or BARS_PER_DAY; n = days*bars_per_day; r = np.log(df.close).diff()
    mom = r.rolling(n).sum(); vol = r.rolling(vol_days*bars_per_day).std()*np.sqrt(n)
    z = mom/vol
    return pd.Series(np.where(z >= min_z, 1, np.where(z <= -min_z, -1, 0)), df.index).fillna(0)

# 2026-10-24 user-approved swap: BB breakout -> Donchian ensemble, RSI(2) -> 30d time-series momentum (old funcs kept above)
OLD_STRATS = {"ema50_200": ema_trend, "rsi2_mr": rsi2_mr, "supertrend": supertrend, "bb_breakout": bb_breakout}
STRATS = {"ema50_200": ema_trend, "supertrend": supertrend, "donchian_ens": donchian_ensemble, "tsmom30d": tsmom}

def combine(votes: dict, min_agree=2):
    """+1 if >=min_agree long and none short; -1 mirrored; else 0."""
    v = list(votes.values()); L, S = v.count(1), v.count(-1)
    return 1 if (L >= min_agree and S == 0) else (-1 if (S >= min_agree and L == 0) else 0)

def evaluate(df, min_agree=2):
    """Votes and combined signal on the last two CLOSED candles."""
    sigs = {k: f(df) for k, f in STRATS.items()}
    now = {k: int(s.iat[-1]) for k, s in sigs.items()}; prev = {k: int(s.iat[-2]) for k, s in sigs.items()}
    return now, combine(now, min_agree), combine(prev, min_agree)
