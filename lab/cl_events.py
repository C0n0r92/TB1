#!/usr/bin/env python3
"""Confluence (CL_) phase 1, PAPER ONLY. Builds smart-wallet buy-cluster events from teammates' files (read-only).
Wallet sets and their lookahead status:
  LEAD   : copy leaders + other mapped traders in onchain-intel/trader_swaps.csv. Identity chosen from the fomo leaderboard
           (PnL over the same weeks) -> LOOKAHEAD (selection overlaps the test window).
  EB_PIT : Scout's early_buyer wallets (first-20 buyers of 100x runners). Time-split: a wallet only counts from
           (its runner's peak_at hour + 1h) onward, and runner mints themselves are excluded -> point-in-time eligibility
           (residual: Scout's 'active in last 30d' / bot / rugger filters were applied at 2026-10-23 22:01Z).
  EB_ALL : same wallets, all buys (Scout's cluster_buys.jsonl definition) -> LOOKAHEAD.
  SMART4 : smart_wallets.json 'smart' (radar_early_trader), every buy precedes date_added -> LOOKAHEAD.
Writes data/cl/events.json"""
import json, csv, collections, datetime as dt, os
OI = "/workspace/onchain-intel"; LAB = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(LAB, "data", "cl")
P = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def load_buys():
    sw = json.load(open(f"{OI}/smart_wallets.json")); R = {r["mint"]: r for r in json.load(open(f"{OI}/data/runners_100x.json"))}
    sets = collections.defaultdict(list); meta = {}
    for r in csv.DictReader(open(f"{OI}/trader_swaps.csv")):
        if r["side"] == "buy":
            sets["LEAD"].append(dict(t=P(r["timestamp"]), w=r["trader"], mint=r["mint"], usd=float(r["usd_size"] or 0), mcap=float(r["mcap_at_fill"] or 0)))
    elig = {}
    for a, v in sw["early_buyer"].items():
        ts = [P(R[e["mint"]]["peak_at"]) + 3600 for e in v.get("early_in", []) if e["mint"] in R]
        elig[a] = min(ts) if ts else None
        for b in v.get("buys", []):
            row = dict(t=P(b["ts"]), w=a, mint=b["mint"], sol=-(b.get("sol") or 0))
            if b["mint"] in R: continue                       # seed runners: never a test trade
            sets["EB_ALL"].append(row)
            if elig[a] is not None and row["t"] >= elig[a]: sets["EB_PIT"].append(row)
    for a, v in sw["smart"].items():
        for b in v.get("buys", []):
            sets["SMART4"].append(dict(t=P(b["ts"]), w=a, mint=b["mint"], sol=b.get("sol"), mcap=b.get("entry_mcap_usd")))
    meta["eligible_from"] = elig; meta["runner_mints"] = sorted(R)
    return sets, meta

def clusters(B, W, N):
    """first buy per wallet per mint; event = first time N distinct wallets bought within W minutes (one event per mint)."""
    by = collections.defaultdict(dict)
    for b in sorted(B, key=lambda b: b["t"]): by[b["mint"]].setdefault(b["w"], b)
    out = []
    for m, first in by.items():
        f = sorted(first.values(), key=lambda b: b["t"])
        for i in range(len(f) - N + 1):
            if f[i + N - 1]["t"] - f[i]["t"] <= W * 60:
                out.append(dict(mint=m, t=f[i + N - 1]["t"], t_first=f[i]["t"], wallets=[x["w"] for x in f[i:i + N]],
                                n_total=len(f))); break
    return out

LOOK = {"LEAD": "LOOKAHEAD", "EB_PIT": "PIT", "EB_ALL": "LOOKAHEAD", "SMART4": "LOOKAHEAD"}
if __name__ == "__main__":
    sets, meta = load_buys(); ev = {}
    for s, B in sets.items():
        for N in (2, 3):
            for W in (10, 30, 60):
                ev[f"{s}_n{N}_w{W}"] = dict(set=s, N=N, W=W, lookahead=LOOK[s], events=clusters(B, W, N))
    singles = {s: [dict(mint=b["mint"], t=b["t"], wallets=[b["w"]]) for b in sorted(B, key=lambda b: b["t"])] for s, B in sets.items()}
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(generated=dt.datetime.utcnow().isoformat() + "Z", events=ev, singles=singles, meta=meta), open(f"{OUT}/events.json", "w"))
    for k, v in ev.items(): print(k, v["lookahead"], len(v["events"]))
    print({s: len(v) for s, v in singles.items()})
