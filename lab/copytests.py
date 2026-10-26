#!/usr/bin/env python3
"""Copyfomo leader tests (PAPER ONLY), from Scout's /workspace/onchain-intel/trader_trades.csv (_benjitrades, ExactTallTakin).
  1. chase-cap sweep 10/15/25% (copyfomo already runs 'max chase 15%'): our fill = 1-min chart price at buy + bot lag,
     leader fill = the leader's own swap (Scout's enh_<trader>_all.json: buy_usd / tokens received).
  2. rugcheck hard-reject filters at buy time: mint/freeze open, LP unlocked (<50% locked), top10 >18% / >25% (ex-pool),
     creator >5%, danger flags. Point-in-time status per field is reported; non-reconstructable fields are LOOKAHEAD.
  3. entry-delay cost 20/40/60 s (alerts + filtered manual copy).
Costs: 2%/side + $0.05, liquidity slippage (assumed pool), -25% stop with ~5 pts extra stop slippage (gap -> open - 5 pts),
exit at the leader's sell price (leader fill x (1+pnl_pct)). Network: <= max_gecko_calls GeckoTerminal + <= max_rugcheck_calls
rugcheck per run (6.5 s / 2 s spacing), newest trades first, everything cached in data/copytest/. --no-network = cache only."""
import csv, glob, json, math, os, statistics, sys, time
from labcore import LAB, DATA, load_json, atomic_write, get_json, ts_of, iso, load_config
save_json = lambda p, o: atomic_write(p, json.dumps(o))
import guards
OI = "/workspace/onchain-intel"; CT = os.path.join(DATA, "copytest"); os.makedirs(os.path.join(CT, "candles"), exist_ok=True)
os.makedirs(os.path.join(CT, "rugcheck"), exist_ok=True)
AMM_AUTH = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1", "GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL",
            "WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh", "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"}

def trades():
    rows = []
    for r in csv.DictReader(open(os.path.join(OI, "trader_trades.csv"))):
        if not r.get("sell_at"): continue
        rows.append({"trader": r["trader"], "wallet": r["wallet"], "mint": r["mint"], "t": ts_of(r["buy_at"]), "t_exit": ts_of(r["sell_at"]),
                     "buy_usd": float(r["buy_usd"] or 0), "ret": float(r["pnl_pct"]) / 100})
    return sorted(rows, key=lambda r: r["t"])

_ENH = {}
def leader_fill(r):
    """USD per token the leader paid (their own swap), or None."""
    if r["trader"] not in _ENH:
        _ENH[r["trader"]] = load_json(os.path.join(OI, f"data/enh_{r['trader']}_all.json"), []) or []
    best = None
    for tx in _ENH[r["trader"]]:
        ts = tx.get("timestamp") or 0
        if abs(ts - r["t"]) > 120: continue
        amt = sum(float(x.get("tokenAmount") or 0) for x in tx.get("tokenTransfers") or []
                  if x.get("mint") == r["mint"] and x.get("toUserAccount") == r["wallet"])
        if amt > 0 and (best is None or abs(ts - r["t"]) < best[0]): best = (abs(ts - r["t"]), r["buy_usd"] / amt)
    return best[1] if best else None

def pools():
    p = load_json(os.path.join(CT, "pools.json"), {})
    for x in load_json(os.path.join(OI, "data/gt_pump_pools.json"), []) or []:
        if x.get("token") and x.get("pool"): p.setdefault(x["token"], x["pool"])
    return p

