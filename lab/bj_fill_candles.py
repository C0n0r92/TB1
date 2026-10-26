"""PAPER ONLY. Retry GeckoTerminal candles for winners-replay trades whose first pool gave no 1-min data:
look up the token's GT pools and try up to 2 more. Rate limited via bf_common.gecko (6.5 s spacing, shared lock). Backs up the old file."""
import json, os, glob, shutil
import bf_common, cr_win_candles as wc
G = wc.G
def main():
    for f in sorted(glob.glob(os.path.join(wc.WD, "*.json"))):
        if os.path.basename(f).startswith("_"): continue
        p = os.path.join(wc.WC, os.path.basename(f))
        if not os.path.exists(p): continue
        C = json.load(open(p))
        if C.get("rows1") or C.get("retry2"): continue
        e = json.load(open(f))
        j = bf_common.gecko(f"{G}/tokens/{e['mint']}/pools?page=1")
        pools = [x["attributes"]["address"] for x in ((j or {}).get("data") or [])]
        pools = [x for x in pools if x not in C.get("tried", [])][:2]
        H = C["H"]; out = dict(C); out["retry2"] = pools
        for pool in pools:
            r1 = wc.get(pool, e["mint"], "minute", 1, min(H, e["t"] + 990 * 60)); out["calls"] = out.get("calls", 0) + 1
            r1 = [r for r in (r1 or []) if r[0] >= e["t"] - 120]
            if r1:
                out["pool"] = pool; out["rows1"] = r1
                if H > e["t"] + 990 * 60:
                    out["rows15"] = [r for r in (wc.get(pool, e["mint"], "minute", 15, H) or []) if r[0] >= e["t"]]
                break
        shutil.copy(p, p + ".bak-bj")
        json.dump(out, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
        print(e["label"], e["symbol"], "pools", pools, "rows1", len(out["rows1"]), flush=True)
if __name__ == "__main__": main()
