"""PAPER ONLY, read-only. Scout winners batch 1 (/workspace/onchain-intel/winners/trades.csv, read-only) -> on-chain enrichment on the
free public RPC (no Helius): entry tx (first-buy check, pool + fill, pump.fun bonding-curve native-SOL reserves), every leader swap on
that mint via the leader's token account (sells for mirroring), block-level 2 s / 5 s delay pricing for the entry and the first sell.
Also: neodot's round trips AFTER Scout's cutoff (post-selection holdout). Cache: data/cr/win/<w8>_<mint>_<sig8>.json."""
import csv, json, os, sys, time, calendar
from cr_rpc import rpc, get_tx, parse_swap, CR, STATS, WSOL, USDC, USDT
import copy_fee_sensitivity as fs
WIN = "/workspace/onchain-intel/winners"; WD = os.path.join(CR, "win"); BW = os.path.join(CR, "blocks_w")
QUOTES = (WSOL, USDC, USDT)
LABEL = {"9PB1RLFs": "_benjitrades", "AH75Bn6Q": "bystevenr", "5o3kAZLw": "neodot", "zhYnXqK3": "onlyzhynx"}
NEODOT = "5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG"
def iso(s): return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
def _amt(b): return float(b["uiTokenAmount"]["uiAmountString"] or 0)
def _keys(txm): return [k["pubkey"] if isinstance(k, dict) else k for k in txm]

def pool_trades2(meta, keys, mint, skip_owner=None):
    """per pool (token-vault owner): fill = |dquote|/|dbase|. Quote = WSOL/USDC/USDT vault of the same owner, else the owner's native
    lamports (pump.fun bonding curve keeps SOL as lamports) -> curve=True."""
    pre = {b["accountIndex"]: b for b in meta.get("preTokenBalances") or []}; post = {b["accountIndex"]: b for b in meta.get("postTokenBalances") or []}
    out = []
    for i, b in post.items():
        if b["mint"] != mint or b.get("owner") == skip_owner: continue
        db = _amt(b) - (_amt(pre[i]) if i in pre else 0.0)
        if db == 0: continue
        q = None; curve = False
        for j, c in post.items():
            if c.get("owner") == b.get("owner") and c["mint"] in QUOTES:
                dq = _amt(c) - (_amt(pre[j]) if j in pre else 0.0)
                if dq != 0 and (q is None or _amt(c) > q[0]): q = (_amt(c), c["mint"], dq)
        if q is None and keys and b.get("owner") in keys:
            k = keys.index(b["owner"]); dl = (meta["postBalances"][k] - meta["preBalances"][k]) / 1e9
            if dl != 0 and (dl > 0) == (db < 0): q = (meta["postBalances"][k] / 1e9, WSOL, dl); curve = True
        out.append(dict(owner=b.get("owner"), base=_amt(b), dbase=db, quote=q[0] if q else None, qmint=q[1] if q else None,
                        fill=abs(q[2] / db) if q else None, curve=curve))
    return out

def pool_state2(tx, mint, wallet):
    ps = pool_trades2(tx["meta"], _keys(tx["transaction"]["message"]["accountKeys"]), mint, wallet)
    qp = [p for p in ps if p["quote"]]
    if not qp: return None
    best = dict(max(qp, key=lambda p: abs(p["dbase"]))); best["alt"] = [p for p in qp if p["owner"] != best["owner"]]
    return best

