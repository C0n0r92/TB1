#!/usr/bin/env python3
"""data/analysis.json -> wallets.csv, avoid.csv, smart_wallets.json, data/summary.json. Pure local; re-runnable."""
import json, csv, os, sys, statistics as st, collections, time, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE
A = json.load(open(os.path.join(BASE, "data", "analysis.json")))
T, W, SOLUSD = A["tokens"], A["wallets"], A["sol_usd"]
DEAD_MCAP = 10000   # token now below $10k mcap = dumped/rugged
def link(s): return "https://solscan.io/tx/" + s if s else ""
def dead(m): n = T.get(m, {}).get("now") or {}; return (n.get("mcap") or 0) < DEAD_MCAP
def fmt_secs(s):
    if s is None: return ""
    return f"{s}s" if s < 120 else (f"{s/60:.0f}m" if s < 7200 else f"{s/3600:.1f}h")

# token-level templates (same launch recipe across different creators = same operator, likely)
tmpl = collections.defaultdict(list)
for m, t in T.items():
    if not t.get("reached_creation"): continue
    devrows = [x for x in W.get(t["creator"], []) if x["mint"] == m]
    d = devrows[0] if devrows else None
    if d and d["sol_spent"] > 80 and t.get("slot0_supply_pct", 0) > 75: tmpl["full-curve dev buy ~86 SOL then token distribution"].append(m)
    elif t.get("slot0_buyers", 0) >= 10 and t.get("slot0_supply_pct", 0) > 75: tmpl["multi-wallet same-slot bundle (>=10 wallets, >75% supply)"].append(m)
tok_tmpl = {m: k for k, v in tmpl.items() for m in v}

def classify(o, rows):
    flags = set()
    for x in rows:
        if x["is_dev"]: flags.add("dev")
        if x["is_bundle"]: flags.add("bundler")
        if x["is_sniper"]: flags.add("sniper")
    closed = [x for x in rows if x["sold_frac"] >= 0.9 and x["xfer_out_tokens"] < 0.1 * max(x["remaining_tokens"] + 1, 1) and x["n_buys"] > 0]
    closed = [x for x in rows if x["sold_frac"] >= 0.9 and x["xfer_out_tokens"] == 0]
    wins = [x for x in closed if x["sol_received"] > x["sol_spent"]]
    realized = sum(x["sol_received"] - x["sol_spent"] for x in closed)
    holds = [x["hold_secs"] for x in closed if x["hold_secs"] is not None]
    mc = [x["entry_mcap_usd"] for x in rows if x["entry_mcap_usd"]]
    distributed = [x for x in rows if x["is_dev"] and x["xfer_out_tokens"] > 0.5 * max(x["sol_spent"], 1) and x["sold_frac"] < 0.1 and x["xfer_out_tokens"] > 1e8]
    s = {"n_tokens": len({x["mint"] for x in rows}), "closed": len(closed), "wins": len(wins),
         "win_rate": round(len(wins) / len(closed), 2) if closed else None,
         "realized_sol": round(realized, 3) if closed else None,
         "avg_entry_mcap": round(st.mean(mc)) if mc else None,
         "median_hold": int(st.median(holds)) if holds else None,
         "median_rank": int(st.median([x["rank"] for x in rows])), "median_secs": int(st.median([x["secs"] for x in rows])),
         "flags": sorted(flags), "distributor": bool(distributed),
         "tokens": sorted({x["sym"] for x in rows}), "in_dead": sorted({x["sym"] for x in rows if dead(x["mint"])}),
         "templates": sorted({tok_tmpl[x["mint"]] for x in rows if x["mint"] in tok_tmpl})}
    ev = []
    for x in sorted(rows, key=lambda x: x["ts"]):
        ev.append(f'{x["sym"]} buy {link(x["sig"])}')
        if x.get("last_sell_sig"): ev.append(f'{x["sym"]} last sell {link(x["last_sell_sig"])}')
    s["evidence"] = " | ".join(ev[:6])
    # type
    if "dev" in flags:
        s["type"] = "dev (full-curve buy + token distribution)" if distributed else "dev"
    elif "bundler" in flags: s["type"] = "bundler (bought in launch slot)"
    elif s["n_tokens"] >= 2 and s["median_hold"] is not None and s["median_hold"] < 120: s["type"] = "fast bot / scalper (not copyable)"
    elif s["n_tokens"] >= 2 and closed and realized > 0 and (s["win_rate"] or 0) >= 0.5:
        dead_frac = len(s["in_dead"]) / s["n_tokens"]
        if (s["avg_entry_mcap"] or 0) < 20000: s["type"] = "micro-cap scalper (profitable; enters far below radar range)"
        elif dead_frac > 0.5: s["type"] = "early flipper (profitable, but mostly in coins that later dumped)"
        else: s["type"] = "early trader (profitable, repeat)"
    elif s["n_tokens"] >= 2: s["type"] = "repeat early buyer (unprofitable/flat)"
    else: s["type"] = "early buyer (single token)"
    return s