def fetch(cfg, rows):
    Q, F = cfg["copytrade"], cfg["fetch"]; P = pools(); g = rc = 0
    for r in sorted(rows, key=lambda r: -r["t"]):
        if g >= Q.get("max_gecko_calls", 8): break
        cf = os.path.join(CT, "candles", f"{r['mint']}_{int(r['t'])}.json")
        if os.path.exists(cf): continue
        if r["mint"] not in P:
            j = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{r['mint']}/pools?page=1", F["gecko_spacing_s"]); g += 1
            try: P[r["mint"]] = j["data"][0]["attributes"]["address"]
            except Exception: P[r["mint"]] = None
            save_json(os.path.join(CT, "pools.json"), P)
            if g >= Q.get("max_gecko_calls", 8): break
        pool = P.get(r["mint"])
        if not pool: save_json(cf, {"fetched": time.time(), "pool": None, "rows": []}); continue
        before = int(min(r["t_exit"] + 600, r["t"] + 16 * 3600))
        j = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit=1000"
                     f"&currency=usd&token=base&before_timestamp={before}", F["gecko_spacing_s"]); g += 1
        try: rows_ = sorted([[int(x[0])] + [float(v) for v in x[1:6]] for x in j["data"]["attributes"]["ohlcv_list"]])
        except Exception: rows_ = None
        if rows_ is not None: save_json(cf, {"fetched": time.time(), "pool": pool, "rows": rows_})
    for m in dict.fromkeys(r["mint"] for r in sorted(rows, key=lambda r: -r["t"])):
        if rc >= Q.get("max_rugcheck_calls", 8): break
        f = os.path.join(CT, "rugcheck", m + ".json")
        if os.path.exists(f): continue
        rep = get_json(f"https://api.rugcheck.xyz/v1/tokens/{m}/report", F["rugcheck_spacing_s"]); rc += 1
        if rep: save_json(f, {"fetched": time.time(), "report": rep})
    return g, rc

def price_at(c, t):
    """Linear interpolation inside the 1-min candle containing t (open at start -> close at end). None if no candle."""
    prev = None
    for x in c:
        if x[0] <= t < x[0] + 60: return x[1] + (x[4] - x[1]) * (t - x[0]) / 60
        if x[0] + 60 <= t: prev = x
        else: break
    # GeckoTerminal omits minutes without trades: carry the last close forward up to 2 min
    return prev[4] if prev and t - prev[0] <= 180 else None

def hard(rep, mint, pool):
    """-> {rule: (hit, pit)} from a rugcheck report fetched AFTER the trade."""
    if not rep: return {}
    rc = guards.rugguard_mod("/workspace/runner-radar").rc_extract(rep, pool)
    pumpmint = mint.endswith("pump")      # pump.fun mints: authorities revoked at creation, cannot be re-enabled
    auth_open = bool(rep.get("mintAuthority") or rep.get("freezeAuthority"))
    pk = {pool} | {m.get("pubkey") for m in rep.get("markets") or []}
    for m in rep.get("markets") or []:
        pk |= {m.get("liquidityA"), m.get("liquidityB"), (m.get("liquidityAAccount") or {}).get("owner"), (m.get("liquidityBAccount") or {}).get("owner")}
    known = rep.get("knownAccounts") or {}
    hold = [float(t.get("pct") or 0) for t in rep.get("topHolders") or [] if not (t.get("owner") in pk or t.get("address") in pk or t.get("owner") in AMM_AUTH
            or ((known.get(t.get("owner")) or known.get(t.get("address")) or {}).get("type") or "").upper() == "AMM")]
    t10 = sum(sorted(hold, reverse=True)[:10]) if rep.get("topHolders") is not None else None
    lp = rc["lp_locked"]
    if lp is None:
        lps = [(m.get("lp") or {}).get("lpLockedPct") for m in rep.get("markets") or []]; lps = [x for x in lps if x is not None]; lp = max(lps) if lps else None
    return {"mint_freeze_open": (auth_open, auth_open or pumpmint),        # open now => open at buy; revoked pump mint => revoked at buy
            "lp_unlocked": (lp is not None and lp < 50, False),
            "top10_gt18": (t10 is not None and t10 > 18, False), "top10_gt25": (t10 is not None and t10 > 25, False),
            "creator_gt5": ((rc["creator_pct"] or 0) > 5, False), "danger_flags": (bool(rc["danger"]), False)}

