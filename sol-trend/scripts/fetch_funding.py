"""Public perp funding history proxies for Drift (Drift data API unreachable from this box; Binance/Bybit geo-blocked 451/403 - not circumvented).
- Hyperliquid SOL perp hourly funding (api.hyperliquid.xyz/info, public POST, no key) -> data/HL_SOL_funding.csv  [PRIMARY Drift proxy: on-chain, hourly, USD-quoted]
- Kraken Futures PF_SOLUSD hourly funding (relativeFundingRate) -> data/KRAKEN_SOL_funding.csv [cross-check]
Positive rate = longs pay shorts. Rates are per hour, fraction of notional."""
import json, os, time, urllib.request
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(ROOT, "data")
UA = {"User-Agent": "sol-trend-paper-research/0.1", "Content-Type": "application/json"}
def hl(start_ms):
    rows = []; t = start_ms; end = int(time.time() * 1000)
    while t < end:
        req = urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps({"type": "fundingHistory", "coin": "SOL", "startTime": t}).encode(), headers=UA)
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
        if not d: break
        rows += d; nt = d[-1]["time"] + 1
        if nt <= t or len(d) < 2: break
        t = nt; time.sleep(0.5)
    df = pd.DataFrame(rows); df["t"] = (df.time // 1000).astype("int64"); df["rate"] = df.fundingRate.astype(float)
    df = df.drop_duplicates("t").sort_values("t")[["t", "rate"]]; df.to_csv(os.path.join(D, "HL_SOL_funding.csv"), index=False)
    print("hyperliquid", len(df), pd.to_datetime(df.t.min(), unit="s"), pd.to_datetime(df.t.max(), unit="s"), "mean/h", df.rate.mean())
def kraken():
    d = json.loads(urllib.request.urlopen(urllib.request.Request("https://futures.kraken.com/derivatives/api/v4/historicalfundingrates?symbol=PF_SOLUSD", headers=UA), timeout=30).read())["rates"]
    df = pd.DataFrame(d); df["t"] = pd.to_datetime(df.timestamp).dt.tz_localize(None).astype("datetime64[s]").astype("int64"); df["rate"] = df.relativeFundingRate.astype(float)
    df = df.drop_duplicates("t").sort_values("t")[["t", "rate"]]; df.to_csv(os.path.join(D, "KRAKEN_SOL_funding.csv"), index=False)
    print("kraken", len(df), pd.to_datetime(df.t.min(), unit="s"), pd.to_datetime(df.t.max(), unit="s"), "mean/h", df.rate.mean())
if __name__ == "__main__":
    hl(int(time.time() * 1000) - 735 * 86400 * 1000); kraken()
