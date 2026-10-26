#!/usr/bin/env python3
"""Swing study (PAPER research only). Long-only spot, 4h + 1d Binance USDT candles (data/sw_candles, sw_fetch.py).
Pre-registered textbook rules + one-step neighbour sweep (NOT optimised):
 (a) EMA20/50 cross-up entry, exit on ATR14 trailing stop = highest close since entry - k*ATR (k 2/3/4, pre-reg 3)
 (b) Donchian: close > prior N-bar high -> buy; close < prior M-bar low -> sell (N 15/20/30 x M 7/10/15, pre-reg 20/10)
 (c) RSI(2) Connors: close > 200-day SMA and RSI2 < X -> buy; exit RSI2 > 70 or close > SMA5 (X 5/10/15, pre-reg 10)
Signals on bar close, fills at NEXT bar open (no lookahead). ATR stop: intrabar, fill min(open, stop) (gap-through).
Costs: lo 0.15%/side + 2*$50/liq; hi 0.30%/side + 2*$50/liq + 0.10% extra on stop fills.
Eval window: common 2024-03-05 (WIF listing) .. last bar, indicators warmed up on full history. Holdout = last 30% of that window."""
import json, os, datetime as dt
import numpy as np, pandas as pd
LAB = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(LAB, "data", "sw_candles"); OUT = os.path.join(LAB, "out")
SYMS = ["SOL", "JUP", "BONK", "WIF", "JTO", "PYTH", "RAY"]
LIQ = {"SOL": 30e6}; TICKET = 50.0
BARS_PER_DAY = {"4h": 6, "1d": 1}
RNG = np.random.default_rng(11)

def load(sym, tf):
    df = pd.read_csv(os.path.join(D, f"bn_{sym}_{tf}.csv"))
    df["t"] = pd.to_datetime(df.ts, unit="ms", utc=True)
    return df.set_index("t")[["o", "h", "l", "c", "vq"]].astype(float)

EVAL_START = pd.Timestamp("2024-03-05", tz="UTC")
def window(tf):
    end = load("SOL", tf).index[-1]
    split = EVAL_START + (end - EVAL_START) * 0.70
    return EVAL_START, split.floor("D"), end

def rsi(c, n):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def atr(df, n=14):
    pc = df.c.shift(); tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def cost_side(sym, cost):
    base = 0.0015 if cost == "lo" else 0.0030
    return base + 2 * TICKET / LIQ.get(sym, 2e6)

def gen(df, sym, cfg, cost, start, end):
    """-> list of trades {sym,t_in,t_out,px_in,px_out,ret,exit,bars} for entries in [start, end]."""
    o, h, l, c = df.o.values, df.h.values, df.l.values, df.c.values; idx = df.index; n = len(df)
    fam = cfg["fam"]; tf = cfg["tf"]; cs = cost_side(sym, cost)
    if fam == "ema":
        e20 = df.c.ewm(span=20, adjust=False).mean().values; e50 = df.c.ewm(span=50, adjust=False).mean().values
        a = atr(df).values; ok = np.arange(n) >= 60
        sig = np.r_[False, (e20[1:] > e50[1:]) & (e20[:-1] <= e50[:-1])] & ok
    elif fam == "don":
        hh = df.h.rolling(cfg["N"]).max().shift(1).values; ll = df.l.rolling(cfg["M"]).min().shift(1).values
        sig = c > hh; xit = c < ll
    elif fam == "rsi":
        r2 = rsi(df.c, 2).values; s5 = df.c.rolling(5).mean().values
        s200 = df.c.rolling(200 * BARS_PER_DAY[tf]).mean().values
        sig = (c > s200) & (r2 < cfg["X"]); xit = (r2 > 70) | (c > s5)
    tr = []; i = 0
    while i < n - 1:
        if not (sig[i] and start <= idx[i + 1] <= end): i += 1; continue
        j = i + 1; pin = o[j]; ex = None
        if fam == "ema":
            hc = c[j]; stop = None
            k = j
            while k < n:
                if stop is not None and l[k] <= stop:
                    ex = (k, min(o[k], stop), "stop"); break
                hc = max(hc, c[k]); stop = hc - cfg["k"] * a[k]
                k += 1
        else:
            k = j
            while k < n - 1:
                if xit[k]: ex = (k + 1, o[k + 1], "rule"); break
                k += 1
        if ex is None: ex = (n - 1, c[n - 1], "eod")
        kx, px, why = ex
        extra = 0.001 if (cost == "hi" and why == "stop") else 0.0
        ret = px * (1 - cs - extra) / (pin * (1 + cs)) - 1
        tr.append({"sym": sym, "t_in": idx[j], "t_out": idx[kx], "px_in": pin, "px_out": px, "ret": ret, "exit": why,
                   "bars": kx - j, "gross": px / pin - 1})
        i = kx if why != "rule" else kx - 1   # can re-signal on the exit bar's close earliest
        i = max(i, j)
        i += 0 if why == "rule" else 0
        if why == "eod": break
    return tr

