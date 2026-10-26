"""PAPER ONLY. Fetch GeckoTerminal 1-min candles for the 7 recorded live copy signals (selfcopy paper entries / copylive actions).
Gentle: 7.5 s between calls (~8/min), cached in data/fe/."""
import json, os, time, urllib.request, calendar
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fe"); os.makedirs(D, exist_ok=True)
MINTS = ["J9WL4zQVCFvLTydjtHoMGcLasjhRMZomnVmp4Y2cpump", "5UHeHyfB4fo7sy4hHN9gGBJvYSQdz7w6ienZoSTDpump", "HgBRWfYxEfvPhtqkaeymCQtHCrKE46qQ43pKe8HCpump",
         "2j5SaS7xy776qCBpyPQbZjyQSAtKiFgrwjfErthnW2ZM", "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump", "98kfF7rmsg1QDUEoCqNE7g7M1FdrTt92TEp2CLzypump",
         "y1AZt42vceCmStjW4zetK3VoNarC1VxJ5iDjpiupump"]
last = [0.0]
def get(u):
    w = 7.5 - (time.time() - last[0])
    if w > 0: time.sleep(w)
    last[0] = time.time()
    req = urllib.request.Request(u, headers={"Accept": "application/json", "User-Agent": "lab-paper-research"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
def main(mints):
    for m in mints:
        p = os.path.join(D, m + ".json")
        if os.path.exists(p): continue
        try:
            pools = get(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{m}/pools?page=1")["data"]
            pools.sort(key=lambda x: -float(x["attributes"].get("reserve_in_usd") or 0)); pool = pools[0]["attributes"]["address"]
            base_is = pools[0]["relationships"]["base_token"]["data"]["id"].endswith(m)
            o = get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000&currency=usd&token={'base' if base_is else 'quote'}")
            rows = sorted(o["data"]["attributes"]["ohlcv_list"])
            json.dump(dict(mint=m, pool=pool, rows1=rows, fetched=int(time.time())), open(p, "w"))
            print(m[:8], pool, len(rows), rows[0][0] if rows else None, rows[-1][0] if rows else None, flush=True)
        except Exception as ex: print(m[:8], "ERR", ex, flush=True)
if __name__ == "__main__":
    main(MINTS)
