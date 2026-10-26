#!/usr/bin/env python3
"""Mean-reversion study candle fetcher (PAPER research). Cache: data/mr_candles/<src>_<SYM>_<tf>.csv
columns: ts (bar open, unix ms UTC), o, h, l, c, vq (quote volume USD/USDT). Resumable (re-run continues).
Binance: data-api.binance.vision spot klines <SYM>USDT (0.25 s spacing, separate from the shared Gecko/DS budget).
GeckoTerminal: top Solana pool OHLCV, 16 s spacing (<=4 req/min), own call log data/mr_candles/.gt_calls.log."""
import csv, json, os, sys, time, urllib.request
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mr_candles"); os.makedirs(D, exist_ok=True)
NOW = int(time.time() * 1000)
DAY = 86400_000
BIN = ["SOL", "PUMP", "PENGU", "TRUMP", "BONK", "JUP", "RENDER", "WIF", "PYTH", "RAY", "JTO", "W", "KMNO", "BOME"]
GT = {"FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump", "POPCAT": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
      "MEW": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "GRASS": "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs",
      "USELESS": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk"}
SPAN = {"1h": 365 * DAY, "15m": 92 * DAY, "5m": 92 * DAY}
GTSPAN = {"1h": 183 * DAY, "5m": 92 * DAY}          # 15m for GT tokens is resampled from 5m
MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}

def get(url, spacing):
    last = getattr(get, "last", {}); k = spacing
    wait = last.get(k, 0) + spacing - time.time()
    if wait > 0: time.sleep(wait)
    for a in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lab-mr/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: out = json.load(r)
            last[k] = time.time(); get.last = last
            if spacing > 5: open(os.path.join(D, ".gt_calls.log"), "a").write(f"{int(time.time())} {url}\n")
            return out
        except Exception as e:
            last[k] = time.time(); get.last = last
            print("ERR", url, e, flush=True); time.sleep(spacing * (a + 1) + (60 if "429" in str(e) else 0))
    return None

def load(p):
    if not os.path.exists(p): return {}
    return {int(r["ts"]): r for r in csv.DictReader(open(p))}

def save(p, rows):
    with open(p + ".tmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ts", "o", "h", "l", "c", "vq"]); w.writeheader()
        for k in sorted(rows): w.writerow({f: rows[k][f] for f in ["ts", "o", "h", "l", "c", "vq"]})
    os.replace(p + ".tmp", p)

def binance(sym, tf):
    p = os.path.join(D, f"bn_{sym}_{tf}.csv"); rows = load(p)
    start = max(rows) + MS[tf] if rows else NOW - SPAN[tf]
    while start < NOW - MS[tf]:
        k = get(f"https://data-api.binance.vision/api/v3/klines?symbol={sym}USDT&interval={tf}&startTime={start}&limit=1000", 0.25)
        if not k: break
        for b in k:
            if b[6] < NOW: rows[int(b[0])] = {"ts": int(b[0]), "o": b[1], "h": b[2], "l": b[3], "c": b[4], "vq": b[7]}
        if len(k) < 1000: break
        start = int(k[-1][0]) + MS[tf]
    save(p, rows); print("bn", sym, tf, len(rows), flush=True)

def gt(sym, mint):
    meta_p = os.path.join(D, f"gt_{sym}_pool.json")
    if os.path.exists(meta_p): meta = json.load(open(meta_p))
    else:
        r = get(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint}/pools?page=1", 16)
        pools = sorted(r["data"], key=lambda x: float(x["attributes"].get("reserve_in_usd") or 0), reverse=True)
        top = pools[0]; meta = {"pool": top["attributes"]["address"], "name": top["attributes"]["name"],
                                "reserve_usd": top["attributes"]["reserve_in_usd"], "base": top["relationships"]["base_token"]["data"]["id"]}
        json.dump(meta, open(meta_p, "w")); print("gt pool", sym, meta, flush=True)
    for tf, (tfp, agg) in {"1h": ("hour", 1), "5m": ("minute", 5)}.items():
        p = os.path.join(D, f"gt_{sym}_{tf}.csv"); rows = load(p); done_p = p + ".done"
        if os.path.exists(done_p): continue
        before = (min(rows) // 1000) if rows else NOW // 1000
        tok = "base" if meta["base"].endswith(mint) else "quote"
        while before * 1000 > NOW - GTSPAN[tf]:
            r = get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{meta['pool']}/ohlcv/{tfp}?aggregate={agg}"
                    f"&before_timestamp={before}&limit=1000&currency=usd&token={tok}", 16)
            lst = (r or {}).get("data", {}).get("attributes", {}).get("ohlcv_list", []) if r else []
            if not lst: break
            for t, o, h, l, c, v in lst:
                if t * 1000 + MS[tf] <= NOW: rows[t * 1000] = {"ts": t * 1000, "o": o, "h": h, "l": l, "c": c, "vq": v}
            save(p, rows)
            nb = min(x[0] for x in lst)
            if nb >= before or len(lst) < 1000: break
            before = nb
        open(done_p, "w").write(str(len(rows))); print("gt", sym, tf, len(rows), flush=True)

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("bn", "all"):
        for s in BIN:
            for tf in ("1h", "15m", "5m"): binance(s, tf)
    if which in ("gt", "all"):
        for s, m in GT.items(): gt(s, m)
