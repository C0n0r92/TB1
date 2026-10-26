"""Reusable candle loader for Lab 2 (read-only on Lab's caches).
All frames: index = bar CLOSE time (UTC, tz-aware), columns o,h,l,c,v (v in quote/USD where available).
Using close time as the index means a value at index t is known at t (no look-ahead when aligning)."""
import csv, glob, json, os
import pandas as pd
LAB2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN = os.path.join(LAB2, "data", "binance")
MID = "/workspace/lab/data/midcap"                    # Lab's older-coins cache (GeckoTerminal), READ ONLY
CUTOFF = pd.Timestamp("2026-10-24 00:00", tz="UTC")   # drop the still-forming bar
SEC = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}

def _frame(T, O, H, L, C, V, tf):
    idx = pd.to_datetime([int(t) + SEC[tf] for t in T], unit="s", utc=True)
    df = pd.DataFrame({"o": O, "h": H, "l": L, "c": C, "v": V}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[(df.c > 0) & (df.index <= CUTOFF)]

def binance(sym, tf):
    """Binance public spot klines SYMUSDT (fetched by fetch_binance.py)."""
    f = os.path.join(BIN, f"{sym}_{tf}.csv")
    r = list(csv.reader(open(f)))[1:]
    return _frame([int(x[0]) // 1000 for x in r], *[[float(x[k]) for x in r] for k in (1, 2, 3, 4)], [float(x[6]) for x in r], tf)

def lab_meta():
    return {p["mint"]: p for p in json.load(open(os.path.join(MID, "prefilter.json")))}

def lab_midcap(tf):
    """Lab's GeckoTerminal OHLCV for the older-coins universe -> {symbol: (mint, df)}. tf in 1h|15m. Timestamps are bar opens (Gecko)."""
    meta = lab_meta(); pre = "rows_" if tf == "1h" else "rows15_"; out = {}
    for f in glob.glob(os.path.join(MID, "ohlcv", pre + "*.json")):
        m = os.path.basename(f)[len(pre):-5]
        rows = json.load(open(f))
        if len(rows) < 200: continue
        sym = "SOL" if m == "SOL" else (meta.get(m, {}).get("symbol") or m[:6])
        df = _frame(*[[r[k] for r in rows] for k in range(6)], tf)
        if sym in out and len(out[sym][1]) >= len(df): continue
        out[sym] = (m, df)
    return out

def resample(df, rule):
    """Resample a close-indexed frame; label = right edge so the bar is known at its index."""
    g = df.resample(rule, label="right", closed="right")
    return pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "v": g.v.sum()}).dropna()
