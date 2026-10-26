#!/usr/bin/env python3
"""Fetch 1-min USD candles around each confluence event (PAPER ONLY, resumable). Priority: EB_PIT clusters, a random
sample of EB_PIT single buys (non-cluster tokens, controls), then EB_ALL / SMART4 / LEAD clusters.
Pools: DexScreener batch (30 mints/call); fallback GeckoTerminal /tokens/<mint>/pools. Candles: GT ohlcv/minute,
window ~[t-4.5h, t+12h]. Cache: data/cl/pools.json, data/cl/candles/<mint>.json"""
import json, os, random, sys
from cl_common import get, CL
G = "https://api.geckoterminal.com/api/v2/networks/solana"; CD = os.path.join(CL, "candles"); os.makedirs(CD, exist_ok=True)
PP = os.path.join(CL, "pools.json")

def queue():
    E = json.load(open(os.path.join(CL, "events.json"))); q = []
    def add(evs, tag):
        for e in evs:
            if e["mint"] not in {x[0] for x in q}: q.append((e["mint"], e["t"], tag))
    add(E["events"]["EB_PIT_n2_w60"]["events"], "pit")
    cl = {e["mint"] for e in E["events"]["EB_ALL_n2_w60"]["events"]}
    sing = [s for s in E["singles"]["EB_PIT"] if s["mint"] not in cl]
    seen = set(); su = []
    for s in sing:
        if s["mint"] not in seen: seen.add(s["mint"]); su.append(s)
    random.Random(11).shuffle(su); add(su[:60], "pit_single")
    add(E["events"]["SMART4_n2_w60"]["events"] + E["events"]["LEAD_n2_w60"]["events"], "la_small")
    add(sorted(E["events"]["EB_ALL_n2_w60"]["events"], key=lambda e: -e["t"]), "la")
    # single LEAD buys on tokens that LEAD clusters touched are already covered; first-buy controls use the same candles
    return q

def pools(mints):
    d = json.load(open(PP)) if os.path.exists(PP) else {}
    need = [m for m in mints if m not in d]
    for i in range(0, len(need), 30):
        ch = need[i:i + 30]; r = get("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ch))
        if isinstance(r, list):
            for p in r:
                m = p["baseToken"]["address"]
                d.setdefault(m, []).append(dict(pool=p["pairAddress"], dex=p["dexId"], created=(p.get("pairCreatedAt") or 0) / 1000,
                                                 liq=(p.get("liquidity") or {}).get("usd"), mcap=p.get("marketCap"), fdv=p.get("fdv"),
                                                 price=p.get("priceUsd"), src="ds"))
            for m in ch: d.setdefault(m, [])
        json.dump(d, open(PP + ".tmp", "w")); os.replace(PP + ".tmp", PP)
    return d

def gt_pools(m, d):
    j = get(f"{G}/tokens/{m}/pools?page=1")
    for p in ((j or {}).get("data") or []):
        a = p["attributes"]; dex = p["relationships"]["dex"]["data"]["id"]
        import datetime as dt
        c = dt.datetime.fromisoformat(a["pool_created_at"].replace("Z", "+00:00")).timestamp() if a.get("pool_created_at") else 0
        d[m].append(dict(pool=a["address"], dex=dex, created=c, liq=float(a.get("reserve_in_usd") or 0), fdv=a.get("fdv_usd"),
                         price=a.get("base_token_price_usd"), src="gt"))
    d[m + "#gt"] = True
    json.dump(d, open(PP + ".tmp", "w")); os.replace(PP + ".tmp", PP)

def ohlcv(pool, mint, before):
    j = get(f"{G}/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&before_timestamp={int(before)}&currency=usd&token={mint}")
    if not j: return None, "fail"
    if j.get("_404"): return [], "404"
    return (j.get("data", {}).get("attributes", {}).get("ohlcv_list") or []), "ok"

def fetch(m, t, d):
    p = os.path.join(CD, f"{m}.json")
    if os.path.exists(p): return
    ps = [x for x in d.get(m, []) if x.get("pool")]
    if not ps and m.endswith("pump"):               # no DS pair (dead / never migrated): bonding-curve PDA only
        ps = []
    elif not ps and not d.get(m + "#gt"):
        gt_pools(m, d); ps = [x for x in d.get(m, []) if x.get("pool")]
    out = dict(mint=m, t=t, pools=ps, series=[], status="ok", calls=0)
    if not ps and not m.endswith("pump"): out["status"] = "no_pool"
    if ps or m.endswith("pump"):
        # pool active at t: latest created <= t+60 ; plus any pool created in (t, t+12h] (migration) stitched after
        ps = sorted(ps, key=lambda x: x["created"] or 0)
        act = [x for x in ps if (x["created"] or 0) <= t + 60]
        later = [x for x in ps if t + 60 < (x["created"] or 0) <= t + 12 * 3600]
        use = ([act[-1]] if act else []) + later[:1]
        if not act and m.endswith("pump"):             # pre-migration: pump.fun bonding-curve PDA == GeckoTerminal pump-fun pool id (verified)
            from solders.pubkey import Pubkey
            pda = str(Pubkey.find_program_address([b"bonding-curve", bytes(Pubkey.from_string(m))], Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"))[0])
            act = [dict(pool=pda, dex="pump-fun", created=0, src="pda")]
            use = act + later[:1]
        if not act and not d.get(m + "#gt"):          # DS shows only the post-migration pool -> find the curve pool on GT
            gt_pools(m, d); ps2 = sorted([x for x in d[m] if x.get("pool")], key=lambda x: x["created"] or 0)
            act = [x for x in ps2 if (x["created"] or 0) <= t + 60]
            use = ([act[-1]] if act else []) + [x for x in ps2 if t + 60 < (x["created"] or 0) <= t + 12 * 3600][:1]
        for x in use:
            rows, st = ohlcv(x["pool"], m, t + 12 * 3600); out["calls"] += 1
            out["series"].append(dict(pool=x["pool"], dex=x["dex"], created=x["created"], status=st, rows=sorted(rows or [])))
        if not act: out["status"] = "no_pool_at_t"
    json.dump(out, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    q = queue(); d = pools([m for m, _, _ in q]); n = 0
    for m, t, tag in q:
        if n >= lim: break
        if not os.path.exists(os.path.join(CD, f"{m}.json")):
            fetch(m, t, d); n += 1; print(tag, m, flush=True)
    print("done", n)