def equity_token(df, trades, start, end, cs):
    """Fully-invested per-token MTM equity on bar closes within [start,end] -> (total, maxdd, exposure, cagr)."""
    sub = df.loc[start:end]; eq = np.ones(len(sub)); inpos = np.zeros(len(sub), bool)
    pos = {t: k for k, t in enumerate(sub.index)}; e = 1.0; last = 0
    cur = 1.0
    for t in trades:
        if t["t_in"] not in pos: continue
        a = pos[t["t_in"]]; b = pos.get(t["t_out"], len(sub) - 1)
        eq[last:a] = cur
        seg = sub.c.values[a:b] / t["px_in"] / (1 + cs) * cur
        eq[a:b] = seg; inpos[a:b] = True
        cur = cur * (1 + t["ret"]); eq[b:] = cur; last = b
    eq[last:] = cur
    pk = np.maximum.accumulate(np.r_[1.0, eq]); dd = float(np.max(1 - np.r_[1.0, eq] / pk))
    days = max(1, (sub.index[-1] - sub.index[0]).days)
    return {"total": cur - 1, "maxdd": dd, "exposure": float(inpos.mean()), "cagr": cur ** (365 / days) - 1}

def bh(df, start, end, cs):
    sub = df.loc[start:end]; p = sub.c.values / sub.o.values[0] / (1 + cs)
    tot = p[-1] * (1 - cs) - 1; pk = np.maximum.accumulate(np.r_[1 / (1 + cs), p]); dd = float(np.max(1 - np.r_[1 / (1 + cs), p] / pk))
    days = max(1, (sub.index[-1] - sub.index[0]).days)
    return {"total": tot, "maxdd": dd, "cagr": (1 + tot) ** (365 / days) - 1, "exposure": 1.0}

def book(trades, size=0.10, maxopen=3):
    """Equal-weight book across tokens: entries in time order (tie: SYMS order), max open, size = fraction of realised equity."""
    order = {s: k for k, s in enumerate(SYMS)}
    tr = sorted(trades, key=lambda t: (t["t_in"], order[t["sym"]])); openp = []; eq = 1.0; taken = []
    for t in tr:
        for p in [p for p in openp if p["t_out"] <= t["t_in"]]: eq += p["stake"] * p["ret"]; openp.remove(p)
        if len(openp) >= maxopen: continue
        if any(p["sym"] == t["sym"] for p in openp): continue
        t = dict(t, stake=size * eq); openp.append(t); taken.append(t)
    return taken

