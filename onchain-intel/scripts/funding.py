#!/usr/bin/env python3
"""Who funded a wallet? Finds the wallet's earliest incoming-SOL tx and the account that paid it.
funder(addr) -> {"funder", "sig", "ts", "sol", "reached_start", "funder_busy"} ; cached in data/funding.json"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from sol import sigs, tx, BASE
FN = os.path.join(BASE, "data", "funding.json")
_C = json.load(open(FN)) if os.path.exists(FN) else {}
def _save(): json.dump(_C, open(FN, "w"), indent=0)

def funder(addr, max_pages=5):
    if addr in _C: return _C[addr]
    S = sigs(addr, limit_pages=max_pages)
    reached = len(S) < max_pages * 1000
    res = {"funder": None, "sig": None, "ts": None, "sol": None, "reached_start": reached, "n_sigs_seen": len(S)}
    ok = sorted([s for s in S if s["err"] is None], key=lambda s: (s["slot"], s.get("transactionIndex", 0)))
    for s in ok[:8]:              # first few txs of the wallet's life
        t = tx(s["signature"])
        if not t: continue
        keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]
        m = t["meta"]; d = {k: (m["postBalances"][i] - m["preBalances"][i]) / 1e9 for i, k in enumerate(keys)}
        if d.get(addr, 0) > 0.01:
            payer = min((k for k in keys if k != addr), key=lambda k: d.get(k, 0))
            if d.get(payer, 0) < 0:
                res.update(funder=payer, sig=s["signature"], ts=s["blockTime"], sol=round(d[addr], 4)); break
    _C[addr] = res; _save(); return res

def chain(addr, hops=2):
    out, cur = [], addr
    for _ in range(hops):
        f = funder(cur)
        if not f["funder"]: break
        out.append({"from": f["funder"], "to": cur, "sol": f["sol"], "sig": f["sig"], "ts": f["ts"]}); cur = f["funder"]
    return out

if __name__ == "__main__":
    print(json.dumps(chain(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2), indent=1))