def block_trades2(slot, mints):
    p = os.path.join(BW, f"{slot}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        if set(mints) <= set(d["mints"]): return d
    r = rpc("getBlock", [slot, {"encoding": "jsonParsed", "transactionDetails": "accounts", "maxSupportedTransactionVersion": 1, "rewards": False, "commitment": "confirmed"}])
    if r == "FAIL": return None
    d = {"mints": sorted(set(mints)), "skipped": r is None, "res": {}, "bt": (r or {}).get("blockTime")}
    for tx in (r or {}).get("transactions", []):
        m = tx.get("meta") or {}
        if m.get("err"): continue
        hit = {b["mint"] for b in (m.get("postTokenBalances") or []) if b["mint"] in set(mints)}
        for mint in hit:
            for pt in pool_trades2(m, _keys(tx["transaction"]["accountKeys"]), mint):
                if pt["fill"]: d["res"][f'{pt["owner"]}|{mint}'] = [pt["fill"], pt["dbase"]]
    json.dump(d, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    return d

def drift2(ps, mint, slot, mints):
    if not ps or not ps.get("fill"): return None
    out = {}; prev = 1.0
    for lo, hi, tag in ((slot + 1, slot + 5, "2s"), (slot + 6, slot + 12, "5s")):
        got = None
        for s in range(hi, lo - 1, -1):
            d = block_trades2(s, mints)
            if d is None: return None
            v = d["res"].get(f'{ps["owner"]}|{mint}')
            if v: got = v[0] / ps["fill"]; out[tag + "_slot"] = s; break
        if got: prev = got
        out[tag] = prev; out[tag + "_trade"] = got is not None
    return out

def px_usd(s, t): return (abs(s["sol"]) * fs.solpx(t) + abs(s["usdq"])) / abs(s["tokens"]) if s and s["tokens"] else None

def enrich(e, mints, do_drift=True):
    w = e["wallet"]
    if "ps" not in e:
        tx = get_tx(e["entry_sig"])
        if not tx or not tx.get("meta"): e["ps"] = None; return e
        s = parse_swap(tx, w); e["slot"] = tx.get("slot"); e["pre_bal"] = s["pre_bal"] if s else None
        e["ps"] = pool_state2(tx, e["mint"], w); e["leader_px"] = px_usd(s, e["t"]); e["entry_tokens"] = s["tokens"] if s else None
        e["ata"] = next((tx["transaction"]["message"]["accountKeys"][b["accountIndex"]]["pubkey"] for b in tx["meta"].get("postTokenBalances") or []
                         if b.get("owner") == w and b["mint"] == e["mint"]), None)
    if "swaps" not in e and e.get("ata"):
        sigs, before = [], None
        for _ in range(5):
            r = rpc("getSignaturesForAddress", [e["ata"], {"limit": 1000, "until": e["entry_sig"], **({"before": before} if before else {})}])
            if r == "FAIL" or not r: break
            sigs += r; before = r[-1]["signature"]
            if len(r) < 1000: break
        H = e["exit_t"] + 120
        sw = []
        for x in sorted([x for x in sigs if not x.get("err") and (x.get("blockTime") or 0) <= H], key=lambda x: (x.get("blockTime") or 0, x.get("slot") or 0)):
            tx = get_tx(x["signature"]); s = parse_swap(tx, w) if tx else None
            if not s or s["mint"] != e["mint"]: continue
            sw.append(dict(sig=x["signature"], t=s["bt"], slot=s["slot"], tokens=s["tokens"], pre_bal=s["pre_bal"], avg_px=px_usd(s, s["bt"]),
                           pool=pool_state2(tx, e["mint"], w)))
        e["swaps"] = sw
    if do_drift and "dpx" not in e and e.get("ps") and e.get("slot"):
        e["dpx"] = drift2(e["ps"], e["mint"], e["slot"], mints)
    if do_drift and "sell_dpx" not in e and e.get("swaps") is not None:
        fs_ = next((s for s in e["swaps"] if s["tokens"] < 0 and s.get("pool")), None)
        e["sell_dpx"] = drift2(fs_["pool"], e["mint"], fs_["slot"], mints) if fs_ else None
    return e

def rows():
    out = []
    for r in csv.DictReader(open(os.path.join(WIN, "trades.csv"))):
        out.append(dict(wallet=r["wallet"], label=LABEL[r["wallet"][:8]], mint=r["mint"], symbol=r["symbol"], t=iso(r["entry_time"]), exit_t=iso(r["exit_time"]),
                        entry_sig=r["entry_sig"], exit_sig=r["exit_sig"], src="scout", scout={k: r[k] for k in ("pnl_pct_gross", "pnl_pct_net5", "pnl_sol_net5",
                        "size_in_usd", "size_in_sol", "age_at_entry_h", "mcap_at_entry_usd_approx", "entry_via_pumpfun", "n_buys", "n_sells", "hold_min", "context_pool")}))
    return out

def neodot_post(cut):
    """neodot round trips that START after Scout's last data point (post-selection holdout). Built from public RPC signatures."""
    sigs, before = [], None
    for _ in range(4):
        r = rpc("getSignaturesForAddress", [NEODOT, {"limit": 1000, **({"before": before} if before else {})}])
        if r == "FAIL" or not r: break
        sigs += r; before = r[-1]["signature"]
        if (r[-1].get("blockTime") or 0) < cut: break
    sw = []
    for x in sorted([x for x in sigs if not x.get("err") and (x.get("blockTime") or 0) > cut], key=lambda x: (x["blockTime"], x["slot"])):
        tx = get_tx(x["signature"]); s = parse_swap(tx, NEODOT) if tx else None
        if s and abs(s["sol"]) + abs(s["usdq"]) > 0.001: sw.append(dict(sig=x["signature"], t=s["bt"], mint=s["mint"], tokens=s["tokens"], pre_bal=s["pre_bal"]))
    trips, open_ = [], {}
    for s in sw:
        m = s["mint"]
        if s["tokens"] > 0 and m not in open_ and s["pre_bal"] <= 1e-9: open_[m] = dict(buy=s, bought=s["tokens"], sold=0.0)
        elif m in open_:
            o = open_[m]
            if s["tokens"] > 0: o["bought"] += s["tokens"]
            else:
                o["sold"] += -s["tokens"]
                if o["sold"] >= 0.95 * o["bought"]:
                    trips.append(dict(wallet=NEODOT, label="neodot", mint=m, symbol="", t=o["buy"]["t"], exit_t=s["t"], entry_sig=o["buy"]["sig"], exit_sig=s["sig"],
                                      src="post_selection", scout={})); del open_[m]
    return trips, len(sw), list(open_)

def main():
    rs = rows()
    cut = max(r["exit_t"] for r in rs if r["label"] == "neodot")
    pf = os.path.join(WD, "_neodot_post.json")
    if not os.path.exists(pf):
        trips, nsw, still = neodot_post(cut); json.dump(dict(cut=cut, trips=trips, n_swaps=nsw, still_open=still, built=time.time()), open(pf, "w"))
    post = json.load(open(pf)); rs += post["trips"]
    print("trades", len(rs), "post-selection neodot", len(post["trips"]), "swaps", post["n_swaps"], "open", len(post["still_open"]), flush=True)
    mints = sorted({r["mint"] for r in rs})
    # fresh launches first (drift matters most there)
    # scope change 01:16: neodot handed to Lab 2 -> skip; benji first (focus), then bystevenr, onlyzhynx
    rs = [r for r in rs if r["label"] != "neodot"]
    rs.sort(key=lambda r: ({"benji": 0, "_benjitrades": 0, "bystevenr": 1, "onlyzhynx": 2}.get(r["label"], 3), r["t"]))
    # pass 1: entry + leader swaps for every trade (core data); pass 2: drift on a sample of <=12 trades per leader (getBlock is the slow part)
    nd = {}
    for pas in (1, 2):
        for n, r in enumerate(rs):
            p = os.path.join(WD, f'{r["wallet"][:8]}_{r["mint"]}_{r["entry_sig"][:8]}.json')
            e = json.load(open(p)) if os.path.exists(p) else r
            e.update({k: r[k] for k in ("scout", "src", "exit_t", "label")})
            dd = pas == 2 and nd.get(r["label"], 0) < 12
            if pas == 2 and "dpx" in e: nd[r["label"]] = nd.get(r["label"], 0) + 1; continue
            e = enrich(e, mints, do_drift=dd)
            if dd and e.get("dpx"): nd[r["label"]] = nd.get(r["label"], 0) + 1
            json.dump(e, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
            if n % 10 == 0: print(pas, n, len(rs), r["label"], STATS, flush=True)

if __name__ == "__main__":
    main()
