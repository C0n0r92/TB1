"""GeckoTerminal free API (no key): 1-minute OHLCV per pool, price in quote token (currency=token). Cached; ~25 calls/min."""
import json, os, time, urllib.request, sys
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "gt"); os.makedirs(D, exist_ok=True)
_last = [0.0]
def call(url, tries=6):
    for k in range(tries):
        dt = time.time() - _last[0]
        if dt < 2.5: time.sleep(2.5 - dt)
        _last[0] = time.time()
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "lab2-research"}), timeout=40))
        except Exception as e:
            if "404" in str(e): return None
            time.sleep(10 * (k + 1))
    raise RuntimeError("gt failed " + url)
def candles(pool, t0, t1):
    f = os.path.join(D, f"{pool}_{t0}_{t1}.json")
    if os.path.exists(f): return json.load(open(f))
    out = {}; before = t1 + 60
    while True:
        r = call(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&currency=token&before_timestamp={before}")
        lst = (r or {}).get("data", {}).get("attributes", {}).get("ohlcv_list", []) if r else []
        for c in lst: out[c[0]] = c
        if not lst or min(c[0] for c in lst) <= t0 or len(lst) < 1000: break
        before = min(c[0] for c in lst)
    res = sorted(c for c in out.values() if t0 - 60 <= c[0] <= t1 + 60)
    json.dump(res, open(f, "w")); return res
if __name__ == "__main__":
    T = json.load(open("legs.json")); S = json.load(open("sigs_summary.json"))
    for tr in T:
        if S.get(str(tr["i"]), {}).get("skip"): continue
        legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]
        for o in S[str(tr["i"])]:
            c = candles(o, min(l["ts"] for l in legs) - 60, max(l["ts"] for l in legs) + 120)
            print(tr["i"], tr["sym"], o[:6], len(c), flush=True)
