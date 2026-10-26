"""Phase 2a: pool signature lists over each trip's hold window (his buy .. first tx >120s after exit). Public RPC only."""
import json, sys, os; sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, pools
T = json.load(open("legs.json")); out = {}
for tr in T:
    legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]
    defs = [pools.define(rpc.tx(l["sig"]), tr["mint"]) for l in legs]
    owners = []
    for d in defs:
        if d and d["kind"] != "unrecon" and d["owner"] not in owners: owners.append(d["owner"])
    if any(d is None or d["kind"] == "unrecon" for d in defs): out[tr["i"]] = dict(skip=True); print(tr["i"], tr["sym"], "skip", flush=True); continue
    first_buy = [l for l in legs if l["side"] == "buy"][0]
    res = {}
    for o in owners:
        s = rpc.sigs(o, tr["before_sig"], first_buy["sig"], maxpages=30)
        res[o] = dict(n=len(s["sigs"]), complete=s["complete"])
        print(tr["i"], tr["sym"], o[:6], len(s["sigs"]), s["complete"], flush=True)
    out[tr["i"]] = res
json.dump(out, open("sigs_summary.json", "w"), indent=1)
