#!/usr/bin/env python3
"""Step 3: GeckoTerminal 1-min OHLCV (USD, base token) for (a) tonight's live radar pairs (calibration) and
(b) sampled migrations, round-robin over days so a partial run covers every day evenly. <= ~9 req/min, cached, resumable.
One call per pool = up to 1000 traded minutes from creation (~16.7 h). Also SOL/USD hourly (1 call).
-> data/backfill/candles1m/<pool>.json {pool, rows:[[t,o,h,l,c,vol_usd],...], status}. Runs until the queue is empty."""
import sys, time, collections, datetime as dt
from bf_common import *
C1 = os.path.join(BF, "candles1m"); os.makedirs(C1, exist_ok=True)
MAXCALLS = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
G = "https://api.geckoterminal.com/api/v2/networks/solana"
calls = 0
def have(pool): return os.path.exists(os.path.join(C1, pool + ".json"))
def fetch(pool, before, kind, extra=None):
    global calls
    r = gecko(f"{G}/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&currency=usd&token=base&before_timestamp={int(before)}"); calls += 1
    out = {"pool": pool, "kind": kind, "before": int(before), "fetched_at": time.time(), **(extra or {})}
    if r is None: out["status"] = "error"
    elif r.get("_404"): out["status"] = "404"
    else:
        try:
            rows = sorted([[int(x[0])] + [float(v) for v in x[1:6]] for x in r["data"]["attributes"]["ohlcv_list"]])
            out.update(status="ok" if rows else "empty", rows=rows)
        except Exception: out["status"] = "bad"
    if out["status"] != "error":
        json.dump(out, open(os.path.join(C1, pool + ".json"), "w"))
    return out["status"]

# SOL/USD hourly (Raydium/Orca SOL-USDC pool via Gecko token pools is 1 extra call; use a well-known pool)
SOLP = os.path.join(BF, "solusd_1h.json")
if not os.path.exists(SOLP):
    r = gecko(f"{G}/pools/Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE/ohlcv/hour?aggregate=1&limit=1000&currency=usd"); calls += 1
    try:
        rows = sorted([[int(x[0])] + [float(v) for v in x[1:5]] for x in r["data"]["attributes"]["ohlcv_list"]])
        json.dump({"rows": rows}, open(SOLP, "w")); print("solusd", len(rows))
    except Exception as e: print("solusd fail", e)

# (a) calibration: live radar pairs
live = read_jsonl("/workspace/runner-radar/scanned.jsonl")
lp = {}
for r in live: lp.setdefault(r["pair"], r)
for pool, r in lp.items():
    if calls >= MAXCALLS: break
    p = os.path.join(C1, pool + ".json")
    if have(pool) and json.load(open(p)).get("before", 0) >= time.time() - 3600: continue
    st = fetch(pool, time.time(), "live", {"mint": r["token"]}); print("live", r["symbol"], st, flush=True)

# (b) migrations, round-robin by day; loop picks up new migrations as the sampler writes them
idle = 0
while calls < MAXCALLS:
    migs = read_jsonl(os.path.join(BF, "migrations.jsonl"))
    q = collections.defaultdict(list)
    for m in migs:
        if not have(m["pool"]): q[m["day"]].append(m)
    if not q:
        idle += 1
        if idle > 20: break
        time.sleep(60); continue
    idle = 0
    days = sorted(q)
    done = collections.Counter(m["day"] for m in migs if have(m["pool"]))
    days.sort(key=lambda d: done[d])                  # least-covered day first
    for d in days[:10]:
        m = q[d][0]
        st = fetch(m["pool"], m["t_mig"] + 60 * 1000 + 60, "mig", {"mint": m["mint"], "t_mig": m["t_mig"], "day": d})
        print(time.strftime("%H:%M:%S"), d, m["mint"][:8], st, "calls", calls, flush=True)
        if calls >= MAXCALLS: break
print("done calls", calls)
