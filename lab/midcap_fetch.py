#!/usr/bin/env python3
"""Mid-cap momentum data fetch (paper research). Free APIs only: GeckoTerminal (discovery + 1h OHLCV) and DexScreener
(liquidity/mcap/pair-age cross-check). HARD BUDGET: <= 8 requests/minute across BOTH hosts (one global 7.6 s gap = 7.9/min,
retries included) because another Lab job and the radar share the ~30/min limit. Everything cached in data/midcap/;
rerun = resume (cached files are never refetched)."""
import json, os, sys, time, urllib.request, urllib.error
LAB = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(LAB, "data", "midcap"); OH = os.path.join(D, "ohlcv")
os.makedirs(OH, exist_ok=True)
GAP = 7.6;   # Zero 23:33: GT+DexScreener <= 8 req/min (was 10.5 s / 6 per min)
_last = [0.0]; LOG = os.path.join(D, "requests.log")
UA = {"User-Agent": "lab-paper-backtest/1.0", "Accept": "application/json"}
GT = "https://api.geckoterminal.com/api/v2"
SOL_USDC_POOL = "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"   # Orca SOL/USDC (deep, long history)

def get(url):
    for attempt in range(3):
        w = GAP - (time.time() - _last[0])
        if w > 0: time.sleep(w)
        _last[0] = time.time()
        code = 200
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                out = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            out, code = None, e.code
        except Exception as e:
            out, code = None, -1
        open(LOG, "a").write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {code} {url}\n")
        if out is not None: return out
        if code == 429: time.sleep(30 * (attempt + 1)); continue
        if code in (-1,) or code >= 500: time.sleep(5); continue
        return None
    return None

def cached(path, url):
    if os.path.exists(path): return json.load(open(path))
    d = get(url)
    if d is not None: json.dump(d, open(path + ".tmp", "w")); os.replace(path + ".tmp", path)
    return d

STABLE_LST = {"USDC", "USDT", "SOL", "WSOL", "JITOSOL", "MSOL", "BSOL", "JUPSOL", "INF", "USDS", "PYUSD", "USD1", "USDG", "EURC",
              "BNSOL", "HSOL", "DSOL", "VSOL", "CBBTC", "WBTC", "WETH", "ETH", "BTC", "FDUSD", "USDE", "SUSDE", "JLP", "XBTC", "ZBTC"}

def discover():
    pools = {}
    srcs = [(f"pools_{so}_{pg}", f"{GT}/networks/solana/pools?page={pg}&sort={so}&include=base_token,quote_token")
            for so in ("h24_volume_usd_desc", "h24_tx_count_desc") for pg in range(1, 11)]
    srcs += [(f"dex_{dx}_{pg}", f"{GT}/networks/solana/dexes/{dx}/pools?page={pg}&sort=h24_volume_usd_desc&include=base_token,quote_token")
             for dx in ("raydium", "orca", "raydium-clmm", "meteora", "pumpswap", "meteora-damm-v2") for pg in range(1, 6)]
    for key, url in srcs:
        if True:
            d = cached(os.path.join(D, key + ".json"), url)
            if not d: continue
            toks = {i["id"]: i["attributes"] for i in d.get("included", [])}
            for p in d.get("data", []):
                a = p["attributes"]; rel = p["relationships"]
                b = toks.get(rel["base_token"]["data"]["id"], {}); q = toks.get(rel["quote_token"]["data"]["id"], {})
                sym = (b.get("symbol") or "").upper()
                if sym in STABLE_LST or (q.get("symbol") or "").upper() not in ("SOL", "WSOL", "USDC", "USDT"): continue
                mint = b.get("address"); liq = float(a.get("reserve_in_usd") or 0)
                mc = float(a.get("market_cap_usd") or a.get("fdv_usd") or 0)
                if not mint: continue
                if mint not in pools or liq > pools[mint]["liq"]:
                    pools[mint] = dict(mint=mint, symbol=b.get("symbol"), pool=a["address"], liq=liq, mcap=mc,
                                       fdv=float(a.get("fdv_usd") or 0), price=float(a.get("base_token_price_usd") or 0),
                                       pool_created=a.get("pool_created_at"), dex=rel.get("dex", {}).get("data", {}).get("id"))
    json.dump(list(pools.values()), open(os.path.join(D, "discovered.json"), "w"), indent=0)
    return list(pools.values())