def sim(cfg, r, c, delay_s, chase=None, stop=-0.25, ss=0.05, liq=20000.0, bet=10.0):
    """-> (status, ret, info). status in closed / skip_chase / no_data."""
    C = cfg["costs"]; fee, fx = C["fee_per_side"], C["fixed_cost_usd"]
    lf = leader_fill(r); p_l = price_at(c, r["t"]); p_e = price_at(c, r["t"] + delay_s)
    if not p_e or not (lf or p_l): return "no_data", None, {}
    if lf and p_l and abs(p_l / lf - 1) > 0.3: return "no_data", None, {"pool_mismatch": True}   # chart pool != leader's fill
    ref = lf or p_l
    ch = p_e / ref - 1
    if chase is not None and ch > chase: return "skip_chase", None, {"chase": ch}
    s = min(C["max_slippage"], C["base_slippage"] + C["impact_mult"] * bet / liq)
    entry = p_e * (1 + s); stop_px = entry * (1 + stop); exit_px, how = ref * (1 + r["ret"]), "leader"
    for x in c:
        if x[0] + 60 <= r["t"] + delay_s or x[0] >= r["t_exit"]: continue
        if x[0] <= r["t"] + delay_s:          # candle containing the entry: its low may predate us -> judge on its close only
            if x[4] <= stop_px: exit_px, how = entry * (1 + stop - ss), "stop"; break
            continue
        if x[3] <= stop_px:
            o = x[1]
            exit_px, how = (o * (1 - ss) if o <= stop_px else entry * (1 + stop - ss)), "stop"; break
    exit_px *= (1 - s)
    cash = max(0.0, (bet * (1 - fee) - fx) * exit_px / entry * (1 - fee) - fx)
    return "closed", cash / bet - 1, {"chase": ch, "exit": how, "leader_fill": bool(lf)}

def stats(xs):
    if not xs: return {"n": 0}
    n = len(xs); m = statistics.mean(xs); sd = statistics.stdev(xs) if n > 1 else 0
    return {"n": n, "mean": m, "net": sum(xs) * 10, "win": sum(x > 0 for x in xs) / n, "ex_best": (sum(xs) - max(xs)) * 10,
            "ci": (m - 1.96 * sd / math.sqrt(n), m + 1.96 * sd / math.sqrt(n)) if n > 1 else (m, m)}

