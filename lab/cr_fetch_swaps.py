"""Stage 1: extend leader swap history to 30 days with the FREE public RPC (resumable). PAPER ONLY, read-only.
Only fetches signatures OUTSIDE the time range already covered by Scout's trader_swaps.csv (that file is contiguous newest-first)."""
import csv, json, os, sys, time
from cr_rpc import rpc, get_tx, parse_swap, CR, STATS
OI = "/workspace/onchain-intel"
WIN0 = int(time.mktime(time.strptime("2026-09-23T23:00:00", "%Y-%m-%dT%H:%M:%S"))) - time.timezone if False else 1790204400  # 2026-09-23T23:00Z
LEAD = {"_benjitrades": "9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc", "bystevenr": "AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx",
        "pointfarmcap": "Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit", "ExactTallTakin": "AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v"}
def main():
    rows = list(csv.DictReader(open(os.path.join(OI, "trader_swaps.csv"))))
    for name, w in LEAD.items():
        mine = sorted((r for r in rows if r["trader"] == name), key=lambda r: r["timestamp"])
        known = {r["signature"] for r in mine}
        sp = os.path.join(CR, f"sigs_{name}.json"); st = json.load(open(sp)) if os.path.exists(sp) else {"sigs": [], "done": False}
        # page newest -> WIN0 (signatures are cheap: 1000/call)
        if not st["done"]:
            before = st["sigs"][-1]["signature"] if st["sigs"] else None
            while True:
                p = {"limit": 1000}
                if before: p["before"] = before
                r = rpc("getSignaturesForAddress", [w, p])
                if r == "FAIL": print(name, "sig fetch failed; resume later", flush=True); return
                if not r: st["done"] = True; break
                st["sigs"] += [{"signature": x["signature"], "bt": x.get("blockTime"), "err": x.get("err") is not None} for x in r]
                before = r[-1]["signature"]; bt = r[-1].get("blockTime") or 0
                json.dump(st, open(sp + ".tmp", "w")); os.replace(sp + ".tmp", sp)
                print(name, len(st["sigs"]), time.strftime("%m-%d %H:%M", time.gmtime(bt)), flush=True)
                if bt < WIN0: st["done"] = True; break
            json.dump(st, open(sp + ".tmp", "w")); os.replace(sp + ".tmp", sp)
        lo = min(int(time.mktime(time.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone) for r in mine) if mine else 10**12
        hi = max(int(time.mktime(time.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone) for r in mine) if mine else 0
        todo = [s for s in st["sigs"] if not s["err"] and s["bt"] and s["bt"] >= WIN0 and (s["bt"] < lo or s["bt"] > hi) and s["signature"] not in known]
        print(name, "sigs", len(st["sigs"]), "csv range", lo, hi, "to fetch", len(todo), flush=True)
        op = os.path.join(CR, f"swaps_extra_{name}.jsonl"); have = set()
        if os.path.exists(op): have = {json.loads(l)["signature"] for l in open(op) if l.strip()}
        with open(op, "a") as fh:
            for k, s in enumerate(todo):
                if s["signature"] in have: continue
                tx = get_tx(s["signature"])
                sw = parse_swap(tx, w) if tx else None
                fh.write(json.dumps({"signature": s["signature"], "bt": s["bt"], "swap": sw, "fetched": tx is not None}) + "\n"); fh.flush()
                if k % 50 == 0: print(name, k, len(todo), STATS, flush=True)
    print("DONE", STATS, flush=True)
if __name__ == "__main__": main()
