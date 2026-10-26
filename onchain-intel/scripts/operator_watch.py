#!/usr/bin/env python3
"""Operator watch: full-curve (~86 SOL create-tx dev buy) coins. Traces creator SOL funding up to HOPS hops and
writes data/operator_chains.json; build_known_ruggers.py merges these into known_ruggers/known_funders/avoid."""
import os, sys, json, glob, time
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE
from funding import chain
HOPS = int(os.environ.get("OP_HOPS", "6"))
out = {}
for fn in glob.glob(os.path.join(BASE, "data", "rugcheck", "*.json")):
    try: r = json.load(open(fn))
    except Exception: continue
    if not any("full-curve dev buy" in x for x in r.get("reasons") or []): continue
    e = r["evidence"]; c = e["creator"]
    if r["mint"] in out: continue
    out[r["mint"]] = {"mint": r["mint"], "creator": c, "create_tx": e["create_tx"], "create_time_utc": e["create_time_utc"],
                      "dev_buy_sol": e.get("dev_buy_sol"), "chain": chain(c, HOPS)}
json.dump(out, open(os.path.join(BASE, "data", "operator_chains.json"), "w"), indent=1)
if __name__ == "__main__":
    for m, v in out.items():
        print(m[:8], v["create_time_utc"], "creator", v["creator"][:8], " <- ".join(f'{x["from"][:8]}({x["sol"]})' for x in v["chain"]))

# ---- forward trace: where did the operator's SOL go next (successor wallets = likely next creators) ----
from sol import sigs, tx
SKIP = {"6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}
def successors(addr, min_sol=50, max_tx=40):
    S = [s for s in sigs(addr, limit_pages=1) if s["err"] is None]
    S.sort(key=lambda s: s["slot"]); res = []
    for s in S[-max_tx:]:
        t = tx(s["signature"])
        if not t: continue
        keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]
        m = t["meta"]; d = {k: (m["postBalances"][i] - m["preBalances"][i]) / 1e9 for i, k in enumerate(keys)}
        if d.get(addr, 0) > -min_sol: continue
        if any("Program 6EF8rr" in l or "pAMMBay6" in l for l in m.get("logMessages") or []): continue  # trades, not transfers
        for k, v in d.items():
            if k != addr and k not in SKIP and v >= min_sol:
                res.append({"from": addr, "to": k, "sol": round(v, 4), "sig": s["signature"], "ts": s["blockTime"]})
    return res

def forward(roots, depth=4):
    seen, edges, frontier = set(roots), [], list(roots)
    for _ in range(depth):
        nxt = []
        for a in frontier:
            for e in successors(a):
                edges.append(e)
                if e["to"] not in seen: seen.add(e["to"]); nxt.append(e["to"])
        frontier = nxt
        if not frontier: break
    return edges

if __name__ == "__main__" and "--forward" in sys.argv:
    roots = [v["creator"] for v in out.values() if v["chain"] and (v["chain"][0]["sol"] or 0) > 100]
    E = forward(roots)
    json.dump(E, open(os.path.join(BASE, "data", "operator_forward.json"), "w"), indent=1)
    creators = {v["creator"] for v in out.values()}
    for e in E:
        print(time.strftime("%H:%M", time.gmtime(e["ts"])), e["from"][:8], "->", e["to"], e["sol"], "CREATOR" if e["to"] in creators else "")
