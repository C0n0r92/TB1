#!/usr/bin/env python3
"""Binance public spot klines (data-api.binance.vision, free, no key) -> data/<SYM>_<tf>.csv (t_ms,o,h,l,c,v,qv). PAPER research."""
import csv, json, os, sys, time, urllib.request, datetime as dt
BASE = "https://data-api.binance.vision/api/v3/klines"
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MS = {"15m": 900_000, "1h": 3_600_000, "5m": 300_000}
def fetch(sym, tf, start_ms, end_ms):
    f = os.path.join(D, f"{sym}_{tf}.csv"); rows = []
    while start_ms < end_ms:
        u = f"{BASE}?symbol={sym}USDT&interval={tf}&startTime={start_ms}&endTime={end_ms}&limit=1000"
        d = None
        for k in range(5):
            try: d = json.load(urllib.request.urlopen(u, timeout=30)); break
            except Exception as e: print("ERR", sym, tf, e, flush=True); time.sleep(2 + 3 * k)
        if not d: break
        rows += [[x[0], x[1], x[2], x[3], x[4], x[5], x[7]] for x in d]
        start_ms = d[-1][0] + MS[tf]; time.sleep(0.3)
        if len(d) < 1000: break
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["t_ms", "o", "h", "l", "c", "v", "qv"]); w.writerows(rows)
    return len(rows)
if __name__ == "__main__":
    end = int(dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc).timestamp() * 1000)
    syms = ["SOL", "JUP", "BONK", "WIF", "JTO", "PYTH", "RAY", "RENDER", "BTC"]
    for tf, days in [("1h", 730), ("15m", 270), ("5m", 120)]:
        for s in syms: print(s, tf, fetch(s, tf, end - days * 86400_000, end), flush=True)
