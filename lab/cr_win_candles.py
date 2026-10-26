"""PAPER ONLY. GeckoTerminal candles for the winners replay via bf_common.gecko (shared <=4/min lock). Per trade: 1-min candles
[entry-2m, entry+~16h] (1 call), plus 15-min candles to the long horizon (min(leader exit+24h, entry+7d)) when that is beyond.
Pool: the leader's entry pool (bonding curve / AMM owner) unless shared-authority, else Scout's context_pool; falls back to context_pool on 404/empty."""
import json, os, glob, time
import bf_common
from cr_enrich import SHARED_AUTH
CR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cr"); WD = os.path.join(CR, "win"); WC = os.path.join(CR, "wcandles")
G = "https://api.geckoterminal.com/api/v2/networks/solana"
def hlong(e): return min(e["exit_t"] + 86400, e["t"] + 7 * 86400)
def get(pool, mint, tf, agg, before):
    j = bf_common.gecko(f"{G}/pools/{pool}/ohlcv/{tf}?aggregate={agg}&limit=1000&before_timestamp={before}&currency=usd&token={mint}")
    if not j or j.get("_404"): return None
    return sorted(j.get("data", {}).get("attributes", {}).get("ohlcv_list") or [])
def fetch(e):
    p = os.path.join(WC, os.path.basename(e["_f"]))
    if os.path.exists(p): return False
    own = (e.get("ps") or {}).get("owner"); ctx = (e.get("scout") or {}).get("context_pool")
    pools = [x for x in [own if own and own not in SHARED_AUTH else None, ctx] if x]
    if not pools and e.get("src") == "post_selection":
        j = bf_common.gecko(f"{G}/tokens/{e['mint']}/pools?page=1"); ps = (j or {}).get("data") or []
        pools = [ps[0]["attributes"]["address"]] if ps else []
    H = hlong(e); out = dict(H=H, rows1=[], rows15=[], pool=None, tried=pools, calls=0)
    for pool in pools:
        r1 = get(pool, e["mint"], "minute", 1, min(H, e["t"] + 990 * 60)); out["calls"] += 1
        r1 = [r for r in (r1 or []) if r[0] >= e["t"] - 120]
        if r1: out["pool"] = pool; out["rows1"] = r1; break
    if out["pool"] and H > e["t"] + 990 * 60:
        out["rows15"] = [r for r in (get(out["pool"], e["mint"], "minute", 15, H) or []) if r[0] >= e["t"]]; out["calls"] += 1
        # migrated tokens: curve pool stops trading at migration -> continue on the context pool
        last = max([r[0] for r in out["rows1"] + out["rows15"]] or [0])
        if ctx and ctx != out["pool"] and last < min(H, e["exit_t"]) - 3600:
            out["rows15_ctx"] = [r for r in (get(ctx, e["mint"], "minute", 15, H) or []) if r[0] >= e["t"]]; out["calls"] += 1
    json.dump(out, open(p + ".tmp", "w")); os.replace(p + ".tmp", p); return True
def main():
    while True:
        fs_ = sorted(glob.glob(os.path.join(WD, "*.json")))
        todo = []
        for f in fs_:
            if os.path.basename(f).startswith("_") or os.path.exists(os.path.join(WC, os.path.basename(f))): continue
            e = json.load(open(f)); e["_f"] = f
            if "ps" in e: todo.append(e)
        todo.sort(key=lambda e: (e["label"] not in ("neodot", "onlyzhynx"), e["t"]))
        for e in todo:
            fetch(e); print(e["label"], e["mint"][:8], flush=True)
        if not todo:
            if os.system("pgrep -f cr_win_fetch.py >/dev/null") != 0: break
            time.sleep(60)
if __name__ == "__main__": main()
