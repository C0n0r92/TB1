"""Phase 2b: fetch pool txs. Priority: dense windows [leg_ts-2, leg_ts+40] around every one of his legs, then
all txs in the first N_EARLY after his buy, then every STRIDE-th tx across the rest of the hold. Public RPC only."""
import json, sys, os; sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, pools
N_EARLY, STRIDE = int(os.environ.get("N_EARLY", 600)), int(os.environ.get("STRIDE", 3))
T = json.load(open("legs.json")); S = json.load(open("sigs_summary.json"))
plan = []
for tr in T:
    if S.get(str(tr["i"]), {}).get("skip"): continue
    legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]
    fb = [l for l in legs if l["side"] == "buy"][0]
    allsig = []
    for o in S[str(tr["i"])]:
        mp = 120 if S[str(tr["i"])][o]["n"] >= 30000 else 30
        allsig += [x for x in rpc.sigs(o, tr["before_sig"], fb["sig"], maxpages=mp)["sigs"] if not x["err"]]
    allsig = sorted({x["s"]: x for x in allsig}.values(), key=lambda x: (x["slot"], x["s"]))
    dense = [x["s"] for x in allsig if any(l["ts"] - 2 <= x["t"] <= l["ts"] + 40 for l in legs)]
    early = [x["s"] for x in allsig[:N_EARLY]]
    stride = STRIDE if len(allsig) < 20000 else max(STRIDE, len(allsig) // 2500)
    rest = [x["s"] for x in allsig[N_EARLY::stride]]
    plan.append((tr["i"], tr["sym"], dense, early, rest, len(allsig)))
tot = sum(len(set(d) | set(e) | set(r)) for _, _, d, e, r, _ in plan); print("planned", tot, flush=True)
for stage in (2, 3, 4):
    for i, sym, d, e, r, n in plan:
        lst = (d, e, r)[stage - 2]; got = 0
        for s in lst:
            if not os.path.exists(os.path.join(rpc.D, "tx", s + ".json")): rpc.tx(s); got += 1
        print("stage", stage, i, sym, "n_pool", n, "fetched", got, "of", len(lst), flush=True)
print("DONE", flush=True)
