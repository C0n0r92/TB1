"""Validation: re-price every one of HIS legs with our model on the exact pre-trade pool state; compare to what he actually got."""
import json, sys, os, statistics as st
sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, pools, replay as R
TR = json.load(open("legs.json")); S = json.load(open("sigs_summary.json")); out = []
for tr in TR:
    if S.get(str(tr["i"]), {}).get("skip"): continue
    T = R.Trip(tr, S)
    if not T.ok: continue
    for x in T.L:
        d = x["d"]; pre = pools.pre_state(x["t"], d, tr["mint"])
        if not pre: continue
        ds, fee = R.his_sol(x["t"]); nw, cl = R.rent_adj(x["t"]); tok = x["post_h"] - x["pre_h"]
        if x["l"]["side"] == "buy":
            q = (-ds - fee - nw * R.RENT + cl * R.RENT) / x["rate"]; net = q * (1 - d["fee"]); m = pre[1] * net / (pre[0] + net); a = tok
        else:
            m = pre[0] * (-tok) / (pre[1] - tok) * (1 - d["fee"]) * x["rate"]; a = ds + fee + nw * R.RENT - cl * R.RENT
        out.append(dict(i=tr["i"], sym=tr["sym"], side=x["l"]["side"], kind=d["kind"], err=m / a - 1))
json.dump(out, open("validation.json", "w"), indent=0)
for k in ("pump_sol", "pump_q", "pumpswap"):
    for s in ("buy", "sell"):
        e = [o["err"] for o in out if o["kind"] == k and o["side"] == s]
        if e: print(k, s, "n", len(e), "median err %+.2f%%" % (100 * st.median(e)), "max |err| %.1f%%" % (100 * max(abs(v) for v in e)))
for o in out:
    if abs(o["err"]) > 0.03: print("  >3%:", o["i"], o["sym"], o["side"], o["kind"], "%+.1f%%" % (100 * o["err"]))
