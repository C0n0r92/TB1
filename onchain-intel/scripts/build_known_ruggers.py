#!/usr/bin/env python3
"""Build known_ruggers.json (+ known_funders.csv) from analysis: creators/bundlers of dumped or template-launch coins,
plus the wallets that funded them (1-2 hops). Re-runnable; funding lookups cached in data/funding.json."""
import os, sys, json, csv, collections, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE
from funding import chain
A = json.load(open(os.path.join(BASE, "data", "analysis.json"))); Sm = json.load(open(os.path.join(BASE, "data", "summary.json")))
T, W, S, tmpl = A["tokens"], A["wallets"], Sm["S"], Sm["tmpl"]
tok_tmpl = {m: k for k, v in tmpl.items() for m in v}
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def dead(m): return ((T.get(m, {}).get("now") or {}).get("mcap") or 0) < 10000
KF = os.path.join(BASE, "known_ruggers.json")
old = json.load(open(KF)) if os.path.exists(KF) else {"wallets": {}}
ruggers = {}
for o, rows in W.items():
    for x in rows:
        m = x["mint"]; bad_tok = dead(m) or m in tok_tmpl
        if not bad_tok: continue
        role = "creator" if x["is_dev"] else ("launch-slot bundler" if x["is_bundle"] else None)
        if not role: continue
        profit = x["sol_received"] - x["sol_spent"]
        if role != "creator" and profit <= 0: continue
        r = ruggers.setdefault(o, {"role": role, "tokens": [], "evidence": [], "first_seen": x["ts"]})
        r["tokens"].append({"sym": x["sym"], "mint": m, "dumped": dead(m), "template": tok_tmpl.get(m), "net_sol": round(profit, 3),
                            "buy_sig": x["sig"], "buy_ts": iso(x["ts"]), "last_sell_sig": x.get("last_sell_sig")})
        r["first_seen"] = min(r["first_seen"], x["ts"])
# trace funding for creators (all) and bundlers with >= 5 SOL profit
fund_edges = []
for o, r in ruggers.items():
    if r["role"] == "creator" or sum(t["net_sol"] for t in r["tokens"]) >= 5:
        c = chain(o, 2); r["funding_chain"] = c; fund_edges += [(o, i + 1, e) for i, e in enumerate(c)]
fcount = collections.defaultdict(lambda: {"funded": set(), "edges": []})
for o, hop, e in fund_edges:
    fcount[e["from"]]["funded"].add(o); fcount[e["from"]]["edges"].append({"rugger": o, "hop": hop, **e})
now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out = {"generated": now, "wallets": {}, "funders": {}}
for o, r in ruggers.items():
    prev = old.get("wallets", {}).get(o, {})
    out["wallets"][o] = {**r, "address": o, "date_added": prev.get("date_added", now), "first_seen": iso(r["first_seen"])}
for f, v in fcount.items():
    prev = old.get("funders", {}).get(f, {})
    out["funders"][f] = {"address": f, "n_ruggers_funded": len(v["funded"]), "ruggers": sorted(v["funded"]),
                         "edges": v["edges"], "date_added": prev.get("date_added", now),
                         "strength": "strong" if len(v["funded"]) >= 2 else "weak (funded 1 known rugger; could be an exchange/hub)"}
json.dump(out, open(KF, "w"), indent=1)
with open(os.path.join(BASE, "known_funders.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["address", "n_ruggers_funded", "ruggers", "evidence", "strength", "date_added"])
    for a, v in sorted(out["funders"].items(), key=lambda kv: -kv[1]["n_ruggers_funded"]):
        w.writerow([a, v["n_ruggers_funded"], " ".join(v["ruggers"]), " | ".join("https://solscan.io/tx/" + e["sig"] for e in v["edges"][:4]), v["strength"], v["date_added"]])
print("ruggers", len(out["wallets"]), "funders", len(out["funders"]), "strong", sum(1 for v in out["funders"].values() if v["n_ruggers_funded"] >= 2))
for a, v in sorted(out["funders"].items(), key=lambda kv: -kv[1]["n_ruggers_funded"])[:12]: print(a, v["n_ruggers_funded"], [x[:6] for x in v["ruggers"]])
