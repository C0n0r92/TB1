"""Stage 2 (PAPER ONLY, read-only): enrich every copy candidate from on-chain data on the free public RPC.
Per (leader, mint) whose first in-window swap is a buy >= $50 at mcap >= $100k:
  A. leader buy tx -> first-buy check (pre_bal), pool (vault owner), point-in-time reserves -> P0 (post-trade price), liq = 2 x quote side
  B. pool age (getSignaturesForAddress on the pool account, paged back past t-60min) for candidates that could pass the NEW filter
  C. block-level delay pricing: last pool trade at <= slot+5 (~2 s) and <= slot+12 (~5 s) -> P(2s), P(5s)
  D. every later leader sell on that mint: tx -> post-sell price; block delay pricing for the first sell
Resumable; cache per candidate in data/cr/cand/."""
import csv, json, os, sys, time, calendar
from cr_rpc import rpc, get_tx, parse_swap, CR, STATS, WSOL, USDC, USDT
import copy_fee_sensitivity as fs
OI = "/workspace/onchain-intel"
LEAD = {"_benjitrades": "9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc", "bystevenr": "AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx",
        "pointfarmcap": "Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit", "ExactTallTakin": "AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v"}
WIN0 = 1790204400
SHARED_AUTH = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1", "GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL",
               "HLnpSz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC", "WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh"}
QUOTES = (WSOL, USDC, USDT)
CAND = os.path.join(CR, "cand"); BLK = os.path.join(CR, "blocks")

def iso2t(s): return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
_sup = {}
def supply(mint):
    if mint.endswith("pump"): return 1e9
    p = os.path.join(CR, "supply.json"); d = json.load(open(p)) if os.path.exists(p) else {}
    if mint not in d:
        r = rpc("getTokenSupply", [mint]); d[mint] = float(r["value"]["uiAmountString"]) if isinstance(r, dict) else None
        json.dump(d, open(p, "w"))
    return d[mint]

def load_swaps():
    """csv (Scout) + RPC extension -> {leader: [swap...]} sorted by time. Swap: t, mint, side, usd, px_usd(avg), sig, src."""
    out = {k: [] for k in LEAD}
    for r in csv.DictReader(open(os.path.join(OI, "trader_swaps.csv"))):
        if r["trader"] not in LEAD: continue
        t = iso2t(r["timestamp"]); 
        if t < WIN0: continue
        out[r["trader"]].append(dict(t=t, mint=r["mint"], side=r["side"], usd=float(r["usd_size"]), mcap=float(r["mcap_at_fill"]), sig=r["signature"], src="csv"))
    for k in LEAD:
        p = os.path.join(CR, f"swaps_extra_{k}.jsonl")
        if not os.path.exists(p): continue
        have = {s["sig"] for s in out[k]}
        for l in open(p):
            j = json.loads(l); sw = j.get("swap")
            if not sw or j["signature"] in have or not sw.get("bt") or sw["bt"] < WIN0: continue
            usd = abs(sw["sol"]) * fs.solpx(sw["bt"]) + abs(sw["usdq"])
            if usd < 1 or abs(sw["tokens"]) <= 0: continue
            sp = supply(sw["mint"]) or 0
            out[k].append(dict(t=sw["bt"], mint=sw["mint"], side="buy" if sw["tokens"] > 0 else "sell", usd=usd, mcap=usd / abs(sw["tokens"]) * sp,
                               sig=j["signature"], src="rpc"))
    for k in out: out[k].sort(key=lambda s: s["t"])
    return out

def candidates(sw):
    res = []
    for k, rows in sw.items():
        by = {}
        for s in rows: by.setdefault(s["mint"], []).append(s)
        for m, rs in by.items():
            if rs[0]["side"] != "buy": continue
            b = rs[0]
            if b["usd"] < 50 or b["mcap"] < 1e5: continue
            res.append(dict(leader=k, mint=m, buy=b, later=rs[1:]))
    return res

def _amt(b): return float(b["uiTokenAmount"]["uiAmountString"] or 0)

