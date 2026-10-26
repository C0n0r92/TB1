#!/usr/bin/env python3
"""Cross-token early-buyer analysis -> wallets.csv, avoid.csv, smart_wallets.json, data/pnl.json.
Re-runnable: uses cached txs (data/txcache) and data/early/*.json. Read-only public data only."""
import json, glob, os, re, sys, collections, statistics as st, time, urllib.request, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE, tx, deltas
from wallet_token_pnl import pnl
MIN_BUY_SOL = 0.05          # ignore dust/"ping" buys
SNIPE_SLOTS = 2             # bought within <=2 slots (~1 s) of creation
MAX_PNL_WALLETS = int(os.environ.get("MAX_PNL_WALLETS", "300"))
H = {"User-Agent": "onchain-intel/1.0", "Accept": "application/json"}
def get(u):
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20).read())
    except Exception: return None
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def solscan(s): return "https://solscan.io/tx/" + s

labels = {}
for l in open(os.path.join(BASE, "data", "tokens.txt")):
    p = l.split()
    if p: labels[p[0]] = (p[1], p[2] if len(p) > 2 else "")
early = {}
for f in glob.glob(os.path.join(BASE, "data", "early", "*.json")):
    r = json.load(open(f)); early[r["mint"]] = r
# SOL price + token market data (DexScreener)
solp = get("https://api.dexscreener.com/latest/dex/pairs/solana/Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE")
SOLUSD = float(solp["pairs"][0]["priceUsd"]) if solp and solp.get("pairs") else None
mk = {}
ms = list(early)
for i in range(0, len(ms), 30):
    for p in get("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ms[i:i+30])) or []:
        a = p["baseToken"]["address"]; liq = (p.get("liquidity") or {}).get("usd") or 0
        if a not in mk or liq > mk[a]["liq"]:
            mk[a] = {"priceUsd": float(p.get("priceUsd") or 0), "mcap": p.get("marketCap") or p.get("fdv"), "liq": liq}
supply = {}
for m in ms:
    rc = os.path.join(BASE, "data", "rugcheck", m + ".json")
    if os.path.exists(rc):
        t = json.load(open(rc)).get("token") or {}
        if t.get("supply"): supply[m] = t["supply"] / 10 ** t.get("decimals", 6)
    supply.setdefault(m, 1e9)

# ---- per token: dev, bundle co-signers, early buyers ----
appear = collections.defaultdict(list)   # owner -> list of early-buy records
token_info = {}
for m, r in early.items():
    sym = labels.get(m, ("?", ""))[0]
    ct0 = tx(r["create_sig"]) if r.get("create_sig") else None
    lg = " ".join((ct0 or {}).get("meta", {}).get("logMessages") or [])
    reached = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P" in lg and bool(re.search(r"Instruction: Create(V2)?\b", lg))
    rcf = os.path.join(BASE, "data", "rugcheck", m + ".json")
    rc_creator = json.load(open(rcf)).get("creator") if os.path.exists(rcf) else None
    if not reached:   # history too long for free paging: we never saw the launch, skip earliness
        token_info[m] = {"sym": sym, "label": labels.get(m, ("", ""))[1], "reached_creation": False, "total_sigs": r["total_sigs"], "rugcheck_creator": rc_creator}
        continue
    ct = tx(r["create_sig"]) if r.get("create_sig") else None
    bundle = set()
    if ct and r.get("creator"):
        tok, sol, wsol, signers, acct = deltas(ct, m)
        bundle = {o for o, d in tok.items() if d > 0 and o in signers and o != r["creator"]}
    seen = {}; rank = 0
    for e in r["events"]:
        if e["side"] != "buy" or e["owner"] in seen: continue
        rank += 1; seen[e["owner"]] = rank
        if -e["sol"] < MIN_BUY_SOL and e["owner"] != r.get("creator"): continue
        px = -e["sol"] / e["tokens"] if e["tokens"] else 0
        appear[e["owner"]].append({"mint": m, "sym": sym, "rank": rank, "secs": e["secs"], "slot_offset": e["slot_offset"],
            "sol": -e["sol"], "sig": e["sig"], "ts": e["ts"], "token_account": e["token_account"],
            "entry_mcap_usd": px * supply[m] * SOLUSD if SOLUSD else None,
            "is_dev": e["owner"] == r.get("creator"), "is_bundle": (e["owner"] in bundle or e["slot_offset"] == 0) and e["owner"] != r.get("creator"),
            "in_create_tx": e["owner"] in bundle, "is_sniper": 0 < e["slot_offset"] <= SNIPE_SLOTS})
    s0 = [e for e in r["events"] if e["side"] == "buy" and e["slot_offset"] == 0]
    s0_tok = sum(e["tokens"] for e in s0)
    token_info[m] = {"sym": sym, "label": labels.get(m, ("", ""))[1], "reached_creation": True,
                     "slot0_buyers": len({e["owner"] for e in s0}), "slot0_supply_pct": round(100 * s0_tok / supply[m], 1),
                     "slot0_sol": round(-sum(e["sol"] for e in s0), 2), "slot0_txs": sorted({e["sig"] for e in s0}), "creator": r.get("creator"), "create_sig": r.get("create_sig"),
                     "create_ts": r.get("create_ts"), "bundle_wallets": sorted(bundle), "total_sigs": r["total_sigs"],
                     "early_window_secs": r["events"][-1]["secs"] if r["events"] else None, "now": mk.get(m)}

# ---- choose wallets for PnL: multi-token early buyers + devs/bundlers + biggest early buyers per token ----
multi = [o for o, v in appear.items() if len({x["mint"] for x in v}) >= 2]
special = [o for o, v in appear.items() if any(x["is_dev"] or x["is_bundle"] for x in v)]
big = []
for m in early:
    if not token_info.get(m, {}).get("reached_creation"): continue
    rows = sorted([(x["sol"], o) for o, v in appear.items() for x in v if x["mint"] == m], reverse=True)[:5]
    big += [o for _, o in rows]
cand = list(dict.fromkeys(multi + special + big))[:MAX_PNL_WALLETS]
pf = os.path.join(BASE, "data", "pnl.json")
P = json.load(open(pf)) if os.path.exists(pf) else {}
for i, o in enumerate(cand):
    for x in appear[o]:
        k = o + ":" + x["mint"]
        if k in P or not x["token_account"]: continue
        try: P[k] = pnl(o, x["mint"], x["token_account"])
        except Exception as ex: P[k] = {"error": str(ex)}
    if i % 10 == 0:
        json.dump(P, open(pf, "w")); print("pnl", i, len(cand), flush=True)
json.dump(P, open(pf, "w"))

# ---- per wallet summary ----
def summarize(o):
    res = []
    for x in appear[o]:
        p = P.get(o + ":" + x["mint"]); 
        if not p or "error" in p: continue
        now = (mk.get(x["mint"]) or {}).get("priceUsd") or 0
        rem = max(p["remaining_est"], 0)
        unreal_usd = rem * now
        real_sol = p["sol_received"] - p["sol_spent"] * (p["tokens_sold"] / p["tokens_bought"] if p["tokens_bought"] else 0)
        sells = [l for l in p["legs"] if l["kind"] == "sell"]; buys = [l for l in p["legs"] if l["kind"] == "buy"]
        xout = [l for l in p["legs"] if l["kind"] == "xfer_out"]
        sold_frac = p["tokens_sold"] / p["tokens_bought"] if p["tokens_bought"] else 0
        hold = None
        if buys and (sells or xout):
            ends = sells + xout
            hold = max(l["ts"] for l in ends) - buys[0]["ts"] if sold_frac + (p["tokens_xfer_out"] / p["tokens_bought"] if p["tokens_bought"] else 0) >= 0.9 else None
        first_sell = min((l["ts"] for l in sells), default=None)
        res.append({**x, "sol_spent": round(p["sol_spent"], 4), "sol_received": round(p["sol_received"], 4),
                    "net_sol_cash": round(p["sol_received"] - p["sol_spent"], 4), "realized_sol_on_sold": round(real_sol, 4),
                    "sold_frac": round(sold_frac, 3), "xfer_out_tokens": p["tokens_xfer_out"], "remaining_tokens": rem,
                    "unrealized_usd": round(unreal_usd, 2), "hold_secs": hold,
                    "secs_to_first_sell": (first_sell - buys[0]["ts"]) if first_sell and buys else None,
                    "n_buys": len(buys), "n_sells": len(sells), "truncated": p["truncated"],
                    "last_sell_sig": sells[-1]["sig"] if sells else None, "first_sell_sig": sells[0]["sig"] if sells else None})
    return res

wallets = {}
for o in cand:
    s = summarize(o)
    if s: wallets[o] = s
json.dump({"generated": iso(time.time()), "sol_usd": SOLUSD, "tokens": token_info, "wallets": wallets},
          open(os.path.join(BASE, "data", "analysis.json"), "w"), indent=1)
print("wallets analysed", len(wallets), "SOLUSD", SOLUSD)