def dexscreener(mints):
    out = {}
    for i in range(0, len(mints), 30):
        ch = mints[i:i + 30]
        d = cached(os.path.join(D, f"dexs_{i // 30}_{len(ch)}.json"), "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ch))
        for p in d or []:
            m = p.get("baseToken", {}).get("address")
            if m not in ch: continue
            o = out.setdefault(m, dict(liq_total=0.0, mcap=0.0, first_pair=None))
            o["liq_total"] += float((p.get("liquidity") or {}).get("usd") or 0)
            o["mcap"] = max(o["mcap"], float(p.get("marketCap") or 0))
            pc = p.get("pairCreatedAt")
            if pc: o["first_pair"] = min(o["first_pair"] or pc, pc)
    return out

def ohlcv(pool, pages=3, tf="hour", agg=1):
    rows = {}
    before = None
    for k in range(pages):
        path = os.path.join(OH, f"{pool}_{k}.json" if tf == "hour" else f"{pool}_{tf}{agg}_{k}.json")
        url = f"{GT}/networks/solana/pools/{pool}/ohlcv/{tf}?aggregate={agg}&limit=1000&currency=usd&token=base"
        if k:
            if before is None: break
            url += f"&before_timestamp={before}"
        d = cached(path, url)
        lst = ((d or {}).get("data") or {}).get("attributes", {}).get("ohlcv_list") or []
        for r in lst: rows[int(r[0])] = r
        if len(lst) < 1000: break
        before = min(int(r[0]) for r in lst)
    return sorted(rows.values())

if __name__ == "__main__":
    t0 = time.time()
    pools = discover()
    now = time.time()
    def age_days(p):
        try:
            import datetime as dt
            return (now - dt.datetime.fromisoformat(p["pool_created"].replace("Z", "+00:00")).timestamp()) / 86400
        except Exception: return 0
    # loose pre-filter (current snapshot) so universe members that were in range earlier but drifted are still fetched
    pre = [p for p in pools if 1.5e6 <= max(p["mcap"], p["fdv"] if p["mcap"] == 0 else 0) <= 6e8 and p["liq"] >= 1.5e5 and age_days(p) >= 8]
    ds = dexscreener([p["mint"] for p in pre])
    for p in pre:
        x = ds.get(p["mint"], {}); p["ds_liq_total"] = x.get("liq_total"); p["ds_mcap"] = x.get("mcap"); p["ds_first_pair_ms"] = x.get("first_pair")
    json.dump(pre, open(os.path.join(D, "prefilter.json"), "w"), indent=0)
    print(f"discovered {len(pools)}, prefilter {len(pre)}", flush=True)
    todo = [("SOL", SOL_USDC_POOL)] + [(p["mint"], p["pool"]) for p in sorted(pre, key=lambda p: -p["liq"])]
    P = {p["mint"]: p for p in pre}
    for i, (m, pool) in enumerate(todo):
        done = os.path.exists(os.path.join(OH, f"rows_{m}.json"))
        rows = ohlcv(pool, pages=3 if done or m == "SOL" else 2)    # 2 pages (~83 d) is enough for a 60-day test + EMA200 warm-up
        json.dump(rows, open(os.path.join(OH, f"rows_{m}.json"), "w"))
        msg = f"{i + 1}/{len(todo)} {m[:8]} {len(rows)} bars"
        p = P.get(m)
        if p and 2.5e6 <= (p["mcap"] or p["fdv"]) <= 1.2e9 and p["liq"] >= 2.5e5:      # 15m only where the token can be in the live universe
            r15 = ohlcv(pool, pages=4, tf="minute", agg=15)                      # 4 x 1000 x 15 min = ~41.7 days
            json.dump(r15, open(os.path.join(OH, f"rows15_{m}.json"), "w")); msg += f", 15m {len(r15)} bars"
        print(msg + f"  t+{(time.time() - t0) / 60:.1f} min", flush=True)
    print("DONE", flush=True)