def pool_trades(meta, keys, mint, skip_owner=None):
    """per pool (vault owner) touched in one tx: base reserve, quote reserve, |dbase|, and the tx's fill price in that pool
    (|dquote|/|dbase|, quote units per token) -- valid for CP and concentrated pools alike."""
    pre = {b["accountIndex"]: b for b in meta.get("preTokenBalances") or []}; post = {b["accountIndex"]: b for b in meta.get("postTokenBalances") or []}
    out = []
    for i, b in post.items():
        if b["mint"] != mint or b.get("owner") == skip_owner: continue
        db = _amt(b) - (_amt(pre[i]) if i in pre else 0.0)
        if db == 0: continue
        q = None
        for j, c in post.items():
            if c.get("owner") == b.get("owner") and c["mint"] in QUOTES:
                dq = _amt(c) - (_amt(pre[j]) if j in pre else 0.0)
                if dq != 0 and (q is None or _amt(c) > q[0]): q = (_amt(c), c["mint"], dq)
        out.append(dict(owner=b.get("owner"), base=_amt(b), dbase=db, quote=q[0] if q else None, qmint=q[1] if q else None,
                        fill=abs(q[2] / db) if q else None))
    return out

def pool_state(tx, mint, wallet):
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
    ps = pool_trades(tx["meta"], keys, mint, wallet)
    if not ps: return None
    qp = [p for p in ps if p["quote"]]
    best = dict(max(qp or ps, key=lambda p: abs(p["dbase"])))
    best["alt"] = [p for p in qp if p["owner"] != best["owner"]]
    return best

def usd(p, t): return (fs.solpx(t) if p["qmint"] == WSOL else 1.0)

def liq_usd(ps, t, px_usd):
    """DexScreener-style liquidity of the deepest SOL/USD-quoted pool touched: quote reserve + base reserve x price."""
    if not ps or not ps.get("quote"): return None
    v = lambda p: p["quote"] * usd(p, t) + p["base"] * px_usd
    return max([v(ps)] + [v(p) for p in ps.get("alt", [])])

