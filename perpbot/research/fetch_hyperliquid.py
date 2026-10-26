"""Hyperliquid public info API (no wallet/key): candles (API keeps last ~5000 per interval) + hourly funding history."""
import json, time, urllib.request, pandas as pd
URL = "https://api.hyperliquid.xyz/info"
def post(body):
    for k in range(5):
        try:
            r = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(r, timeout=60).read())
        except Exception as e: print("retry", e); time.sleep(2+k*3)
    raise SystemExit("HL API failed")
START = int(pd.Timestamp("2024-10-01", tz="UTC").timestamp()*1000); NOW = int(time.time()*1000)
for coin, sym in [("BTC", "BTCUSDT"), ("SOL", "SOLUSDT")]:
    for tf, ms in [("1h", 3600e3), ("4h", 14400e3)]:
        rows, t = [], START
        while t < NOW:
            c = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": tf, "startTime": t, "endTime": NOW}})
            if not c: break
            rows += c; nt = c[-1]["t"] + int(ms)
            if nt <= t: break
            t = nt; time.sleep(0.3)
        df = pd.DataFrame(rows).drop_duplicates("t")
        df = pd.DataFrame({"ts": pd.to_datetime(df.t, unit="ms", utc=True), "open": df.o.astype(float), "high": df.h.astype(float),
                           "low": df.l.astype(float), "close": df.c.astype(float), "volume": df.v.astype(float)}).sort_values("ts")
        df = df[df.ts < pd.Timestamp.now(tz="UTC").floor(tf)]  # drop the still-open candle
        df.to_csv(f"data/HL_{sym}_{tf}.csv", index=False); print(coin, tf, len(df), df.ts.min(), df.ts.max())
    rows, t = [], START
    while t < NOW:
        f = post({"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": NOW})
        if not f: break
        rows += f; nt = f[-1]["time"] + 1
        if nt <= t: break
        t = nt; time.sleep(0.3)
    f = pd.DataFrame(rows).drop_duplicates("time")
    f = pd.DataFrame({"ts": pd.to_datetime(f.time, unit="ms", utc=True), "rate": f.fundingRate.astype(float)})
    f.to_csv(f"data/HL_{sym}_funding.csv", index=False); print(coin, "funding", len(f), f.ts.min(), f.ts.max(), "mean/h", f.rate.mean())
