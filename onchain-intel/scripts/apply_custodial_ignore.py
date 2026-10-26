#!/usr/bin/env python3
"""Strip public-label-confirmed exchange/custodial wallets (custodial_ignore.json) from known_ruggers.json funders
and known_funders.csv. Run after build_known_ruggers.py and merge_operator.py, which rebuild those lists. Read-only on-chain."""
import os, json, csv
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ig = {w["address"] for w in json.load(open(os.path.join(BASE, "custodial_ignore.json")))["wallets"]}
kf = os.path.join(BASE, "known_ruggers.json"); K = json.load(open(kf))
n = sum(1 for a in list(K.get("funders", {})) if a in ig and K["funders"].pop(a, None) is not None)
if n: json.dump(K, open(kf + ".tmp", "w"), indent=1); os.replace(kf + ".tmp", kf)
cf = os.path.join(BASE, "known_funders.csv"); rows = list(csv.DictReader(open(cf))); keep = [r for r in rows if r["address"] not in ig]
if len(keep) != len(rows):
    with open(cf + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(keep)
    os.replace(cf + ".tmp", cf)
print("custodial_ignore: removed", n, "funders from known_ruggers.json,", len(rows) - len(keep), "rows from known_funders.csv")