S = {o: classify(o, rows) for o, rows in W.items()}
# clusters: identical buy SOL amount + same slot across >=2 tokens = one operator running several wallets
sig = collections.defaultdict(list)
for o, rows in W.items():
    key = tuple(sorted((x["mint"], x["slot_offset"], round(x["sol_spent"], 3)) for x in rows))
    if len(rows) >= 2: sig[tuple((m, so) for m, so, _ in key)].append(o)
for k, os_ in sig.items():
    if len(os_) >= 3:
        for o in os_: S[o]["cluster"] = f"{len(os_)} wallets bought the same tokens in the same slots"

def confidence(s):
    if s["type"].startswith("dev") or s["type"].startswith("bundler"): return "high" if s["closed"] or s["distributor"] else "medium"
    return "medium" if s["n_tokens"] >= 5 and s["closed"] >= 5 else "low"

def earliness(s): return f'median buyer #{s["median_rank"]}, +{fmt_secs(s["median_secs"])} after launch'

cols = ["address", "type", "evidence", "win_rate", "realized_pnl", "avg_entry_mcap", "typical_hold_time", "earliness_vs_crowd", "fomo_handle", "confidence"]
def row(o, s):
    t = s["type"] + (f'; {s["cluster"]}' if s.get("cluster") else "") + f' [tokens: {",".join(s["tokens"])}]'
    rp = "" if s["realized_sol"] is None else f'{s["realized_sol"]:+.3f} SOL (~${s["realized_sol"]*SOLUSD:+,.0f}) over {s["closed"]} closed'
    return {"address": o, "type": t, "evidence": s["evidence"], "win_rate": "" if s["win_rate"] is None else f'{s["wins"]}/{s["closed"]}',
            "realized_pnl": rp, "avg_entry_mcap": "" if not s["avg_entry_mcap"] else f'${s["avg_entry_mcap"]:,}',
            "typical_hold_time": fmt_secs(s["median_hold"]), "earliness_vs_crowd": earliness(s), "fomo_handle": "", "confidence": confidence(s)}

avoid, keep = [], []
for o, s in S.items():
    bad = s["type"].startswith("dev") or (s["type"].startswith("bundler") and (s["realized_sol"] or 0) > 0) \
          or (s.get("cluster") and (s["realized_sol"] or 0) <= 0)
    (avoid if bad else keep).append(o)
