"""Fetch SOLUSDT klines from Binance public market-data mirror (data-api.binance.vision; read-only, no key).
api.binance.com returns 451 (restricted location) from this box, so the official public mirror is used.
Cross-check: Coinbase Exchange SOL-USD 1h public candles. Cached per request; 0.6 s spacing."""
import json, os, time, urllib.request, hashlib, sys
import pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(ROOT, "cache")
UA = {"User-Agent": "lab-paper-research/0.1"}
DAYS = int(os.environ.get("DAYS", "730"))
def get(url, final):
    k = hashlib.sha1(url.encode()).hexdigest(); p = os.path.join(CACHE, k + ".json")
    if os.path.exists(p): return json.load(open(p))
    for i in range(4):
        time.sleep(0.6)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r: d = json.loads(r.read())
            if final: json.dump(d, open(p, "w"))
            return d
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(5 * (i + 1))
    raise RuntimeError(url)
MS = {"5m": 300e3, "15m": 900e3, "1h": 3600e3, "4h": 14400e3}
def binance(iv):
    end = int(time.time() * 1000); start = end - DAYS * 86400 * 1000; rows = []; t = start
    while t < end:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol=SOLUSDT&interval={iv}&startTime={t}&limit=1000"
        final = t + 1000 * MS[iv] < end - 86400e3
        d = get(url, final)
        if not d: break
        rows += d; t = int(d[-1][0] + MS[iv])
        if len(d) < 1000: break
    df = pd.DataFrame(rows, columns="t o h l c v ct qv n tbv tqv x".split())[["t","o","h","l","c","v","qv","n"]]
    df = df.astype(float).drop_duplicates("t").sort_values("t")
    df = df[df.t + MS[iv] <= time.time() * 1000]  # closed bars only
    df["t"] = df.t.astype("int64")
    gaps = (df.t.diff() != MS[iv]).sum() - 1
    df.to_csv(os.path.join(ROOT, "data", f"SOLUSDT_{iv}.csv"), index=False)
    print(iv, len(df), pd.to_datetime(df.t.iloc[0], unit="ms"), pd.to_datetime(df.t.iloc[-1], unit="ms"), "gaps", gaps, flush=True)
def coinbase_1h():
    end = int(time.time()) // 3600 * 3600; start = end - 365 * 86400; rows = []; t = start
    while t < end:
        e = min(t + 300 * 3600, end)
        url = f"https://api.exchange.coinbase.com/products/SOL-USD/candles?granularity=3600&start={t}&end={e}"
        rows += get(url, e < end - 86400); t = e
    df = pd.DataFrame(rows, columns="t l h o c v".split()).drop_duplicates("t").sort_values("t")
    df.to_csv(os.path.join(ROOT, "data", "COINBASE_SOLUSD_1h.csv"), index=False); print("coinbase 1h", len(df))
if __name__ == "__main__":
    for iv in ["4h", "1h", "15m", "5m"]: binance(iv)
    coinbase_1h()