def main():
    cfg = load_config(); Q = cfg["copytrade"]; rows = trades()
    g = rc = 0
    if "--no-network" not in sys.argv: g, rc = fetch(cfg, rows)
    P = pools(); lag = Q.get("bot_lag_s", 10); stop, ss, liq = Q.get("stop", -0.25), Q.get("stop_slip", 0.05), Q.get("assumed_liq_usd", 20000)
    split = rows[int(len(rows) * 0.6)]["t"] if rows else 0
    data = []
    for r in rows:
        cf = load_json(os.path.join(CT, "candles", f"{r['mint']}_{int(r['t'])}.json"))
        rep = (load_json(os.path.join(CT, "rugcheck", r["mint"] + ".json")) or {}).get("report")
        data.append((r, (cf or {}).get("rows") or [], cf is not None, hard(rep, r["mint"], P.get(r["mint"])), rep is not None))
    have = [d for d in data if d[1]]
    out = [f"# Copyfomo leader tests ({iso(time.time())}, PAPER ONLY)", "",
           f"Closed leader round trips: {len(rows)} ({', '.join(sorted({r['trader'] for r in rows}))}). With 1-min candles: {len(have)}; "
           f"candle fetch attempted: {sum(d[2] for d in data)}; trades with a rugcheck report: {sum(d[4] for d in data)}; leader fill from own swap: "
           f"{sum(1 for d in have if leader_fill(d[0]))}/{len(have)}. This run: {g} GeckoTerminal + {rc} rugcheck calls.",
           f"Costs: 2%/side + $0.05, slippage on ${liq:,.0f} assumed pool, stop {stop:.0%} with {ss*100:.0f} pts extra slippage (gap: open - {ss*100:.0f} pts), "
           f"bot lag {lag}s, $10/trade, exit at leader's sell price. No max-open cap (per-trade comparison). OOS = buys after {iso(split)}.", ""]
    def line(name, res):
        cl = [x for x in res if x[0] == "closed"]; s = stats([x[1] for x in cl]); so = stats([x[1] for x in cl if x[2] >= split])
        if not s["n"]: return f"| {name} | 0 | - | - | - | - | - | {sum(x[0]=='skip_chase' for x in res)} |"
        return (f"| {name} | {s['n']} ({so['n']} OOS) | {s['win']:.0%} | {s['mean']:+.1%} | [{s['ci'][0]:+.2f},{s['ci'][1]:+.2f}] | {s['net']:+.2f} | "
                f"{s['ex_best']:+.2f} | {sum(x[0]=='skip_chase' for x in res)} | {so.get('mean', 0):+.1%} |")
    H = ["| variant | trades | win | mean | CI95 | net $ | net ex best $ | skipped (chase) | OOS mean |", "|---|---|---|---|---|---|---|---|---|"]
    run = lambda sub, delay, chase=None: [(*sim(cfg, d[0], d[1], delay, chase, stop, ss, liq)[:2], d[0]["t"]) for d in sub]
    out += ["## 1. Chase cap sweep (copyfomo has max chase 15% on; our fill = chart price at buy + bot lag vs leader's own fill)", ""] + H
    for ch in (None, 0.10, 0.15, 0.25):
        out.append(line(f"chase {'off' if ch is None else f'{ch:.0%}'} (lag {lag}s)", run(have, lag, ch)))
    chs = [sim(cfg, d[0], d[1], lag)[2].get("chase") for d in have]; chs = sorted(x for x in chs if x is not None)
    if chs: out += ["", f"Chase at {lag}s: median {statistics.median(chs):+.1%}, share > 10/15/25%: "
                    f"{sum(x>0.10 for x in chs)/len(chs):.0%} / {sum(x>0.15 for x in chs)/len(chs):.0%} / {sum(x>0.25 for x in chs)/len(chs):.0%}."]
    out += ["", "## 2. Rugcheck hard rejects at buy time (skip rejects) -- chase 15%, lag as above", "",
            "PIT: mint/freeze is reconstructable (authority can only be revoked, and pump.fun mints are revoked at creation). "
            "LP lock, top10, creator %, danger flags come from a report fetched AFTER the trade = LOOKAHEAD (buy-time holders cannot "
            "be reconstructed: no holder history for these mints; Scout's early-buyer files do not cover them).", ""] + H
    cov = [d for d in have if d[3]]
    out.append(line("no filter (coins with report)", run(cov, lag, 0.15)))
    rules = ["mint_freeze_open", "lp_unlocked", "top10_gt18", "top10_gt25", "creator_gt5", "danger_flags"]
    for k in rules + ["ALL (mint/freeze, LP, top10>25, creator, danger)"]:
        ks = rules[:2] + rules[3:] if k.startswith("ALL") else [k]
        keep = [d for d in cov if not any(d[3][x][0] for x in ks)]; hit = [d for d in cov if any(d[3][x][0] for x in ks)]
        pit = all(d[3][x][1] for d in cov for x in ks)
        rs = run(hit, lag, 0.15); cl = [x[1] for x in rs if x[0] == "closed"]
        out.append(line(f"skip {k}{'' if pit else ' [LOOKAHEAD]'}", run(keep, lag, 0.15)) +
                   f" rejected {len(hit)} coins-trades ({len(cl)} simulable): their mean {statistics.mean(cl):+.1%} |" if cl else line(f"skip {k}{'' if pit else ' [LOOKAHEAD]'}", run(keep, lag, 0.15)) + f" rejected {len(hit)} |")
    out += ["", "## 3. Entry delay cost (alerts + filtered manual copy; chase cap 15%)", "", 
            "1-min candles interpolated open->close: sub-minute delays are approximations.", ""] + H
    for dl in (0, lag, 20, 40, 60):
        out.append(line(f"delay {dl}s", run(have, dl, 0.15)))
    out += ["", "## Caveats", "", "- Leader P&L/exit from Scout's trader_trades.csv (their round trips); open positions excluded.",
            "- Pool depth assumed; real slippage on small pools is larger. Candle history for dead coins may be missing (no_data).",
            "- 2 leaders only; trades are not independent (same leader, same nights)."]
    p = os.path.join(LAB, "out/copyfomo_tests.md"); open(p + ".tmp", "w").write("\n".join(out) + "\n"); os.replace(p + ".tmp", p)
    print(f"copytests: {len(rows)} round trips, {len(have)} with candles, {sum(d[4] for d in data)} rugcheck; calls gecko {g} rugcheck {rc} -> {p}")

if __name__ == "__main__":
    main()
