#!/usr/bin/env python3
"""Merge operator-watch wallets (full-curve ~86 SOL dev-buy operator) into avoid.csv, known_ruggers.json, known_funders.csv.
Inputs: data/operator_chains.json (backward SOL funding chains of creators), data/operator_forward.json (where creators' SOL went next).
Adds creators, hop-1/2 funders, and forward successors. date_added preserved across reruns. Run after build_outputs + build_known_ruggers."""
import os, sys, json, csv, time
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); HOPS = 2
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
SYM = {l.split()[0]: l.split()[1] for l in open(os.path.join(BASE, "data", "tokens.txt")) if l.strip()}
SYM.update({"AFTT85geTb4xkr7QDPNChNXobFiTHvEL2Anon7JNpump": "Grok", "FYikV6BpxnWz4v5G9pU4jowmph4ywXpgaabRx4Ykpump": "MrBeast(2)",
            "Bk6hjA8TuvcuXjJ3SmnrouN4Q9GsqLwtq79P6ykapump": "SpaceX-AI", "M7qm4YGLmEyfyPyN3MFpReN9xGiRZPkr2PbW5Tupump": "GTA6-Coin",
            "9HCJfz2LwkmQieYCyApuk6dVJRr6zX4nGbqnPV5Rpump": "YMB", "AzsRDaPns1p345H16fVBkXoXA6RwrwMzVvQoxUnzpump": "Speed",
            "t8kwWQM6U76MdCMyuFFSresbjyvQ4hQM3ZTDL3tpump": "Mr-Beast(1)"})
C = json.load(open(os.path.join(BASE, "data", "operator_chains.json")))
F = json.load(open(os.path.join(BASE, "data", "operator_forward.json"))) if os.path.exists(os.path.join(BASE, "data", "operator_forward.json")) else []
W = {}   # address -> {role, mints, evidence, first_seen}
def add(a, role, mint, sig, ts):
    w = W.setdefault(a, {"roles": [], "mints": [], "evidence": [], "first_seen": iso(ts) if ts else None})
    if role not in w["roles"]: w["roles"].append(role)
    if mint and mint not in w["mints"]: w["mints"].append(mint)
    if sig and len(w["evidence"]) < 4: w["evidence"].append("https://solscan.io/tx/" + sig)
ops = {m: v for m, v in C.items() if v["chain"] and (v["chain"][0]["sol"] or 0) >= 100}   # operator template: fresh creator funded >=100 SOL just before an ~86 SOL dev buy
creators = {v["creator"]: m for m, v in ops.items()}
for m, v in ops.items():
    add(v["creator"], f"operator creator ({SYM.get(m, m[:6])}, full-curve {v['dev_buy_sol']} SOL dev buy)", m, v["create_tx"], None)
    for h, e in enumerate(v["chain"][:HOPS], 1):
        add(e["from"], f"operator funder hop{h} of {SYM.get(m, m[:6])} creator ({e['sol']} SOL)", m, e["sig"], e["ts"])
for e in F:
    if e["to"] in creators: continue
    src = creators.get(e["from"]); lab = f"operator successor: received {e['sol']} SOL from " + (f"{SYM.get(src, src[:6])} creator" if src else "operator wallet " + e["from"][:8])
    add(e["to"], lab, src, e["sig"], e["ts"]); add(e["from"], "operator peel-chain wallet", src, None, None)
json.dump({"generated": NOW, "wallets": W}, open(os.path.join(BASE, "data", "operator_watch.json"), "w"), indent=1)

# --- avoid.csv
fn = os.path.join(BASE, "avoid.csv"); rows = list(csv.DictReader(open(fn))); hdr = list(rows[0].keys()) if rows else ["address", "reason", "date_added", "mints", "type", "evidence"]
idx = {r["address"]: r for r in rows}; old = json.load(open(os.path.join(BASE, "data", "operator_dates.json"))) if os.path.exists(os.path.join(BASE, "data", "operator_dates.json")) else {}
for a, w in W.items():
    d = old.setdefault(a, NOW)
    r = idx.get(a)
    reason = "operator watch: " + "; ".join(w["roles"])
    if r is None:
        r = {k: "" for k in hdr}; r.update(address=a, date_added=d, type="operator"); rows.append(r); idx[a] = r
    if "operator watch" not in r["reason"]: r["reason"] = (r["reason"] + " | " if r["reason"] else "") + reason
    r["mints"] = " ".join(sorted(set((r.get("mints") or "").split()) | set(w["mints"])))
    if not r.get("evidence"): r["evidence"] = " | ".join(w["evidence"])
json.dump(old, open(os.path.join(BASE, "data", "operator_dates.json"), "w"), indent=0)
with open(fn, "w", newline="") as f:
    cw = csv.DictWriter(f, fieldnames=hdr); cw.writeheader(); cw.writerows(rows)

# --- known_ruggers.json (creators as wallets; all operator funders/successors as funders)
K = json.load(open(os.path.join(BASE, "known_ruggers.json")))
for a, w in W.items():
    toks = [{"sym": SYM.get(m, m[:6]), "mint": m, "template": "operator full-curve dev buy"} for m in w["mints"]]
    if any(r.startswith("operator creator") for r in w["roles"]):
        e = K["wallets"].setdefault(a, {"address": a, "date_added": old[a], "first_seen": w["first_seen"], "evidence": [], "tokens": [], "funding_chain": []})
        e["role"] = "operator creator"; e.setdefault("tokens", [])
        for t in toks:
            if t["mint"] not in [x.get("mint") for x in e["tokens"]]: e["tokens"].append(t)
        m = creators.get(a)
        if m: e["funding_chain"] = ops[m]["chain"][:HOPS]
    else:
        f = K["funders"].setdefault(a, {"address": a, "n_ruggers_funded": 0, "ruggers": [], "edges": [], "date_added": old[a]})
        rug = sorted({ops[m]["creator"] for m in w["mints"] if m in ops})
        f["ruggers"] = sorted(set(f.get("ruggers", [])) | set(rug)); f["n_ruggers_funded"] = len(f["ruggers"])
        f["strength"] = "strong"; f["operator_watch"] = w["roles"]; f.setdefault("evidence", w["evidence"])
K["generated"] = NOW
json.dump(K, open(os.path.join(BASE, "known_ruggers.json"), "w"), indent=1)

# --- known_funders.csv
fn = os.path.join(BASE, "known_funders.csv"); fr = list(csv.DictReader(open(fn))); fidx = {r["address"]: r for r in fr}
for a, w in W.items():
    if any(r.startswith("operator creator") for r in w["roles"]) and not any("funder" in r or "successor" in r or "peel" in r for r in w["roles"]): continue
    f = K["funders"][a] if a in K["funders"] else None
    rug = f["ruggers"] if f else []
    r = fidx.get(a)
    if r is None:
        r = {"address": a, "date_added": old[a]}; fr.append(r); fidx[a] = r
    r.update(n_ruggers_funded=str(max(int(r.get("n_ruggers_funded") or 0), len(rug))), ruggers=" ".join(sorted(set((r.get("ruggers") or "").split()) | set(rug))),
             strength="strong", evidence=(r.get("evidence") or " | ".join(w["evidence"])))
    if "operator" not in r["evidence"]: r["evidence"] = "operator watch: " + "; ".join(w["roles"])[:300] + " | " + r["evidence"]
with open(fn, "w", newline="") as f:
    cw = csv.DictWriter(f, fieldnames=["address", "n_ruggers_funded", "ruggers", "evidence", "strength", "date_added"]); cw.writeheader(); cw.writerows(fr)
print("operator wallets", len(W), "creators", len(creators), "coins", len(ops))