def book_curve(taken, start, end):
    """Realised book equity (exit-time order) -> total, maxdd (realised), cagr, avg deployed fraction."""
    ev = sorted(taken, key=lambda t: t["t_out"]); eq = 1.0; curve = [1.0]
    for t in ev: eq += t["stake"] * t["ret"]; curve.append(eq)
    curve = np.array(curve); pk = np.maximum.accumulate(curve); dd = float(np.max(1 - curve / pk))
    days = max(1, (end - start).days)
    dep = sum(t["stake"] * (t["t_out"] - t["t_in"]).total_seconds() for t in taken) / ((end - start).total_seconds())
    return {"total": eq - 1, "maxdd": dd, "cagr": max(eq, 1e-9) ** (365 / days) - 1, "deployed": dep}

def stats(rets):
    r = np.array(rets)
    if len(r) == 0: return {"n": 0, "mean": None, "lo": None, "hi": None, "med": None, "win": None}
    b = RNG.choice(r, (2000, len(r))).mean(1) if len(r) > 1 else np.array([r[0]])
    return {"n": len(r), "mean": float(r.mean()), "lo": float(np.percentile(b, 2.5)), "hi": float(np.percentile(b, 97.5)),
            "med": float(np.median(r)), "win": float((r > 0).mean())}

def grid():
    V = []
    for tf in ("4h", "1d"):
        for k in (2, 3, 4): V.append({"fam": "ema", "tf": tf, "k": k, "prereg": k == 3, "name": f"SW_ema_{tf}_k{k}"})
        for N in (15, 20, 30):
            for M in (7, 10, 15): V.append({"fam": "don", "tf": tf, "N": N, "M": M, "prereg": (N, M) == (20, 10), "name": f"SW_don_{tf}_N{N}_M{M}"})
        for X in (5, 10, 15): V.append({"fam": "rsi", "tf": tf, "X": X, "prereg": X == 10, "name": f"SW_rsi2_{tf}_X{X}"})
    return V

def run():
    data = {tf: {s: load(s, tf) for s in SYMS} for tf in ("4h", "1d")}
    res = {}
    for cfg in grid():
        tf = cfg["tf"]; start, split, end = window(tf)
        for cost in ("lo", "hi"):
            allt = []; per = {}
            for s in SYMS:
                df = data[tf][s]; tr = gen(df, s, cfg, cost, start, end)
                for t in tr: t["is_oos"] = t["t_in"] >= split
                allt += tr
                cs = cost_side(s, cost)
                per[s] = {w: equity_token(df, [t for t in tr if (t["t_in"] >= split) == (w == "oos")], *( (start, split) if w == "is" else (split, end)), cs)
                          for w in ("is", "oos")}
                per[s]["full"] = equity_token(df, tr, start, end, cs)
                per[s]["n"] = {"is": sum(not t["is_oos"] for t in tr), "oos": sum(t["is_oos"] for t in tr)}
            res[(cfg["name"], cost)] = {"cfg": cfg, "trades": allt, "per": per}
    bhs = {}
    for tf in ("4h", "1d"):
        start, split, end = window(tf)
        for s in SYMS:
            cs = cost_side(s, "hi")
            bhs[(tf, s)] = {"is": bh(data[tf][s], start, split, cs), "oos": bh(data[tf][s], split, end, cs), "full": bh(data[tf][s], start, end, cs)}
    return data, res, bhs

if __name__ == "__main__":
    data, res, bhs = run()
    for (name, cost), r in res.items():
        if cost != "hi": continue
        tr = r["trades"]; i = stats([t["ret"] for t in tr if not t["is_oos"]]); o = stats([t["ret"] for t in tr if t["is_oos"]])
        f = lambda s: "n/a" if s["n"] == 0 else f"n={s['n']:3d} mean {s['mean']*100:+.2f}% med {s['med']*100:+.2f}% win {s['win']:.0%}"
        print(f"{name:24s} IS {f(i)} | OOS {f(o)}")
    for tf in ("4h", "1d"): print(tf, window(tf)); print({s: round(bhs[(tf, s)]["oos"]["total"], 3) for s in SYMS})
