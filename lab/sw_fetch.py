#!/usr/bin/env python3
"""Swing study candle fetcher (PAPER research). Full-history Binance spot klines <SYM>USDT, 4h and 1d,
from data-api.binance.vision (free, public). Cache: data/sw_candles/bn_<SYM>_<tf>.csv (ts=bar open ms UTC,o,h,l,c,vq).
Only closed bars are stored. Resumable."""
import csv, json, os, time, urllib.request
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sw_candles"); os.makedirs(D, exist_ok=True)
SYMS = ["SOL", "JUP", "BONK", "WIF", "JTO", "PYTH", "RAY"]
MS = {"4h": 4 * 3600_000, "1d": 86400_000}
NOW = int(time.time() * 1000)
def get(url):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lab-sw/1.0"}), timeout=30) as r: return json.load(r)
        except Exception as e: print("ERR", url, e, flush=True); time.sleep(2 * (a + 1))
    return None
for s in SYMS:
    for tf in MS:
        p = os.path.join(D, f"bn_{s}_{tf}.csv"); rows = {}
        if os.path.exists(p): rows = {int(r["ts"]): r for r in csv.DictReader(open(p))}
        start = max(rows) + MS[tf] if rows else 0
        while True:
            k = get(f"https://data-api.binance.vision/api/v3/klines?symbol={s}USDT&interval={tf}&startTime={start}&limit=1000"); time.sleep(0.3)
            if not k: break
            for b in k:
                if b[6] < NOW: rows[int(b[0])] = {"ts": int(b[0]), "o": b[1], "h": b[2], "l": b[3], "c": b[4], "vq": b[7]}
            if len(k) < 1000: break
            start = int(k[-1][0]) + MS[tf]
        with open(p + ".tmp", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["ts", "o", "h", "l", "c", "vq"]); w.writeheader()
            for t in sorted(rows): w.writerow(rows[t])
        os.replace(p + ".tmp", p)
        ks = sorted(rows); print(s, tf, len(rows), time.strftime("%Y-%m-%d", time.gmtime(ks[0] / 1000)) if ks else "-", flush=True)