def block_trades(slot, mints):
    """last trade (fill price) per (pool owner, mint) for our mints in one block. Cached."""
    p = os.path.join(BLK, f"{slot}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        if set(mints) <= set(d["mints"]): return d
    r = rpc("getBlock", [slot, {"encoding": "jsonParsed", "transactionDetails": "accounts", "maxSupportedTransactionVersion": 1, "rewards": False, "commitment": "confirmed"}])
    if r == "FAIL": return None
    d = {"mints": sorted(set(mints)), "skipped": r is None, "res": {}, "bt": (r or {}).get("blockTime")}
    if r:
        ms = set(mints)
        for tx in r.get("transactions", []):
            m = tx.get("meta") or {}
            if m.get("err"): continue
            hit = {b["mint"] for b in (m.get("postTokenBalances") or []) if b["mint"] in ms}
            for mint in hit:
                for pt in pool_trades(m, None, mint):
                    if pt["fill"]: d["res"][f'{pt["owner"]}|{mint}'] = [pt["fill"], pt["dbase"]]
    json.dump(d, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    return d

def delayed_drift(ps, mint, slot, mints):
    """drift(d) = fill of the last pool trade at <= slot+5 (~2 s) / <= slot+12 (~5 s), over the leader's own fill in that pool.
    No trade in the window -> previous value (1.0 = the leader's fill). Positive drift on a buy = we pay more."""
    if not ps or not ps.get("fill"): return None
    out = {}; prev = 1.0
    for lo, hi, tag in ((slot + 1, slot + 5, "2s"), (slot + 6, slot + 12, "5s")):
        got = None
        for s in range(hi, lo - 1, -1):
            d = block_trades(s, mints)
            if d is None: return None
            v = d["res"].get(f'{ps["owner"]}|{mint}')
            if v: got = v[0] / ps["fill"]; out[tag + "_slot"] = s; break
        if got: prev = got
        out[tag] = prev; out[tag + "_trade"] = got is not None
    return out

def pool_age(owner, before_sig, t, max_pages=6):
    """seconds since the pool account's first tx if reachable within max_pages; 99999 = older than 1 h; None = unknown."""
    before = before_sig
    for _ in range(max_pages):
        r = rpc("getSignaturesForAddress", [owner, {"limit": 1000, "before": before}])
        if r == "FAIL": return None
        if not r: return 0
        last = r[-1]
        if (last.get("blockTime") or t) < t - 3600: return 99999
        if len(r) < 1000: return t - (last.get("blockTime") or t)
        before = last["signature"]
    return None

def main(stages="ABCD"):
    sw = load_swaps(); cs = candidates(sw)
    mints = sorted({c["mint"] for c in cs})
    print("candidates", len(cs), {k: sum(c["leader"] == k for c in cs) for k in LEAD}, flush=True)
    for n, c in enumerate(cs):
        p = os.path.join(CAND, f'{c["leader"]}_{c["mint"]}.json')
        e = json.load(open(p)) if os.path.exists(p) else {"leader": c["leader"], "mint": c["mint"], "buy": c["buy"]}
        e["buy"] = c["buy"]; e["later"] = c["later"]; w = LEAD[c["leader"]]
        if "A" in stages and "ps" not in e:
            tx = get_tx(c["buy"]["sig"])
            if tx and tx.get("meta"):
                s = parse_swap(tx, w); e["pre_bal"] = s["pre_bal"] if s else None; e["slot"] = tx.get("slot")
                e["ps"] = pool_state(tx, c["mint"], w)
                e["leader_px"] = (abs(s["sol"]) * fs.solpx(c["buy"]["t"]) + abs(s["usdq"])) / abs(s["tokens"]) if s and s["tokens"] else c["buy"]["mcap"] / (supply(c["mint"]) or 1)
                e["mcap"] = e["leader_px"] * (supply(c["mint"]) or 0); e["liq"] = liq_usd(e["ps"], c["buy"]["t"], e["leader_px"])
        if (e.get("pre_bal") or 0) > 1e-9:          # not a first buy (held before the window): never copied -> no more calls
            json.dump(e, open(p + ".tmp", "w")); os.replace(p + ".tmp", p); continue
        newish = e.get("ps") and (e.get("mcap") or c["buy"]["mcap"]) >= 1e6 and (e.get("liq") or 0) >= 1e5
        if "B" in stages and newish and "age_s" not in e:
            e["age_s"] = None if e["ps"]["owner"] in SHARED_AUTH else pool_age(e["ps"]["owner"], c["buy"]["sig"], c["buy"]["t"])
        if "C" in stages and e.get("ps") and "dpx" not in e and e.get("slot"):
            e["dpx"] = delayed_drift(e["ps"], c["mint"], e["slot"], mints)
        if "D" in stages and e.get("ps") and "sells" not in e:
            sells = []
            from cr_candles import flat_time
            H = flat_time(c["buy"]["t"])
            for s in c["later"]:
                if s["side"] != "sell": continue
                if s["t"] > H: break                     # copies are flat by 08:00 Dublin: later sells never matter
                tx = get_tx(s["sig"]); ps = pool_state(tx, c["mint"], w) if tx and tx.get("meta") else None
                sw_ = parse_swap(tx, w) if tx else None
                sells.append(dict(sig=s["sig"], t=s["t"], slot=(tx or {}).get("slot"), pool=ps, avg_px=((abs(sw_["sol"]) * fs.solpx(s["t"]) + abs(sw_["usdq"])) / abs(sw_["tokens"])) if sw_ and sw_["tokens"] else s["mcap"] / (supply(c["mint"]) or 1),
                                  tokens=abs(sw_["tokens"]) if sw_ else None, pre_bal=sw_["pre_bal"] if sw_ else None, owner=(ps or {}).get("owner")))
            if sells and sells[0]["slot"] and sells[0]["pool"]:
                sells[0]["dpx"] = delayed_drift(sells[0]["pool"], c["mint"], sells[0]["slot"], mints)
            e["sells"] = sells
        json.dump(e, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
        if n % 10 == 0: print(n, len(cs), c["leader"], STATS, flush=True)
    print("DONE", STATS, flush=True)

if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else "ABCD")
