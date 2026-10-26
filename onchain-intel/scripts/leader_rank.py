#!/usr/bin/env python3
"""Job 3: copyfomo leader re-rank (weekly, e.g. Sunday). Read-only. Recommendations only.
Candidates: data/trader_wallets.json (evidenced) + /workspace/trader-analysis/wallets.json (unverified provenance)
            + handles in /workspace/copyfomo/leaderboard-*.md (newest) that map to a wallet in those files (or list a Solana address).
Per wallet (Helius enhanced SWAP history, 30 d; account age + first funder via getTransactionsForAddress asc):
  swaps -> trader_swaps.csv (trader,wallet,timestamp,mint,side,sol_size,usd_size,mcap_at_fill,signature)
  rounds (buy..>=95% sold) ; copy-filter = first round per mint AND entry mcap >= $100k ; copy sim = $50 per such round
  win rate, weekly PnL stability, worst drawdown of the $50-copy equity curve, rug rate (now < $10k mcap / rugcheck verdict),
  entry token age + mcap, insider signs (entries < 60 s after pair creation, flips < 60 s, funder overlap with known ruggers).
Output: leader-rank.md, data/leader_rank.json. Env: LR_DAYS=30 LR_MAXPAGES=10 LR_RUGCHECK_MAX=15 (per trader)."""
import os, sys, json, time, csv, re, glob, statistics as st, subprocess, requests, calendar
sys.path.insert(0, os.path.dirname(__file__))
from sol import BASE, rpc, _helius_key
import trader_trades as TT
DAYS = int(os.environ.get("LR_DAYS", "30")); TT.DAYS = DAYS; TT.MAXP = int(os.environ.get("LR_MAXPAGES", "10"))
RCMAX = int(os.environ.get("LR_RUGCHECK_MAX", "15")); COPY_USD = 50; MIN_MCAP = 100000; DUMP = 10000
NOW = time.time(); iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
USD, SOL = TT.USD, TT.SOL; LOG = os.path.join(BASE, "data", "rpc_calls.log")
RELAYER, FOMOFEE = "AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51", "R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX"

def jload(p, d):
    try: return json.load(open(p))
    except Exception: return d

