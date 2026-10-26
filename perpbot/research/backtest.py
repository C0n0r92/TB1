"""Blended leveraged perp backtest (research only). Closed-candle signals, next-bar-open entries,
ATR stop resting on exchange (intrabar fill, gap-aware), 1% equity risk/trade, 3x leverage cap,
0.05% taker + 0.02% slippage per side, real 8h funding history (Binance public archive as price proxy).
Walk-forward: params tuned on first 70% only; last 30% reported out-of-sample with fresh equity."""
import numpy as np, pandas as pd, itertools, json, sys
FEE, SLIP, RISK, LEV, ATR_N = 0.00045, 0.0002, 0.01, 3.0, 14
SYMS = ["BTCUSDT", "SOLUSDT"]; SPLIT = 0.70

def load(sym, tf):
    """Hyperliquid candles (4h: full history; 1h: HL API keeps only ~5000 bars, so older 1h uses Binance perp
    as a price proxy, spliced). Funding = Hyperliquid hourly history, summed over each bar and charged at next bar open
    against the position held through that bar."""
    hl = pd.read_csv(f"data/HL_{sym}_{tf}.csv", parse_dates=["ts"]).set_index("ts")
    if tf == "1h":
        bn = pd.read_csv(f"data/{sym}_{tf}.csv", parse_dates=["ts"]).set_index("ts")
        hl = pd.concat([bn[bn.index < hl.index[0]], hl])
    df = hl[~hl.index.duplicated()].sort_index()
    f = pd.read_csv(f"data/HL_{sym}_funding.csv"); f["ts"] = pd.to_datetime(f.ts, utc=True, format="mixed").dt.floor("h")
    f["bar"] = f.ts.dt.ceil(tf); f.loc[f.bar == f.ts, "bar"] += pd.Timedelta(tf)  # funding at T paid by position held at T
    df["fund"] = f.groupby("bar").rate.sum().reindex(df.index).fillna(0.0)
    return df

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(df, n=ATR_N):
    pc = df.close.shift()
    tr = pd.concat([df.high-df.low, (df.high-pc).abs(), (df.low-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()
def rsi(s, n):
    d = s.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn.replace(0, 1e-12))

# ---- strategies: return desired direction per CLOSED bar (+1/0/-1); acted on at next open ----
def s_ema(df, fast=50, slow=200):
    ef, es = ema(df.close, fast), ema(df.close, slow)
    d = np.where((ef > es) & (df.close > es), 1, np.where((ef < es) & (df.close < es), -1, 0))
    return pd.Series(d, df.index)
def s_rsi(df, lo=10, ema_n=200):
    r, e, sma5 = rsi(df.close, 2), ema(df.close, ema_n), df.close.rolling(5).mean()
    c = df.close.values; out = np.zeros(len(df)); st = 0
    for i in range(len(df)):
        if st == 1 and (c[i] > sma5.iat[i] or r.iat[i] > 70): st = 0
        elif st == -1 and (c[i] < sma5.iat[i] or r.iat[i] < 30): st = 0
        if st == 0:
            if c[i] > e.iat[i] and r.iat[i] < lo: st = 1
            elif c[i] < e.iat[i] and r.iat[i] > 100-lo: st = -1
        out[i] = st
    return pd.Series(out, df.index)
def s_st(df, n=10, mult=3.0):
    a = atr(df, n).values; hl2 = ((df.high+df.low)/2).values; c = df.close.values
    ub, lb = hl2+mult*a, hl2-mult*a; fu, fl = ub.copy(), lb.copy(); d = np.ones(len(df))
    for i in range(1, len(df)):
        fu[i] = ub[i] if (ub[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = lb[i] if (lb[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        d[i] = 1 if c[i] > fu[i-1] else (-1 if c[i] < fl[i-1] else d[i-1])
    return pd.Series(d, df.index)
def s_bb(df, n=20, k=2.0):
    m = df.close.rolling(n).mean(); sd = df.close.rolling(n).std(); c = df.close.values
    out = np.zeros(len(df)); st = 0
    for i in range(len(df)):
        if np.isnan(m.iat[i]): continue
        if st == 1 and c[i] < m.iat[i]: st = 0
        if st == -1 and c[i] > m.iat[i]: st = 0
        if st == 0:
            if c[i] > m.iat[i]+k*sd.iat[i]: st = 1
            elif c[i] < m.iat[i]-k*sd.iat[i]: st = -1
        out[i] = st
    return pd.Series(out, df.index)
STRATS = {"EMA50/200": s_ema, "RSI2-MR": s_rsi, "Supertrend": s_st, "BB-breakout": s_bb}
GRID = {"EMA50/200": [dict(fast=50, slow=200), dict(fast=20, slow=100)],
        "RSI2-MR": [dict(lo=10), dict(lo=5)],
        "Supertrend": [dict(n=10, mult=3.0)],  # spec'd params fixed
        "BB-breakout": [dict(n=20, k=2.0)]}
TFS = ["1h", "4h"]; STOPS = [1.5, 2.5, 4.0]

def simulate(df, d, stop_mult, start, end):
    """Event loop over bars [start,end). d = desired dir decided at close of bar i -> act at open of i+1."""
    o, h, l, c, fu = (df[x].values for x in ["open","high","low","close","fund"])
    a = atr(df).values; dv = d.values; idx = df.index
    eq = 1.0; pos = 0; qty = 0.0; ent = stop = 0.0; eq_ent = 0.0; trades = []; curve = []
    cost = FEE + SLIP
    for i in range(start, end):
        sig = dv[i-1]; prev = dv[i-2] if i >= 2 else 0
        if pos != 0 and fu[i] != 0: eq -= pos*qty*o[i]*fu[i]          # funding at bar open
        if pos != 0 and sig != pos:                                       # signal exit at open
            px = o[i]*(1-pos*SLIP); eq += pos*qty*(px-ent) - qty*px*FEE
            trades.append(eq/eq_ent-1); pos = 0
        if pos == 0 and sig != 0 and sig != prev and not np.isnan(a[i-1]):  # fresh signal entry
            dist = stop_mult*a[i-1]; px = o[i]*(1+sig*SLIP)
            qty = min(RISK*eq/dist, LEV*eq/px); eq_ent = eq
            eq -= qty*px*FEE; pos = sig; ent = px; stop = px - sig*dist
        if pos != 0:                                                      # resting stop, gap-aware
            hit = (pos == 1 and l[i] <= stop) or (pos == -1 and h[i] >= stop)
            if hit:
                fill = (min(o[i], stop) if pos == 1 else max(o[i], stop)) * (1-pos*SLIP)
                eq += pos*qty*(fill-ent) - qty*fill*FEE; trades.append(eq/eq_ent-1); pos = 0
        curve.append(eq + (pos*qty*(c[i]-ent) - qty*c[i]*FEE if pos else 0))
    if pos != 0:  # close at end
        px = c[end-1]*(1-pos*SLIP); eq += pos*qty*(px-ent) - qty*px*FEE; trades.append(eq/eq_ent-1); curve[-1] = eq
    return pd.Series(curve, idx[start:end]), trades

def bounds(df):
    n = len(df); s = int(n*SPLIT); return (210, s), (s, n)  # 210-bar warmup

def metrics(curve, trades):
    t = np.array(trades) if trades else np.array([0.0])
    gp, gl = t[t > 0].sum(), -t[t < 0].sum()
    dd = (curve/curve.cummax()-1).min()
    return dict(ret=curve.iat[-1]/curve.iat[0]-1 if len(curve) else 0, maxdd=dd, n=len(trades),
                win=(t > 0).mean() if trades else 0, pf=gp/gl if gl > 0 else np.inf, avg=t.mean())

DATA = {(s, tf): load(s, tf) for s in SYMS for tf in TFS}
def book(sigfn, tf, stop_mult, part):
    """Equal-capital BTC+SOL book; returns combined curve (normalized start 1) and pooled trades."""
    curves, trades = [], []
    for s in SYMS:
        df = DATA[(s, tf)]; d = sigfn(df); (a0, a1), (b0, b1) = bounds(df)
        lo, hi = (a0, a1) if part == "IS" else (b0, b1)
        cv, tr = simulate(df, d, stop_mult, lo, hi); curves.append(cv/cv.iat[0]*0.5 if len(cv) else cv); trades += [x*0.5 for x in tr]
    cv = pd.concat(curves, axis=1).ffill().sum(axis=1)
    return cv, trades

def vote_fn(members, need):
    def f(df):
        v = sum(STRATS[m](df) for m in members)
        return pd.Series(np.where(v >= need, 1, np.where(v <= -need, -1, 0)), df.index)
    return f

if __name__ == "__main__":
    rows, chosen = [], {}
    def score(m): return m["ret"] if m["n"] >= 20 else -9
    cands = {k: [(lambda df, f=fn, p=p: f(df, **p), p) for p in GRID[k]] for k, fn in STRATS.items()}
    cands["Vote 2-of-3 (EMA,ST,BB)"] = [(vote_fn(["EMA50/200","Supertrend","BB-breakout"], 2), {})]
    cands["Vote 3-of-4 (all)"] = [(vote_fn(list(STRATS), 3), {})]
    tune_log = []
    for name, opts in cands.items():
        best = None
        for (fn, p), tf, sm in itertools.product(opts, TFS, STOPS):
            m = metrics(*book(fn, tf, sm, "IS")); tune_log.append(dict(strategy=name, params=str(p), tf=tf, stop_atr=sm, **m))
            if best is None or score(m) > score(best[0]): best = (m, fn, p, tf, sm)
        m_is, fn, p, tf, sm = best; m_oos = metrics(*book(fn, tf, sm, "OOS"))
        chosen[name] = (fn, tf, sm)
        rows.append(dict(strategy=name, cfg=f"{tf} stop={sm}xATR {p}", **{f"IS_{k}": v for k, v in m_is.items()}, **{f"OOS_{k}": v for k, v in m_oos.items()}))
    # equal-capital split across the 4 tuned single strategies (each 1/4, each BTC/SOL halves)
    for part in ["IS", "OOS"]:
        cs, ts = [], []
        for k in STRATS:
            fn, tf, sm = chosen[k]; cv, tr = book(fn, tf, sm, part); cs.append(cv/4); ts += [x/4 for x in tr]
        cv = pd.concat(cs, axis=1, sort=True).ffill().bfill().sum(axis=1); chosen[f"split_{part}"] = metrics(cv, ts)
    rows.append(dict(strategy="Equal-capital split (4)", cfg="each strat's tuned cfg",
                     **{f"IS_{k}": v for k, v in chosen["split_IS"].items()}, **{f"OOS_{k}": v for k, v in chosen["split_OOS"].items()}))
    res = pd.DataFrame(rows); res.to_csv("results.csv", index=False); pd.DataFrame(tune_log).to_csv("tuning_log.csv", index=False)
    df0 = DATA[("BTCUSDT","1h")]; (a0,a1),(b0,b1) = bounds(df0)
    print(f"IS {df0.index[a0]:%Y-%m-%d}..{df0.index[a1-1]:%Y-%m-%d} | OOS {df0.index[b0]:%Y-%m-%d}..{df0.index[b1-1]:%Y-%m-%d}")
    pd.set_option("display.width", 250); fmt = res.copy()
    for c in fmt.columns:
        if c.endswith(("ret","maxdd","win","avg")): fmt[c] = (fmt[c]*100).map("{:.2f}%".format)
        if c.endswith("pf"): fmt[c] = fmt[c].map("{:.2f}".format)
    print(fmt.to_string(index=False))