rank = lambda o: (-(S[o]["n_tokens"]), -(S[o]["realized_sol"] or -99))
with open(os.path.join(BASE, "wallets.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, cols); w.writeheader()
    for o in sorted(keep, key=rank): w.writerow(row(o, S[o]))
import datetime as _dt
NOW = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def iso(t): return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
_prev = {}
try:
    for _r in csv.DictReader(open(os.path.join(BASE, "avoid.csv"))):
        if _r.get("date_added"): _prev[_r["address"]] = _r["date_added"]
except Exception: pass
_prevj = {}
try:
    _pj = json.load(open(os.path.join(BASE, "smart_wallets.json")))
    for _sec in ("smart", "avoid"):
        for _a, _v in (_pj.get(_sec) or {}).items():
            if _v.get("date_added"): _prevj[_a] = _v["date_added"]
except Exception: pass
DATE = lambda o: _prev.get(o) or _prevj.get(o) or NOW
def buys(o): return [{"mint": x["mint"], "sym": x["sym"], "ts": iso(x["ts"]), "sig": x["sig"], "sol": round(x["sol"], 4),
                      "slot_offset": x["slot_offset"], "entry_mcap_usd": x.get("entry_mcap_usd")} for x in sorted(W[o], key=lambda x: x["ts"])]
with open(os.path.join(BASE, "avoid.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, ["address", "reason", "date_added", "mints"] + [c for c in cols if c != "address"]); w.writeheader()
    for o in sorted(avoid, key=lambda o: (not S[o]["type"].startswith("dev"), -(S[o]["realized_sol"] or 0))):
        s = S[o]; r = row(o, s)
        why = []
        if s["type"].startswith("dev"): why.append("token creator")
        if s["distributor"]: why.append("bought ~the whole bonding curve in the create tx then sent tokens out to other wallets")
        if s["type"].startswith("bundler"): why.append(f'bought in the launch slot and exited for {s["realized_sol"]:+.2f} SOL')
        if s.get("cluster"): why.append(s["cluster"])
        if s["in_dead"]: why.append("in dumped tokens: " + ",".join(s["in_dead"]))
        if s["templates"]: why.append("launch recipe: " + "; ".join(s["templates"]))
        r["reason"] = "; ".join(why); r["date_added"] = DATE(o); r["mints"] = " ".join(sorted({x["mint"] for x in W[o]})); w.writerow(r)

smart = {}
for o in keep:
    s = S[o]
    if s["type"] == "early trader (profitable, repeat)":
        alive = s["n_tokens"] - len(s["in_dead"])
        wgt = round(min(1.0, 0.15 * alive * (s["win_rate"] or 0)), 2)
        smart[o] = {"address": o, "date_added": DATE(o), "buys": buys(o), "weight": wgt, "type": "early_trader", "confidence": confidence(s), "tokens": s["tokens"],
                    "win_rate": s["win_rate"], "realized_sol": s["realized_sol"], "median_hold_s": s["median_hold"]}
avoid_map = {o: {"address": o, "date_added": DATE(o), "buys": buys(o), "weight": -1.0 if S[o]["type"].startswith("dev") else -0.5, "type": S[o]["type"].split(" ")[0], "confidence": confidence(S[o]),
                 "tokens": S[o]["tokens"]} for o in avoid}
out = {"generated": A["generated"], "schema": 2, "schema_notes": "smart/avoid keyed by address; each entry has address, date_added (ISO UTC, first time Scout listed it) and buys[] with mint + ts (ISO UTC) + sig. For back-tests ignore entries with date_added after the test time.",
       "rug_flag": "python3 /workspace/onchain-intel/rugcheck_creator.py <mint> -> JSON verdict block|caution|ok|unknown; lists: known_ruggers.json, known_funders.csv", "source": "/workspace/onchain-intel (read-only on-chain analysis)",
       "how_to_use": "For a candidate coin, collect buyer addresses (e.g. GeckoTerminal /pools/<pool>/trades tx_from_address, kind=buy). "
                     "boost = sum(weight of distinct smart wallets), capped; any avoid wallet with weight -1 (dev) or >=2 avoid wallets => skip/penalise.",
       "launch_red_flags": {"full_curve_dev_buy_sol_gt": 80, "slot0_supply_pct_gt": 75},
       "smart": smart, "avoid": avoid_map,
       "templates": {k: [T[m]["sym"] + ":" + m for m in v] for k, v in tmpl.items()}}
json.dump(out, open(os.path.join(BASE, "smart_wallets.json"), "w"), indent=1)
json.dump({"S": S, "tmpl": tmpl}, open(os.path.join(BASE, "data", "summary.json"), "w"), indent=1)
print("keep", len(keep), "avoid", len(avoid), "smart", len(smart))
for k, v in tmpl.items(): print(k, [T[m]["sym"] for m in v])
