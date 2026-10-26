#!/usr/bin/env python3
"""Per-trade results for copyfomo traders' Solana wallets (Helius enhanced API, type=SWAP).
Wallet mappings come from data/trader_wallets.json (only mappings with recorded evidence).
Output: trader_trades.csv  trader,wallet,mint,buy_at,sell_at,buy_usd,pnl_pct
FIFO-free simple model: per (wallet,mint) round = buys until position closes (sold >=95% of bought tokens).
Quote leg valued in USD: USDC/USDT 1:1, SOL at the SOL/USD rate in data/solusd.json (GeckoTerminal daily close) else latest.
Open positions: sell_at empty, pnl_pct empty."""
import os, sys, json, time, csv, requests
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE, _helius_key, budget_take
DAYS = int(os.environ.get("TT_DAYS", "28")); MAXP = int(os.environ.get("TT_MAXPAGES", "20"))
USD = {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
SOL = "So11111111111111111111111111111111111111112"
LOG = os.path.join(BASE, "data", "rpc_calls.log")

def fetch(addr, name):
    key = _helius_key(); fn = os.path.join(BASE, "data", f"enh_{name}_all.json")
    have = json.load(open(fn)) if os.path.exists(fn) else []
    sigs = {x["signature"] for x in have}; newest = max([x["timestamp"] for x in have], default=0)
    cutoff = time.time() - DAYS * 86400; before = None; got = []
    for _ in range(MAXP):
        if not budget_take(100, "enhanced"): print(f"budget: stopped enhanced paging for {name}", flush=True); break
        p = {"api-key": key, "type": "SWAP", "limit": 100}
        if before: p["before"] = before
        r = requests.get(f"https://api.helius.xyz/v0/addresses/{addr}/transactions", params=p, timeout=60)
        open(LOG, "a").write(f"{int(time.time())} helius-enhanced 1\n"); time.sleep(0.3)
        d = r.json() if r.ok else []
        if isinstance(d, dict):   # Helius may answer "continue with before=<sig>" when the window had no swaps
            msg = str(d.get("error", "")); before = msg.split("before` parameter set to ")[-1].split(".")[0].strip() if "before" in msg else None
            if not before: break
            continue
        if not d: break
        got += [x for x in d if x["signature"] not in sigs]
        before = d[-1]["signature"]
        if d[-1]["timestamp"] < max(cutoff, newest): break
    allx = sorted(have + got, key=lambda x: x["timestamp"])
    json.dump(allx, open(fn, "w")); return [x for x in allx if x["timestamp"] >= cutoff]

def solusd():
    fn = os.path.join(BASE, "data", "solusd.json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 6 * 3600: return json.load(open(fn))
    # SOL/USDC Raydium pool on GeckoTerminal, daily OHLCV
    u = "https://api.geckoterminal.com/api/v2/networks/solana/pools/58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2/ohlcv/day?limit=40"
    d = {}
    try:
        for o in requests.get(u, timeout=30).json()["data"]["attributes"]["ohlcv_list"]:
            d[time.strftime("%Y-%m-%d", time.gmtime(o[0]))] = o[4]
    except Exception: pass
    json.dump(d, open(fn, "w")); return d

def legs(x, addr):
    """net balance changes for addr in this swap. Uses accountData (real pre/post deltas: native SOL of the wallet + token
    balances owned by it) so multi-hop routes that pass USDT/wSOL through the wallet net out. Falls back to transfers."""
    dl = {}
    if x.get("accountData"):
        for a in x["accountData"]:
            if a.get("account") == addr and a.get("nativeBalanceChange"): dl[SOL] = dl.get(SOL, 0) + a["nativeBalanceChange"] / 1e9
            for t in a.get("tokenBalanceChanges") or []:
                if t.get("userAccount") == addr:
                    r = t["rawTokenAmount"]; dl[t["mint"]] = dl.get(t["mint"], 0) + int(r["tokenAmount"]) / 10 ** int(r["decimals"])
        return {m: v for m, v in dl.items() if abs(v) > 1e-9}
    for t in x.get("tokenTransfers") or []:
        a = float(t.get("tokenAmount") or 0); m = t["mint"]
        if t.get("toUserAccount") == addr: dl[m] = dl.get(m, 0) + a
        if t.get("fromUserAccount") == addr: dl[m] = dl.get(m, 0) - a
    for n in x.get("nativeTransfers") or []:
        a = n["amount"] / 1e9
        if n.get("toUserAccount") == addr: dl[SOL] = dl.get(SOL, 0) + a
        if n.get("fromUserAccount") == addr: dl[SOL] = dl.get(SOL, 0) - a
    return dl

def trades(name, addr, txs, px):
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    def usd(m, a, t): return a if m in USD else a * float(px.get(time.strftime("%Y-%m-%d", time.gmtime(t))) or px.get(max(px), 0) if px else 0)
    pos, rows = {}, []
    for x in txs:
        dl = legs(x, addr); q = [(m, a) for m, a in dl.items() if m in USD or m == SOL]
        toks = [(m, a) for m, a in dl.items() if m not in USD and m != SOL and abs(a) > 0]
        if len(toks) != 1 or not q: continue
        m, a = toks[0]; qv = sum(usd(qm, qa, x["timestamp"]) for qm, qa in q)
        p = pos.setdefault(m, {"buy_at": None, "bought": 0, "sold": 0, "cost": 0, "proceeds": 0})
        if a > 0 and qv < 0:
            if p["buy_at"] is None: p["buy_at"] = x["timestamp"]
            p["bought"] += a; p["cost"] += -qv
        elif a < 0 and qv > 0 and p["buy_at"] is not None:
            p["sold"] += -a; p["proceeds"] += qv
            if p["sold"] >= 0.95 * p["bought"]:
                rows.append([name, addr, m, iso(p["buy_at"]), iso(x["timestamp"]), round(p["cost"], 2),
                             round((p["proceeds"] / p["cost"] - 1) * 100, 1) if p["cost"] else ""]); pos.pop(m)
    for m, p in pos.items():
        if p["buy_at"]: rows.append([name, addr, m, iso(p["buy_at"]), "", round(p["cost"], 2), ""])
    return sorted(rows, key=lambda r: r[3])

if __name__ == "__main__":
    W = json.load(open(os.path.join(BASE, "data", "trader_wallets.json")))
    px = solusd(); out = []
    for name, v in W.items():
        if not v.get("evidence"): continue
        txs = fetch(v["solana"], name); r = trades(name, v["solana"], txs, px); out += r
        print(name, "swaps", len(txs), "rounds", len(r), "closed", sum(1 for x in r if x[4]))
    with open(os.path.join(BASE, "trader_trades.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["trader", "wallet", "mint", "buy_at", "sell_at", "buy_usd", "pnl_pct"]); w.writerows(out)
