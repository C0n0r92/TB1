"""read-only: last-24h leader buys (paper-trades.jsonl leader_swap + ypnn 24h diag) vs entry-signal thresholds.
approx: mcap at buy = fill_px * current supply (DexScreener); liq and pair age from DexScreener NOW (age at buy = created -> block time)."""
import json, time, urllib.request, collections, datetime
UA = {"User-Agent": "Mozilla/5.0 selfcopy-diag"}
now = time.time(); cut = now - 86400
P = lambda s: datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
buys = []
for l in open("/workspace/selfcopy/paper-trades.jsonl"):
    if '"leader_swap"' not in l or '"buy"' not in l: continue
    e = json.loads(l)
    if e.get("side") != "buy" or P(e["ts"]) < cut: continue
    buys.append(dict(leader=e["leader"], mint=e["mint"], usd=e["usd"], px=e.get("fill_px"), t=P(e["ts"]), first=not e.get("pre_bal")))
info = {}
def get(u):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20))
    except Exception: return None
for m in {b["mint"] for b in buys}:
    j = [p for p in (get(f"https://api.dexscreener.com/tokens/v1/solana/{m}") or []) if p.get("priceUsd")]; time.sleep(0.25)
    if not j: info[m] = None; continue
    p = max(j, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0); px = float(p["priceUsd"]); fdv = p.get("marketCap") or p.get("fdv") or 0
    info[m] = dict(supply=fdv / px if px else None, liq=(p.get("liquidity") or {}).get("usd") or 0, created=(p.get("pairCreatedAt") or 0) / 1000, sym=p["baseToken"]["symbol"])
rows = []
for b in buys:
    i = info.get(b["mint"]) or {}
    mc = (b["px"] or 0) * (i.get("supply") or 0); age = (b["t"] - i["created"]) / 60 if i.get("created") else None
    rows.append(dict(leader=b["leader"], coin=i.get("sym") or b["mint"][:6], usd=b["usd"], mcap=mc, liq=i.get("liq") or 0, age=age, t=b["t"], first=b["first"]))
# ypnn before the bot tracked it (08:56Z): 24h diag rows
yd = json.load(open("/workspace/selfcopy/diag/ypnn_filters.json"))["rows"]
for r in yd: rows.append(dict(leader="ypnn-day", coin=r["sym"], usd=r["usd"], mcap=r["mcap"] or 0, liq=r["liq_now"] or 0, age=r["age_min"], t=None, first=r["first"], diag=True))
rows = [r for r in rows if not (r["leader"] == "ypnn-day" and not r.get("diag") and r["t"] and r["t"] < P("2026-10-24T08:58:30Z"))]
def passes(r, mm, ma): return r["usd"] >= 50 and r["mcap"] >= mm and r["liq"] >= 100_000 and r["age"] is not None and r["age"] >= ma
out = {}
for name, mm, ma in (("old $1M/60min, first buys only", 1e6, 60), ("old $1M/60min, + top-ups", 1e6, 60), ("NEW $300k/15min, + top-ups", 3e5, 15)):
    sel = [r for r in rows if passes(r, mm, ma) and (r["first"] or "top-ups" in name)]
    coins = {(r["leader"], r["coin"]) for r in sel}
    out[name] = dict(buys=len(sel), unique_leader_coin=len(coins), by_leader=dict(collections.Counter(r["leader"] for r in sel)),
                     coins_by_leader={L: sorted({c for (l, c) in coins if l == L}) for L in {l for l, _ in coins}})
print("total 24h leader buys considered:", len(rows), dict(collections.Counter(r["leader"] for r in rows)))
print(json.dumps(out, indent=1))
