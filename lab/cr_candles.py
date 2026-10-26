"""Stage 3 (PAPER ONLY): 1-minute USD candles per copy candidate from GeckoTerminal, through bf_common.gecko (shared lock with
the backfill job: combined Gecko+DexScreener <= 4/min). Cached in data/cr/candles/<leader>_<mint>.json. Resumable."""
import json, os, glob, sys, time, datetime as dt
from zoneinfo import ZoneInfo
import bf_common
from cr_enrich import CAND, SHARED_AUTH, LEAD
CR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cr"); CD = os.path.join(CR, "candles")
DUB = ZoneInfo("Europe/Dublin"); G = "https://api.geckoterminal.com/api/v2/networks/solana"
POOLS = os.path.join(CR, "gecko_pools.json")

def flat_time(t):
    """next 08:00 Europe/Dublin at or after t (selfcopy: flat by 08:00)."""
    d = dt.datetime.fromtimestamp(t, DUB); f = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if f <= d: f += dt.timedelta(days=1)
    return int(f.timestamp())

def horizon(e):
    t = e["buy"]["t"]; H = flat_time(t); pre = 0.0; held = None
    for s in e.get("sells") or []:
        if s["t"] >= H: break
        if s.get("pre_bal") and s.get("tokens") and s["tokens"] >= 0.95 * s["pre_bal"]: return min(H, s["t"] + 300), "leader_full_exit"
    return H, "flat_0800"

def pool_for(e):
    own = (e.get("ps") or {}).get("owner")
    if own and own not in SHARED_AUTH: return own
    d = json.load(open(POOLS)) if os.path.exists(POOLS) else {}
    if e["mint"] in d: return d[e["mint"]]
    ct = json.load(open(os.path.join(CR, "..", "copytest", "pools.json")))
    if e["mint"] in ct and not ((e.get("mcap") or 0) >= 1e6 and (e.get("liq") or 0) >= 1e5): d[e["mint"]] = ct[e["mint"]]
    else:
        j = bf_common.gecko(f"{G}/tokens/{e['mint']}/pools?page=1")
        ps = (j or {}).get("data") or []
        d[e["mint"]] = ps[0]["attributes"]["address"] if ps else None
        if ps: d["created:" + e["mint"]] = ps[0]["attributes"].get("pool_created_at")
    json.dump(d, open(POOLS, "w")); return d[e["mint"]]

def ensure_created(e):
    """NEW-rule candidates whose on-chain pool age is unknown: pool_created_at of the deepest pool from GeckoTerminal (1 call, cached)."""
    if not ((e.get("mcap") or 0) >= 1e6 and (e.get("liq") or 0) >= 1e5) or e.get("age_s") is not None: return
    d = json.load(open(POOLS)) if os.path.exists(POOLS) else {}
    if "created:" + e["mint"] in d: return
    j = bf_common.gecko(f"{G}/tokens/{e['mint']}/pools?page=1"); ps = (j or {}).get("data") or []
    d["created:" + e["mint"]] = ps[0]["attributes"].get("pool_created_at") if ps else None
    d["pools:" + e["mint"]] = [(p["attributes"]["address"], p["attributes"].get("pool_created_at"), p["attributes"].get("reserve_in_usd")) for p in ps[:5]]
    json.dump(d, open(POOLS, "w"))

def fetch(e):
    p = os.path.join(CD, f'{e["leader"]}_{e["mint"]}.json')
    if os.path.exists(p): return json.load(open(p))
    pool = pool_for(e); t0 = e["buy"]["t"] - 120; H, why = horizon(e)
    out = dict(pool=pool, t0=t0, H=H, why=why, rows=[], calls=0, status="ok")
    if not pool: out["status"] = "no_pool"
    else:
        before = H + 60
        for _ in range(3):
            j = bf_common.gecko(f"{G}/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&before_timestamp={before}&currency=usd&token={e['mint']}")
            out["calls"] += 1
            if not j or j.get("_404"): out["status"] = "404" if j else "fail"; break
            rows = j.get("data", {}).get("attributes", {}).get("ohlcv_list") or []
            out["rows"] += rows
            if len(rows) < 1000 or not rows or min(r[0] for r in rows) <= t0: break
            before = min(r[0] for r in rows)
        out["rows"] = sorted({r[0]: r for r in out["rows"] if t0 <= r[0] <= H + 60}.values())
    json.dump(out, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    return out

def main():
    fs = sorted(glob.glob(os.path.join(CAND, "*.json")))
    es = [json.load(open(f)) for f in fs]
    es = [e for e in es if e.get("ps") and (e.get("pre_bal") or 0) <= 1e-9 and "sells" in e]
    es.sort(key=lambda e: -(e.get("mcap") or 0))            # NEW-rule candidates (mcap >= $1M) first
    print("to fetch", len(es), flush=True)
    for k, e in enumerate(es):
        ensure_created(e); r = fetch(e); print(k, e["leader"], e["mint"][:8], r["status"], len(r["rows"]), r["calls"], r["why"], flush=True)
if __name__ == "__main__": main()
