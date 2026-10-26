"""Extra public data: Binance-mirror SOLUSDT 1m klines (for Polymarket TWAP proxy + direction model) and OKX SOL-USDT-SWAP funding history
(proxy for perp funding; Drift's data API is unreachable from this box - TLS reset)."""
import os, json, time, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_candles as F
F.MS["1m"] = 60e3
ROOT = F.ROOT
def okx_funding():
    rows, after = [], ""
    for _ in range(60):
        url = "https://www.okx.com/api/v5/public/funding-rate-history?instId=SOL-USDT-SWAP&limit=100" + (f"&after={after}" if after else "")
        d = F.get(url, False).get("data", [])
        if not d: break
        rows += d; after = d[-1]["fundingTime"]
    df = pd.DataFrame(rows)[["fundingTime", "realizedRate", "fundingRate"]].astype(float).drop_duplicates("fundingTime").sort_values("fundingTime")
    df.to_csv(os.path.join(ROOT, "data", "OKX_SOL_funding.csv"), index=False)
    print("okx funding", len(df), pd.to_datetime(df.fundingTime.min(), unit="ms"), pd.to_datetime(df.fundingTime.max(), unit="ms"), flush=True)
if __name__ == "__main__":
    okx_funding()
    F.DAYS = int(os.environ.get("DAYS1M", "400")); F.binance("1m")