def candidates():
    C = {}
    for n, v in jload(os.path.join(BASE, "data", "trader_wallets.json"), {}).items():
        if v.get("evidence") and v.get("solana"): C[n] = {"wallet": v["solana"], "provenance": "data/trader_wallets.json: " + v["evidence"][:300], "current_leader": True}
    for n, ws in jload("/workspace/trader-analysis/wallets.json", {}).items():
        sw = [w for w in ws if not w.startswith("0x")]
        if sw and n not in C: C[n] = {"wallet": sw[0], "provenance": "trader-analysis/wallets.json (source not recorded; unverified)", "current_leader": False}
    MP = jload(os.path.join(BASE, "data", "leader_mappings.json"), {})
    for n, v in MP.items():
        if n.startswith("_note") or not isinstance(v, dict): continue
        C[n] = {"wallet": v["wallet"], "provenance": f"[{v['confidence']}] " + v["evidence"], "current_leader": n in ("ExactTallTakin", "_benjitrades"), "confidence": v["confidence"]}
    lb = sorted(glob.glob("/workspace/copyfomo/leaderboard-*.md"))
    lbinfo = {"file": lb[-1] if lb else None, "handles": []}
    if lb:
        txt = open(lb[-1]).read()
        lbh = re.findall(r"^\|\s*\d+\s*\|\s*([A-Za-z0-9_]+)\s*\|", txt, re.M)
        lbinfo["all_handles"] = list(dict.fromkeys(lbh)); lbinfo["handles"] = sorted(set(lbh) & set(C)); lbinfo["no_wallet"] = [h for h in lbinfo["all_handles"] if h not in C]
        for line in txt.splitlines():   # explicit "handle ... <solana address>" lines
            a = re.findall(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b", line); h = re.findall(r"@([A-Za-z0-9_]{3,20})", line)
            if a and h and h[0] not in C: C[h[0]] = {"wallet": a[0], "provenance": f"{lb[-1]} (Copycat leaderboard line; unverified)", "current_leader": False}
        for n in lbinfo["handles"]: C[n]["on_leaderboard"] = True
    return C, lbinfo

def first_txs(addr):
    fn = os.path.join(BASE, "data", "leader_first.json"); c = jload(fn, {})
    if addr in c: return c[addr]
    cfg = {"transactionDetails": "full", "sortOrder": "asc", "limit": 5, "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    r = requests.post("https://mainnet.helius-rpc.com/?api-key=" + _helius_key(), json={"jsonrpc": "2.0", "id": 1, "method": "getTransactionsForAddress", "params": [addr, cfg]}, timeout=60).json()
    open(LOG, "a").write(f"{int(time.time())} helius-gtfa 10\n")
    out = {"first_ts": None, "funder": None, "fund_sol": None, "fund_sig": None}
    for t in (r.get("result") or {}).get("data") or []:
        out["first_ts"] = out["first_ts"] or t.get("blockTime")
        keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]; m = t["meta"]
        d = {k: (m["postBalances"][i] - m["preBalances"][i]) / 1e9 for i, k in enumerate(keys)}
        if d.get(addr, 0) > 0.01 and not out["funder"]:
            p = min((k for k in keys if k != addr), key=lambda k: d.get(k, 0))
            if d.get(p, 0) < 0: out.update(funder=p, fund_sol=round(d[addr], 4), fund_sig=t["transaction"]["signatures"][0])
    c[addr] = out; json.dump(c, open(fn, "w")); return out

def supply(mints):
    fn = os.path.join(BASE, "data", "supply.json"); c = jload(fn, {})
    for m in mints:
        if m in c: continue
        if m.endswith("pump"): c[m] = 1e9; continue    # pump.fun fixed 1B supply
        r = rpc("getTokenSupply", [m]) or {}; v = (r.get("value") or {}).get("uiAmount")
        if v: c[m] = v
    json.dump(c, open(fn, "w")); return c

def dex(mints):
    fn = os.path.join(BASE, "data", "dex_mints.json"); c = jload(fn, {})
    todo = [m for m in mints if m not in c or NOW - c[m].get("at", 0) > 12 * 3600]
    for i in range(0, len(todo), 30):
        ch = todo[i:i + 30]
        try: P = requests.get("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(ch), timeout=30).json()
        except Exception: P = []
        for m in ch: c[m] = {"at": NOW, "listed": False}
        for q in P or []:
            m = q["baseToken"]["address"]
            if m not in c: continue
            e = c[m]; e["listed"] = True
            e["mcap"] = max(e.get("mcap", 0), float(q.get("marketCap") or q.get("fdv") or 0))
            if q.get("priceUsd") and float(q.get("liquidity", {}).get("usd") or 0) >= e.get("liq", -1): e["price"] = float(q["priceUsd"]); e["liq"] = float(q.get("liquidity", {}).get("usd") or 0)
            if q.get("pairCreatedAt"): e["created"] = min(e.get("created", 9e18), q["pairCreatedAt"] / 1000)
        time.sleep(0.25)
    json.dump(c, open(fn, "w")); return c

def rugcheck(m):
    fn = os.path.join(BASE, "data", "leader_rugcheck.json"); c = jload(fn, {})
    if m in c: return c[m]
    try: v = json.loads(subprocess.run(["python3", os.path.join(BASE, "rugcheck_creator.py"), m], capture_output=True, text=True, timeout=120).stdout)
    except Exception: v = {"verdict": "unknown"}
    c[m] = {"verdict": v.get("verdict"), "reasons": v.get("reasons", [])[:4]}; json.dump(c, open(fn, "w")); return c[m]

WATCH = {k: v for k, v in jload(os.path.join(BASE, "data", "leader_watchlist.json"), {}).items() if not k.startswith("_") and isinstance(v, dict)}

def fetch_long(addr, name, days, maxp):
    """Watch-list history: normal incremental fetch, then backfill older pages (TT.fetch stops at the newest cached tx)."""
    TT.fetch(addr, name)
    fn = os.path.join(BASE, "data", f"enh_{name}_all.json"); have = jload(fn, [])
    cutoff = NOW - days * 86400; sigs = {x["signature"] for x in have}
    if not have or min(x["timestamp"] for x in have) <= cutoff: return [x for x in have if x["timestamp"] >= cutoff]
    before = min(have, key=lambda x: x["timestamp"])["signature"]; got = []
    maxp = min(maxp, int(os.environ.get("LR_WATCH_MAXPAGES", maxp)))
    for _ in range(maxp):
        if not TT.budget_take(100, "enhanced"): print(f"budget: stopped watch-list backfill for {name}", flush=True); break
        r = requests.get(f"https://api.helius.xyz/v0/addresses/{addr}/transactions", params={"api-key": _helius_key(), "type": "SWAP", "limit": 100, "before": before}, timeout=60)
        open(LOG, "a").write(f"{int(time.time())} helius-enhanced 1\n"); time.sleep(0.3)
        d = r.json() if r.ok else []
        if isinstance(d, dict):
            msg = str(d.get("error", "")); before = msg.split("before` parameter set to ")[-1].split(".")[0].strip() if "before" in msg else None
            if not before: break
            continue
        if not d: break
        got += [x for x in d if x["signature"] not in sigs]; before = d[-1]["signature"]
        if d[-1]["timestamp"] < cutoff: break
    allx = sorted(have + got, key=lambda x: x["timestamp"]); json.dump(allx, open(fn, "w"))
    return [x for x in allx if x["timestamp"] >= cutoff]

def analyse(name, w, px):
    wl = WATCH.get(name)
    txs = fetch_long(w, name, int(wl.get("days", 90)), int(wl.get("max_pages", 25))) if wl else TT.fetch(w, name)
    sw = []
    relayed = 0
    for x in txs:
        if x.get("feePayer") == RELAYER or any(n.get("toUserAccount") == FOMOFEE for n in x.get("nativeTransfers") or []) or any(t.get("toUserAccount") == FOMOFEE for t in x.get("tokenTransfers") or []): relayed += 1
        dl = TT.legs(x, w); q = {m: a for m, a in dl.items() if m in USD or m == SOL}
        toks = [(m, a) for m, a in dl.items() if m not in USD and m != SOL]
        if len(toks) != 1 or not q: continue
        m, a = toks[0]; s = px.get(time.strftime("%Y-%m-%d", time.gmtime(x["timestamp"]))) or px.get(max(px))
        usd = sum(v if k in USD else v * s for k, v in q.items())
        if (a > 0) == (usd > 0) or abs(usd) < 0.5: continue
        sw.append({"ts": x["timestamp"], "mint": m, "side": "buy" if a > 0 else "sell", "tokens": abs(a), "usd": abs(usd), "sol": abs(usd) / s, "sig": x["signature"]})
    sup = supply({r["mint"] for r in sw}); D = dex({r["mint"] for r in sw})
    for r in sw: r["mcap"] = r["usd"] / r["tokens"] * sup[r["mint"]] if sup.get(r["mint"]) else None
    # rounds
    pos, rounds, seen = {}, [], set()
    for r in sorted(sw, key=lambda r: r["ts"]):
        p = pos.get(r["mint"])
        if r["side"] == "buy":
            if not p: p = pos[r["mint"]] = {"mint": r["mint"], "buy_at": r["ts"], "entry_mcap": r["mcap"], "bought": 0, "sold": 0, "cost": 0, "proc": 0, "first": r["mint"] not in seen, "sig": r["sig"]}; seen.add(r["mint"])
            p["bought"] += r["tokens"]; p["cost"] += r["usd"]
        elif p:
            p["sold"] += r["tokens"]; p["proc"] += r["usd"]
            if p["sold"] >= 0.95 * p["bought"]: p["sell_at"] = r["ts"]; rounds.append(pos.pop(r["mint"]))
    for p in pos.values():   # open: mark to market at DexScreener price (0 if unlisted/dead)
        pr = D.get(p["mint"], {}).get("price") or 0
        p["sell_at"] = None; p["proc"] += max(0, p["bought"] - p["sold"]) * pr; rounds.append(p)
    for p in rounds:
        p["pnl_pct"] = (p["proc"] / p["cost"] - 1) * 100 if p["cost"] else 0
        d = D.get(p["mint"], {}); p["now_mcap"] = d.get("mcap") if d.get("listed") else 0
        p["age_s"] = p["buy_at"] - d["created"] if d.get("created") else None
        p["hold_s"] = (p["sell_at"] - p["buy_at"]) if p["sell_at"] else None
    passing = sorted([p for p in rounds if p["first"] and (p["entry_mcap"] or 0) >= MIN_MCAP], key=lambda p: p["buy_at"])
    # rugcheck on passing pump mints (cap)
    rc = {}
    for p in passing[-RCMAX:]:
        if p["mint"].endswith("pump"): rc[p["mint"]] = rugcheck(p["mint"])
    closed = [p for p in passing if p["sell_at"]]
    eq, peak, dd, curve = 0, 0, 0, []
    for p in sorted(passing, key=lambda p: p["sell_at"] or NOW):
        eq += COPY_USD * p["pnl_pct"] / 100; peak = max(peak, eq); dd = max(dd, peak - eq); curve.append(round(eq, 2))
    wk = {}
    for p in passing: wk.setdefault(time.strftime("%G-W%V", time.gmtime(p["buy_at"])), []).append(COPY_USD * p["pnl_pct"] / 100)
    wks = {k: round(sum(v), 2) for k, v in sorted(wk.items())}
    ft = first_txs(w); kr = jload(os.path.join(BASE, "known_ruggers.json"), {})
    bad = set(kr.get("wallets", {})) | set(kr.get("funders", {}))
    try: bad |= {r["address"] for r in csv.DictReader(open(os.path.join(BASE, "known_funders.csv")))}
    except Exception: pass
    allc = [p for p in rounds if p["sell_at"]]
    res = {"trader": name, "wallet": w, "n_swaps": len(sw), "relayed_fomo_swaps": relayed, "n_rounds": len(rounds), "n_pass": len(passing), "n_pass_closed": len(closed),
           "win_rate": round(sum(p["pnl_pct"] > 0 for p in closed) / len(closed), 2) if closed else None,
           "copy_pnl_usd": round(eq, 2), "max_dd_usd": round(dd, 2), "weekly_usd": wks,
           "pos_weeks": f"{sum(v > 0 for v in wks.values())}/{len(wks)}", "pos_week_frac": round(sum(v > 0 for v in wks.values()) / len(wks), 2) if wks else 0,
           "weekly_sd": round(st.pstdev(wks.values()), 2) if len(wks) > 1 else None,
           "median_pnl_pct": round(st.median([p["pnl_pct"] for p in passing]), 1) if passing else None,
           "dumped_rate": round(sum((p["now_mcap"] or 0) < DUMP for p in passing) / len(passing), 2) if passing else None,
           "rugcheck_block_or_caution": f"{sum(v['verdict'] in ('block', 'caution') for v in rc.values())}/{len(rc)}",
           "median_entry_mcap": round(st.median([p["entry_mcap"] for p in passing])) if passing else None,
           "median_entry_age_h": round(st.median([p["age_s"] for p in passing if p["age_s"] is not None]) / 3600, 1) if [p for p in passing if p["age_s"] is not None] else None,
           "entries_lt_60s_after_pair": sum(1 for p in rounds if p["age_s"] is not None and p["age_s"] < 60),
           "flips_lt_60s": sum(1 for p in allc if p["hold_s"] is not None and p["hold_s"] < 60), "n_closed_all": len(allc),
           "median_hold_min": round(st.median([p["hold_s"] for p in allc]) / 60, 1) if allc else None,
           "first_tx": iso(ft["first_ts"]) if ft["first_ts"] else None, "account_age_d": round((NOW - ft["first_ts"]) / 86400) if ft["first_ts"] else None,
           "funder": ft["funder"], "fund_sol": ft["fund_sol"], "fund_sig": ft["fund_sig"], "funder_in_rugger_lists": bool(ft["funder"] and ft["funder"] in bad),
           "all_rounds_copy_pnl_usd": round(sum(COPY_USD * p["pnl_pct"] / 100 for p in rounds), 2), "all_rounds": len(rounds),
           "worst_passing": [{"mint": p["mint"], "pnl_pct": round(p["pnl_pct"], 1), "buy_at": iso(p["buy_at"]), "sig": p["sig"]} for p in sorted(passing, key=lambda p: p["pnl_pct"])[:3]]}
    cut = []
    if res["n_pass"] < 30: cut.append(f"only {res['n_pass']} copyable trades (<30)")
    if res["account_age_d"] is not None and res["account_age_d"] < 28: cut.append(f"account {res['account_age_d']} d old")
    if res["entries_lt_60s_after_pair"] >= 5: cut.append(f"insider-like: {res['entries_lt_60s_after_pair']} entries <60 s after pair creation")
    if res["flips_lt_60s"] >= 0.3 * max(1, len(allc)): cut.append(f"fast flips: {res['flips_lt_60s']}/{len(allc)} closed rounds held <60 s (copiers can't match)")
    if res["funder_in_rugger_lists"]: cut.append("funder in known rugger lists")
    if res["n_swaps"] == 0: cut.append("no Solana swaps found in window")
    res["cut"] = cut
    return res, sw

def main():
    C, lb = candidates(); px = TT.solusd(); out, rows = [], []
    for n, v in C.items():
        print("analysing", n, v["wallet"], flush=True)
        try: r, sw = analyse(n, v["wallet"], px)
        except Exception as e: print("  fail", e); continue
        r.update(watch=bool(WATCH.get(n)), window_days=int(WATCH[n].get("days", 90)) if WATCH.get(n) else DAYS)
        r.update(confidence=v.get("confidence", "low"), provenance=v["provenance"], current_leader=v.get("current_leader"), on_leaderboard=v.get("on_leaderboard", False)); out.append(r)
        rows += [[n, v["wallet"], iso(s["ts"]), s["mint"], s["side"], round(s["sol"], 4), round(s["usd"], 2), round(s["mcap"]) if s["mcap"] else "", s["sig"]] for s in sorted(sw, key=lambda s: s["ts"])]
        print("  swaps", r["n_swaps"], "pass", r["n_pass"], "win", r["win_rate"], "copy$", r["copy_pnl_usd"], "dd", r["max_dd_usd"], "cut", r["cut"], flush=True)
    with open(os.path.join(BASE, "trader_swaps.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["trader", "wallet", "timestamp", "mint", "side", "sol_size", "usd_size", "mcap_at_fill", "signature"]); w.writerows(rows)
    # rank: eligible first; then positive-week fraction, then win rate, then smaller drawdown. Peak PnL not used.
    out.sort(key=lambda r: (bool(r["cut"]), r["n_pass"] < 30, -(r["pos_week_frac"] or 0), -(r["win_rate"] or 0), r["max_dd_usd"]))
    json.dump({"generated": iso(NOW), "leaderboard": lb, "traders": out}, open(os.path.join(BASE, "data", "leader_rank.json"), "w"), indent=1)
    L = [f"# Copyfomo leader re-rank ({iso(NOW)}), recommendations only", "",
         f"Window: last {DAYS} d of Solana swaps (Helius enhanced SWAP history). The copy filter is the first round per mint with entry mcap ≥ ${MIN_MCAP:,}. Each copy is simulated at ${COPY_USD}. Ranked by: not cut, then share of positive weeks, then win rate, then smaller worst drawdown. Peak PnL is not used.",
         f"Leaderboard file: {lb['file'] or 'not present at run time'}; handles matched to wallets: {', '.join(lb['handles']) or 'none'}.",
         f"Leaderboard handles with **no wallet found** (not guessed): {', '.join(lb.get('no_wallet', [])) or '-'}.",
         "Caveats: wallet↔handle mappings are not independently verified (see provenance); EVM (Base/BSC) trades not covered; open rounds marked at DexScreener price now; mcap_at_fill = fill price × supply (pump.fun = 1B).", "",
         "| # | trader | mapping conf. | wallet | copyable trades (closed) | win rate | positive weeks | weekly $ (sd) | worst DD $ | copy PnL $ | median entry mcap | median entry age h | dumped <$10k | rugcheck block/caution | <60s entries / flips | acct age d | cut |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(out, 1):
        L.append(f"| {i} | {r['trader']}{' (current)' if r['current_leader'] else ''} | {r.get('confidence')} | `{r['wallet']}` | {r['n_pass']} ({r['n_pass_closed']}) | {r['win_rate']} | {r['pos_weeks']} | {r['weekly_usd']} (sd {r['weekly_sd']}) | {r['max_dd_usd']} | {r['copy_pnl_usd']} | {r['median_entry_mcap']} | {r['median_entry_age_h']} | {r['dumped_rate']} | {r['rugcheck_block_or_caution']} | {r['entries_lt_60s_after_pair']} / {r['flips_lt_60s']} of {r['n_closed_all']} | {r['account_age_d']} | {'; '.join(r['cut']) or '-'} |")
    ok = [r["trader"] for r in out if not r["cut"]]
    L += ["", "## Recommendation (auto)", f"- Traders passing every filter: {', '.join(ok) or 'none'}.",
          "- Treat cut traders as watch or drop only. Mappings below medium confidence are not evidence of identity, so verify them before acting.",
          "- Insider-like = several first entries less than 60 s after pair creation (launch sniping). Fast flips = round trips held under 60 s; fomo copiers cannot match these."]
    L += ["", "## Watch list (data/leader_watchlist.json)",
          "Watched handles get a longer SWAP history than the default window; their row and evidence use that window, so their counts are not directly comparable with the others. Watch is a recommendation only.", ""]
    for n, v in WATCH.items():
        r = next((x for x in out if x["trader"] == n), None)
        L.append(f"- {n}: {v.get('days', 90)} d / up to {v.get('max_pages', 25)} extra pages (about {100 * v.get('max_pages', 25):,} Helius credits max on the first backfill). Reason: {v.get('reason', '-')}. "
                 + (f"Result: {r['n_pass']} copyable trades ({r['n_pass_closed']} closed), win rate {r['win_rate']}, positive weeks {r['pos_weeks']}, cut: {'; '.join(r['cut']) or '-'}." if r else "Not analysed this run (no wallet mapping)."))
    L += ["", "## Evidence per trader"]
    for r in out:
        L += [f"### {r['trader']}: `{r['wallet']}`", f"- Provenance: {r['provenance']}",
              f"- {r['n_swaps']} swaps, {r['relayed_fomo_swaps']} fomo-app-relayed txs (fee payer {RELAYER[:8]}… or platform fee to {FOMOFEE[:8]}…). {r['all_rounds']} rounds in total; copying all of them at $50 would give ${r['all_rounds_copy_pnl_usd']}. Median hold is {r['median_hold_min']} min.",
              (f"- First tx {r['first_tx']}; first funder `{r['funder']}` ({r['fund_sol']} SOL, https://solscan.io/tx/{r['fund_sig']}); funder in rugger lists: {r['funder_in_rugger_lists']}" if r['funder'] else f"- First tx {r['first_tx']}; first funder: not found (no plain SOL transfer in the first 5 txs)"),
              f"- Copy PnL without the best week: ${round(sum(r['weekly_usd'].values()) - max(r['weekly_usd'].values()), 2) if r['weekly_usd'] else 0} (shows whether one week carries the result)",
              "- Worst copyable trades: " + "; ".join(f"{x['mint']} {x['pnl_pct']}% ({x['buy_at']}, https://solscan.io/tx/{x['sig']})" for x in r["worst_passing"]), ""]
    open(os.path.join(BASE, "leader-rank.md"), "w").write("\n".join(L))
    print("wrote leader-rank.md", len(out), "traders;", len(rows), "swap rows")

if __name__ == "__main__": main()
