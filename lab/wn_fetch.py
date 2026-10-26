#!/usr/bin/env python3
"""PAPER ONLY. 1m GT candles around each winners/ trade entry (one call per trade; pump curve PDA if the entry was on pump.fun,
else Scout's context_pool). Cache data/cl/wn/<mint>_<entry_ts>.json. Shares the <=5/min throttle in cl_common."""
import csv, json, os, sys, datetime as dt
from cl_common import get, CL
from solders.pubkey import Pubkey
G = "https://api.geckoterminal.com/api/v2/networks/solana"; WD = os.path.join(CL, "wn")
PF = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
rows = list(csv.DictReader(open("/workspace/onchain-intel/winners/trades.csv")))
done = 0
for r in rows:
    t = int(dt.datetime.fromisoformat(r["entry_time"].replace("Z", "+00:00")).timestamp()); m = r["mint"]
    p = os.path.join(WD, f"{m}_{t}.json")
    if os.path.exists(p): continue
    if r["entry_via_pumpfun"] == "True" and m.endswith("pump"):
        pool = str(Pubkey.find_program_address([b"bonding-curve", bytes(Pubkey.from_string(m))], PF)[0]); kind = "pda"
    else: pool = r["context_pool"]; kind = "context"
    if not pool: continue
    j = get(f"{G}/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&before_timestamp={t + 6 * 3600}&currency=usd&token={m}")
    rs = [] if not j or j.get("_404") else (j.get("data", {}).get("attributes", {}).get("ohlcv_list") or [])
    json.dump(dict(mint=m, t=t, pool=pool, kind=kind, status="fail" if j is None else ("404" if j.get("_404") else "ok"), rows=sorted(rs)), open(p, "w"))
    done += 1; print(done, m, kind, len(rs), flush=True)
print("done")
