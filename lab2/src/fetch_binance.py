#!/usr/bin/env python3
"""Fetch Binance public spot klines (data-api.binance.vision, no key) -> data/binance/<SYM>_<tf>.csv.
Free public endpoint; ~0.25 s spacing. Resumes from the last cached bar."""
import csv, json, os, sys, time, urllib.request
BASE = "https://data-api.binance.vision/api/v3/klines"
D = os.path.join(os.path.dirname(__file__), "..", "data", "binance")
MS = {"15m": 900_000, "1h": 3_600_000, "5m": 300_000}
def fetch(sym, tf, start_ms, end_ms):
    f = os.path.join(D, f"{sym}_{tf}.csv"); rows = []
    if os.path.exists(f):
        rows = [r for r in csv.reader(open(f))][1:]
        if rows: start_ms = int(rows[-1][0]) + MS[tf]
    while start_ms < end_ms:
        u = f"{BASE}?symbol={sym}USDT&interval={tf}&startTime={start_ms}&endTime={end_ms}&limit=1000"
        for k in range(5):
            try: d = json.load(urllib.request.urlopen(u, timeout=30)); break
            except Exception as e: time.sleep(2 + 3 * k); d = None
        if not d: break
        rows += [[x[0], x[1], x[2], x[3], x[4], x[5], x[7]] for x in d]   # open_ms,o,h,l,c,base_vol,quote_vol
        start_ms = d[-1][0] + MS[tf]; time.sleep(0.25)
        if len(d) < 1000: break
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["t_ms", "o", "h", "l", "c", "v", "qv"]); w.writerows(rows)
    return len(rows)
if __name__ == "__main__":
    import datetime as dt
    syms = sys.argv[1].split(","); tf = sys.argv[2]; days = int(sys.argv[3])
    end = int(dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc).timestamp() * 1000)
    for s in syms: print(s, tf, fetch(s, tf, end - days * 86400_000, end), flush=True)
