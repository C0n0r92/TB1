"""Write fetch plan (priority-ordered sig list) for fetch_multi.py."""
import json, sys, os; sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc
N_EARLY, STRIDE, CAP = 300, 4, 400
T = json.load(open("legs.json")); S = json.load(open("sigs_summary.json")); st = [[], [], []]; info = {}
for tr in T:
    if S.get(str(tr["i"]), {}).get("skip"): continue
    legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]; fb = [l for l in legs if l["side"] == "buy"][0]
    a = []
    for o in S[str(tr["i"])]:
        a += [x for x in rpc.sigs(o, tr["before_sig"], fb["sig"], maxpages=120 if S[str(tr["i"])][o]["n"] >= 30000 else 30)["sigs"] if not x["err"]]
    a = sorted({x["s"]: x for x in a}.values(), key=lambda x: (x["slot"], x["s"]))
    st[0] += [x["s"] for x in a if any(l["ts"] - 2 <= x["t"] <= l["ts"] + 40 for l in legs)]
    st[1] += [x["s"] for x in a[:N_EARLY]]
    rest = a[N_EARLY:]; k = max(STRIDE, len(rest) // CAP + 1); st[2] += [x["s"] for x in rest[::k]]
    info[tr["i"]] = (tr["sym"], len(a), k)
seen = set(); out = []
for s in st[0] + st[1] + st[2]:
    if s not in seen and not os.path.exists(os.path.join(rpc.D, "tx", s + ".json")): seen.add(s); out.append(s)
open("plan.txt", "w").write("\n".join(out)); print(len(st[0]), len(st[1]), len(st[2]), "todo", len(out)); print(info)
