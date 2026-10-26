"""Download free public Binance USD-M perp klines + funding (price source only) from data.binance.vision."""
import io, zipfile, urllib.request, pandas as pd, os
BASE="https://data.binance.vision/data/futures/um/monthly"
SYMS=["BTCUSDT","SOLUSDT"]; TFS=["1h","4h"]
months=pd.period_range("2024-10","2026-09",freq="M")
def get(url):
    try:
        with urllib.request.urlopen(url,timeout=60) as r: data=r.read()
    except Exception as e: print("miss",url,e); return None
    z=zipfile.ZipFile(io.BytesIO(data)); return z.read(z.namelist()[0]).decode()
os.makedirs("data",exist_ok=True)
for s in SYMS:
    for tf in TFS:
        frames=[]
        for m in months:
            t=get(f"{BASE}/klines/{s}/{tf}/{s}-{tf}-{m}.zip")
            if t is None: continue
            lines=t.strip().splitlines()
            if lines[0].startswith("open_time"): lines=lines[1:]
            df=pd.read_csv(io.StringIO("\n".join(lines)),header=None).iloc[:,:6]
            df.columns=["ts","open","high","low","close","volume"]; frames.append(df)
        df=pd.concat(frames).drop_duplicates("ts").sort_values("ts")
        df["ts"]=pd.to_datetime(df.ts,unit="ms",utc=True); df.to_csv(f"data/{s}_{tf}.csv",index=False); print(s,tf,len(df),df.ts.min(),df.ts.max())
    frames=[]
    for m in months:
        t=get(f"{BASE}/fundingRate/{s}/{s}-fundingRate-{m}.zip")
        if t is None: continue
        frames.append(pd.read_csv(io.StringIO(t)))
    f=pd.concat(frames); f.columns=[c.strip() for c in f.columns]
    f=f.rename(columns={f.columns[0]:"ts"}); f["ts"]=pd.to_datetime(f.ts,unit="ms",utc=True)
    f=f[["ts","last_funding_rate"]].rename(columns={"last_funding_rate":"rate"}).sort_values("ts")
    f.to_csv(f"data/{s}_funding.csv",index=False); print(s,"funding",len(f),f.rate.mean())
