#!/usr/bin/env python3
"""For each mint: page signatures back to creation, fetch the first N successful txs,
record creator, early buyers (rank, secs after creation, SOL spent, tx sig, token account).
Usage: early_buyers.py <mint> [<mint> ...]   -> data/early/<mint>.json"""
import sys, json, os, re, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from sol import sigs, tx, deltas, BASE
N = int(os.environ.get("EARLY_N", "200"))
BC_PAGES = int(os.environ.get("EARLY_BC_PAGES", "60")); MINT_PAGES = int(os.environ.get("EARLY_MINT_PAGES", "400"))
DEFER = os.path.join(BASE, "data", "early_deferred.txt")
OUT = os.path.join(BASE, "data", "early"); os.makedirs(OUT, exist_ok=True)
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PROGRAM_OWNERS = set()  # pool owners are PDAs; we only count signers as buyers

def run(mint):
    fn = os.path.join(OUT, mint + ".json")
    if os.path.exists(fn): return json.load(open(fn))
    # pump.fun: the bonding-curve PDA's history is short (ends at graduation) and starts with the create tx,
    # so early buyers are reachable even for coins with >400k mint signatures. Fall back to the mint's history.
    import pda
    S = sigs(pda.bonding_curve(mint), limit_pages=BC_PAGES) if mint.endswith("pump") else []
    if len([s for s in S if s["err"] is None]) < N:
        # graduated fast: early trades are on the AMM, so merge in the mint's own history
        seen = {s["signature"] for s in S}; M = sigs(mint, limit_pages=MINT_PAGES)
        if len(M) >= MINT_PAGES * 1000:
            # page cap hit before creation: do NOT cache a wrong 'early buyers' list; defer to a manual backfill
            open(DEFER, "a").write(f"{int(time.time())} {mint} mint history > {MINT_PAGES} pages\n")
            return {"mint": mint, "deferred": True, "total_sigs": len(S) + len(M), "creator": None, "events": []}
        S += [s for s in M if s["signature"] not in seen]
    ok = [s for s in S if s["err"] is None]
    ok.sort(key=lambda s: (s["slot"], s.get("transactionIndex", 0)))
    first = ok[:N]
    with ThreadPoolExecutor(6) as ex:
        txs = list(ex.map(lambda s: tx(s["signature"]), first))
    t0 = first[0]["blockTime"]; slot0 = first[0]["slot"]
    creator = None; events = []
    for s, t in zip(first, txs):
        if not t: continue
        tok, sol, wsol, signers, acct = deltas(t, mint)
        logs = " ".join(t["meta"].get("logMessages") or [])
        if creator is None and s is first[0] and PUMP in logs and re.search(r"Instruction: Create(V2)?\b", logs):
            creator = signers[0]
        for o, d in tok.items():
            if abs(d) < 1e-9 or o not in signers: continue
            events.append({"owner": o, "side": "buy" if d > 0 else "sell", "tokens": d,
                           "sol": round(sol.get(o, 0) + wsol.get(o, 0), 6), "sig": s["signature"],
                           "slot": s["slot"], "slot_offset": s["slot"] - slot0, "ts": s["blockTime"],
                           "secs": s["blockTime"] - t0, "token_account": acct.get(o), "fee_payer": signers[0]})
    res = {"mint": mint, "total_sigs": len(S), "creator": creator, "create_sig": first[0]["signature"],
           "reached_creation": creator is not None, "create_ts": t0, "create_slot": slot0, "events": events}
    json.dump(res, open(fn, "w"), indent=1)
    return res

if __name__ == "__main__":
    for m in sys.argv[1:]:
        r = run(m)
        buys = [e for e in r["events"] if e["side"] == "buy"]
        print(m, "sigs", r["total_sigs"], "creator", r["creator"], "buys", len(buys), "uniq", len({e['owner'] for e in buys}), flush=True)
