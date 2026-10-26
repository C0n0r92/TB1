#!/usr/bin/env python3
"""Job 1: early-buyer mining on past >=100x Solana (pump.fun) runners. Re-runnable, cached.
1. candidates: pump.fun mints from GeckoTerminal pumpswap pool lists (top by 24h volume / tx count) + data/runner_candidates.txt
   + data/tokens.txt; operator (full-curve dev buy) coins excluded.
2. peak check: launch price = first on-chain buy price (SOL/token, from the bonding-curve history) x SOLUSD;
   peak = max hourly CLOSE across the token's GeckoTerminal pools (closes, not wicks). Keep peak_x >= 100.
3. first 20 distinct buyers (signers, not the creator) per runner.
4. keep wallets active in last 30 d; drop bots (>=1000 sigs within <72h, or median gap between own txs < 10 s).
5. profile: last-30d buys (Helius getTransactionsForAddress, token-in transfers, wallet-signed, paid in SOL/USDC) + current holdings.
6. clusters: >=3 kept wallets buying the same mint within WINDOW_MIN minutes -> cluster_buys.jsonl.
Outputs: data/early_buyer_wallets.json, merged into smart_wallets.json (source "early_buyer"), cluster_buys.jsonl."""
import os, sys, json, time, statistics, requests, re, calendar
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE, rpc, sigs, _helius_key, HAVE_HELIUS, budget_take
import early_buyers
MIN_X = 100; N_BUYERS = 20; MAX_RUNNERS = int(os.environ.get("MAX_RUNNERS", "20")); WINDOW_MIN = int(os.environ.get("CLUSTER_WINDOW_MIN", "30"))
NOW = time.time(); D30 = NOW - 30 * 86400
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
MD = os.path.join(BASE, "data", "miner"); os.makedirs(MD, exist_ok=True)
GT = "https://api.geckoterminal.com/api/v2"; _gt_last = [0]
LOG = os.path.join(BASE, "data", "rpc_calls.log")
QUOTE = {"So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
def gt(path, params=None):
    for a in range(4):
        w = 2.5 - (time.time() - _gt_last[0])
        if w > 0: time.sleep(w)
        _gt_last[0] = time.time()
        try:
            r = requests.get(GT + path, params=params, timeout=30, headers={"Accept": "application/json"})
            if r.status_code == 429: time.sleep(15); continue
            return r.json() if r.ok else None
        except Exception: time.sleep(3)
def cache(name, fn):
    p = os.path.join(MD, name + ".json")
    if os.path.exists(p): return json.load(open(p))
    v = fn(); json.dump(v, open(p, "w")); return v

def sol_usd():
    d = gt("/networks/solana/pools/58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2/ohlcv/day", {"limit": 90}) or {}
    return {time.strftime("%Y-%m-%d", time.gmtime(o[0])): o[4] for o in (d.get("data") or {}).get("attributes", {}).get("ohlcv_list", [])}

def candidates():
    c = {}
    p = os.path.join(BASE, "data", "runner_candidates.txt")
    for f in [p, os.path.join(BASE, "data", "tokens.txt")]:
        if os.path.exists(f):
            for l in open(f):
                if l.strip() and not l.startswith("#"): c.setdefault(l.split()[0], l.split()[1] if len(l.split()) > 1 else "")
    pl = cache("gt_pools_" + time.strftime("%Y%m%d"), lambda: [
        {"token": x["relationships"]["base_token"]["data"]["id"].split("_", 1)[1], "name": x["attributes"]["name"]}
        for sort in ("h24_volume_usd_desc", "h24_tx_count_desc") for pg in (1, 2, 3)
        for x in ((gt("/networks/solana/dexes/pumpswap/pools", {"page": pg, "sort": sort}) or {}).get("data") or [])])
    for x in pl: c.setdefault(x["token"], x["name"].split(" /")[0])
    ops = json.load(open(os.path.join(BASE, "data", "operator_chains.json"))) if os.path.exists(os.path.join(BASE, "data", "operator_chains.json")) else {}
    c = {m: s for m, s in c.items() if m.endswith("pump") and m not in ops}
    # cheap prefilter (DexScreener, 30 mints/call): keep coins whose best pair shows mcap >= $100k now, or volume24h >= $500k
    # (dead runners can be added by hand in data/runner_candidates.txt; those always pass)
    manual = {l.split()[0] for l in open(p)} if os.path.exists(p) else set()
    keep = {}
    ms = list(c)
    for i in range(0, len(ms), 30):
        try: P = requests.get("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ms[i:i+30]), timeout=30).json()
        except Exception: P = []
        best = {}
        for q in P or []:
            t = q["baseToken"]["address"]; best[t] = max(best.get(t, 0), float(q.get("marketCap") or 0), 0.0)
            if float((q.get("volume") or {}).get("h24") or 0) >= 500000: best[t] = max(best[t], 1e9)
        for t, v in best.items():
            if v >= 100000: keep[t] = c[t]
        time.sleep(0.3)
    for m in manual:
        if m in c: keep[m] = c[m]
    return keep

def peak(mint):
    def f():
        pools = (gt(f"/networks/solana/tokens/{mint}/pools", {"page": 1}) or {}).get("data") or []
        best = None
        for p in pools[:3]:
            addr = p["attributes"]["address"]
            o = (gt(f"/networks/solana/pools/{addr}/ohlcv/hour", {"limit": 1000, "token": "base", "currency": "usd"}) or {}).get("data")
            L = (o or {}).get("attributes", {}).get("ohlcv_list") or []
            if not L: continue
            mx = max(L, key=lambda x: x[4])
            if best is None or mx[4] > best["peak_close_usd"]:
                best = {"pool": addr, "dex": p["relationships"]["dex"]["data"]["id"], "peak_close_usd": mx[4], "peak_at": iso(mx[0]), "n_candles": len(L),
                        "fdv_now": p["attributes"].get("fdv_usd")}
        return best
    return cache("peak_" + mint, f)

def launch_price(e):
    b = sorted([x for x in e["events"] if x["side"] == "buy" and x["tokens"] > 0 and x["sol"] < 0], key=lambda x: (x["slot"], x["secs"]))
    for x in b:   # first buy priced in SOL
        return -x["sol"] / x["tokens"], x["ts"]
    return None, None

def first_buyers(e):
    out, seen = [], set()
    for x in sorted(e["events"], key=lambda x: (x["slot"], x["secs"])):
        if x["side"] != "buy" or x["owner"] == e["creator"] or x["owner"] in seen: continue
        seen.add(x["owner"]); out.append(x)
        if len(out) >= N_BUYERS: break
    return out

def activity(addr):
    def f():
        S = sigs(addr, limit_pages=1)
        ts = sorted([s["blockTime"] for s in S if s.get("blockTime")])
        if not ts: return {"n": 0, "last": None, "span_h": None, "median_gap_s": None}
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        return {"n": len(S), "last": ts[-1], "first_in_page": ts[0], "span_h": round((ts[-1] - ts[0]) / 3600, 1), "median_gap_s": statistics.median(gaps) if gaps else None}
    return cache("act_" + addr, f)

def gtfa(addr, after, token=None):
    key = _helius_key(); out, tok = [], None
    for _ in range(3):   # <= 300 token-in txs per wallet (30 credits)
        cfg = {"transactionDetails": "full", "sortOrder": "desc", "limit": 100, "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
               "filters": {"blockTime": {"gte": int(after)}, "status": "succeeded", "tokenAccounts": "balanceChanged", "tokenTransfer": {"direction": "in"}}}
        if tok: cfg["paginationToken"] = tok
        if not budget_take(10, "gtfa"): break
        try:
            r = requests.post("https://mainnet.helius-rpc.com/?api-key=" + key, json={"jsonrpc": "2.0", "id": 1, "method": "getTransactionsForAddress", "params": [addr, cfg]}, timeout=60).json()
        except Exception: break
        open(LOG, "a").write(f"{int(time.time())} helius-gtfa {max(10, 10 * -(-len((r.get('result') or {}).get('data') or []) // 100))}\n"); time.sleep(0.15)
        res = r.get("result") or {}; out += res.get("data") or []; tok = res.get("paginationToken")
        if not tok or len(res.get("data") or []) < 100: break
    return out

def profile(addr):
    def f():
        buys = []
        for t in gtfa(addr, D30):
            keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
            signers = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"] if isinstance(k, dict) and k.get("signer")]
            if addr not in signers: continue      # airdrops / spam / fee payouts don't count
            m = t["meta"]; pre = {}; post = {}
            for b in m.get("preTokenBalances") or []:
                if b.get("owner") == addr: pre[b["mint"]] = pre.get(b["mint"], 0) + float(b["uiTokenAmount"]["uiAmount"] or 0)
            for b in m.get("postTokenBalances") or []:
                if b.get("owner") == addr: post[b["mint"]] = post.get(b["mint"], 0) + float(b["uiTokenAmount"]["uiAmount"] or 0)
            d = {k: post.get(k, 0) - pre.get(k, 0) for k in set(pre) | set(post)}
            i = keys.index(addr); dsol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9 + d.get("So11111111111111111111111111111111111111112", 0)
            dusd = d.get("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 0) + d.get("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", 0)
            got = [(k, v) for k, v in d.items() if k not in QUOTE and v > 0]
            if len(got) != 1 or not (dsol < -0.005 or dusd < -0.5): continue
            buys.append({"mint": got[0][0], "ts": iso(t["blockTime"]), "sig": t["transaction"]["signatures"][0], "sol": round(dsol, 4), "usd_quote": round(dusd, 2) if dusd else None})
        hold = []
        for prog in ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"):
            r = rpc("getTokenAccountsByOwner", [addr, {"programId": prog}, {"encoding": "jsonParsed"}]) or {}
            for a in (r.get("value") or []):
                inf = a["account"]["data"]["parsed"]["info"]; amt = float(inf["tokenAmount"]["uiAmount"] or 0)
                if amt > 0 and inf["mint"] not in QUOTE: hold.append({"mint": inf["mint"], "amount": amt})
        return {"buys": sorted(buys, key=lambda b: b["ts"]), "holdings": hold, "profiled_at": iso(time.time())}
    p = os.path.join(MD, "prof_" + addr + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600: return json.load(open(p))
    v = f(); json.dump(v, open(p, "w")); return v

MANUAL = {l.split()[0] for l in open(os.path.join(BASE, "data", "runner_candidates.txt")) if l.strip() and not l.startswith("#")} if os.path.exists(os.path.join(BASE, "data", "runner_candidates.txt")) else set()
def main():
    px = sol_usd(); C = candidates(); runners = []
    print("candidates", len(C), flush=True)
    os.environ.setdefault("EARLY_N", "80")
    for m, sym in C.items():
        if len(runners) >= MAX_RUNNERS: break
        pk = peak(m)
        if not pk: continue
        if pk["peak_close_usd"] * 1e9 < 250000: continue     # cannot be 100x from a ~$3-4k pump.fun launch; skip before paying for history
        early_buyers.N = int(os.environ["EARLY_N"])
        try: e = early_buyers.run(m)
        except Exception as ex: print("early fail", m, ex); continue
        if not e.get("creator"): continue
        lp, lts = launch_price(e)
        if not lp: continue
        s = px.get(time.strftime("%Y-%m-%d", time.gmtime(lts))) or px.get(max(px)) if px else None
        if not s: continue
        # launch price = pump.fun curve start (30 SOL virtual / 1,073,000,000 virtual tokens = 2.796e-8 SOL/token, 27.96 SOL mcap);
        # on-chain first-buy prices are unreliable (fee/bundle txs), kept only as info
        lp_onchain = lp; lp = 30 / 1.073e9
        x = pk["peak_close_usd"] / (lp * s)
        r = {"mint": m, "sym": sym, "launch_at": iso(e["create_ts"]), "launch_price_usd": lp * s, "launch_mcap_usd": round(lp * s * 1e9), **pk,
             "peak_mcap_usd": round(pk["peak_close_usd"] * 1e9), "peak_x": round(x, 1), "creator": e["creator"], "first_buy_price_sol_onchain": lp_onchain, "sol_usd_at_launch": s}
        if r["peak_mcap_usd"] > 50e6 and m not in MANUAL: print("  skip: peak mcap > $50M (GeckoTerminal FDV likely manipulated/illiquid)", m); continue
        print(sym, m[:8], "peak_x", r["peak_x"], "peak_mcap", r["peak_mcap_usd"], flush=True)
        if x >= MIN_X: r["first_buyers"] = first_buyers(e); runners.append(r)
    json.dump(runners, open(os.path.join(BASE, "data", "runners_100x.json"), "w"), indent=1)
    # wallets
    rug = json.load(open(os.path.join(BASE, "known_ruggers.json")))["wallets"]
    W = {}
    for r in runners:
        for i, b in enumerate(r["first_buyers"], 1):
            w = W.setdefault(b["owner"], {"address": b["owner"], "early_in": []})
            w["early_in"].append({"mint": r["mint"], "sym": r["sym"], "rank": i, "secs_after_launch": b["secs"], "slot_offset": b["slot_offset"], "sig": b["sig"], "ts": iso(b["ts"]), "sol": b["sol"], "peak_x": r["peak_x"]})
    kept, dropped = {}, {"inactive": 0, "bot": 0, "rugger": 0}
    for a, w in W.items():
        if a in rug: dropped["rugger"] += 1; continue
        act = activity(a)
        if not act["last"] or act["last"] < D30: dropped["inactive"] += 1; continue
        if (act["n"] >= 1000 and act["span_h"] < 72) or (act["median_gap_s"] is not None and act["median_gap_s"] < 10 and act["n"] >= 100): dropped["bot"] += 1; continue
        pr = profile(a)
        bt = sorted(calendar.timegm(time.strptime(b["ts"], "%Y-%m-%dT%H:%M:%SZ")) for b in pr["buys"])
        if len(bt) >= 20 and statistics.median([y - x for x, y in zip(bt, bt[1:])]) < 10: dropped["bot"] += 1; continue
        w.update(activity=act, last_active=iso(act["last"]), buys_30d=pr["buys"], holdings=pr["holdings"][:50], n_holdings=len(pr["holdings"]))
        kept[a] = w
    print("wallets", len(W), "kept", len(kept), "dropped", dropped, flush=True)
    # clusters
    by = {}
    for a, w in kept.items():
        for b in w["buys_30d"]:
            by.setdefault(b["mint"], []).append((calendar.timegm(time.strptime(b["ts"], "%Y-%m-%dT%H:%M:%SZ")), a, b["sig"]))
    clusters = []
    for m, L in by.items():
        L.sort(); best = None
        for i in range(len(L)):
            win = [x for x in L[i:] if x[0] - L[i][0] <= WINDOW_MIN * 60]
            ws = []
            for x in win:
                if x[1] not in ws: ws.append(x[1])
            if len(ws) >= 3 and (best is None or len(ws) > len(best[1])): best = (L[i][0], ws, [x[2] for x in win][:10], win[-1][0])
        if best: clusters.append({"mint": m, "wallets": best[1], "n_wallets": len(best[1]), "first_buy_at": iso(best[0]), "last_buy_in_window_at": iso(best[3]),
                                  "window_min": WINDOW_MIN, "sigs": best[2], "detected_at": iso(NOW), "source": "early_buyer", "is_seed_runner": m in {r["mint"] for r in runners}})
    clusters.sort(key=lambda c: c["first_buy_at"])
    prev = set()
    cp = os.path.join(BASE, "cluster_buys.jsonl")
    if os.path.exists(cp):
        for l in open(cp):
            try: j = json.loads(l); prev.add((j["mint"], j["first_buy_at"]))
            except Exception: pass
    with open(cp, "a") as f:
        for c in clusters:
            if (c["mint"], c["first_buy_at"]) not in prev: f.write(json.dumps(c) + "\n")
    # smart_wallets.json merge (source early_buyer); date_added preserved
    sp = os.path.join(BASE, "data", "early_buyer_wallets.json")
    old = json.load(open(sp)) if os.path.exists(sp) else {}
    out = {}
    for a, w in kept.items():
        out[a] = {"address": a, "source": "early_buyer", "date_added": (old.get(a) or {}).get("date_added") or iso(NOW),
                  "buys": [{"mint": b["mint"], "ts": b["ts"], "sig": b["sig"], "sol": b["sol"]} for b in w["buys_30d"]],
                  "early_in": w["early_in"], "last_active": w["last_active"], "n_holdings": w["n_holdings"],
                  "holdings_top": sorted(w["holdings"], key=lambda h: -h["amount"])[:15], "weight": round(min(0.5, 0.2 * len(w["early_in"])), 2)}
    json.dump(out, open(sp, "w"), indent=1)
    SW = json.load(open(os.path.join(BASE, "smart_wallets.json")))
    SW.setdefault("early_buyer", {}); SW["early_buyer"] = out
    for a, v in (SW.get("smart") or {}).items(): v.setdefault("source", "radar_early_trader")
    SW["schema_notes"] = SW.get("schema_notes", "").split(" | early_buyer:")[0] + " | early_buyer: section 'early_buyer' = first-20 buyers of verified >=100x runners (data/runners_100x.json), active in last 30d, bots dropped; buys = their last-30d wallet-signed buys."
    json.dump(SW, open(os.path.join(BASE, "smart_wallets.json"), "w"), indent=1)
    print("runners", len(runners), "clusters", len(clusters))
    for c in sorted(clusters, key=lambda c: -c["n_wallets"])[:10]: print(" cluster", c["mint"], c["n_wallets"], c["first_buy_at"])

if __name__ == "__main__": main()
