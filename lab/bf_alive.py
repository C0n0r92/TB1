#!/usr/bin/env python3
"""Survivorship probe: which sampled graduations are still listed on DexScreener today, and with what liquidity.
tokens/v1/solana/<<=30 mints> -> data/backfill/alive.json. <= 9 req/min."""
import json, os, time, urllib.request
from bf_common import *
migs = read_jsonl(os.path.join(BF, "migrations.jsonl")); P = os.path.join(BF, "alive.json")
alive = json.load(open(P)) if os.path.exists(P) else {}
todo = [m["mint"] for m in migs if m["mint"] not in alive]
for i in range(0, len(todo), 30):
    ch = todo[i:i + 30]
    throttle("dexscreener tokens/v1")
    try:
        with urllib.request.urlopen(urllib.request.Request("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ch), headers=UA), timeout=30) as r:
            js = json.loads(r.read().decode())
    except Exception as e:
        print("err", e); time.sleep(30); continue
    best = {}
    for p in js or []:
        a = (p.get("baseToken") or {}).get("address"); l = (p.get("liquidity") or {}).get("usd") or 0
        if a in ch and l >= (best.get(a) or {}).get("liq", -1):
            best[a] = {"liq": l, "mcap": p.get("marketCap") or p.get("fdv"), "dex": p.get("dexId"), "pair": p.get("pairAddress"), "vol24": (p.get("volume") or {}).get("h24")}
    for a in ch: alive[a] = best.get(a, {"listed": False})
    json.dump(alive, open(P, "w")); print(i, len(best), flush=True)
print("done", len(alive))
