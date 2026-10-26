#!/usr/bin/env python3
"""Copy-candidate simulator (PAPER ONLY; proposals only, never instructs a trading bot).
Simulates copying each trader with copyfomo's settings: first buy per coin only (adds ignored), skip leader buys < $50,
skip coins < $100k mcap at buy, TP +100% sells half, SL -25% filled ~5 pts worse (gap-through: candle open - 5 pts),
max chase 15% (skip if our estimated fill > 15% above the leader's entry), 3-10 s delay (1-min candles: approximation),
remainder exits with the leader, 2%/side fees + liquidity slippage. Plus the stake-size / nightly-loss-limit test.
Inputs: /workspace/onchain-intel/trader_trades.csv (+ enh_<trader>_all.json for the leader's own fill), leader-rank.md (Scout,
pending), /workspace/copyfomo/leaderboard-*.md (Copycat, pending), x-watch-log.md (TRUTH calibration).
Reruns only when inputs change (out/.copy_candidates.sig) unless --force. Output: out/copy_candidates.md (+ .csv)."""
import csv, glob, hashlib, json, math, os, random, re, statistics, sys, time
from labcore import LAB, DATA, load_json, atomic_write, get_json, ts_of, iso, load_config, night_of
import scoring
OI, CF = "/workspace/onchain-intel", "/workspace/copyfomo"
CT = os.path.join(DATA, "copytest")
S = dict(min_buy_usd=50, min_mcap=100_000, tp=1.0, tp_frac=0.5, sl=-0.25, sl_slip=0.025, crash_close=False, chase=0.15, delays=(3, 10),
         fee=0.02, fixed=0.015, liq=20_000, base_slip=0.005, impact=2.0, max_slip=0.15, stake=9.40,
         balance=91.0, night_limit=0.20, trade_cap=0.15, stakes=(9.40, 8.0, 7.0, 6.0, 5.0, 4.0), approx_lag=0.02, top_n=5)
# Calibrated on the real TRUTH copy (n=1, 2026-10-23): -$2.78 on $9.40 (-29.5%) = chart entry, stop filled ~2.5% below the -25% trigger,
# copyfomo 2%/side inside the position P&L, +$0.03 gas billed back. CENTRAL = that fit; CONSERVATIVE = 5% below trigger and never better
# than a crash candle's close (the previous model, ~-38% on TRUTH). DEX/pool fee is inside the chart price; base_slip covers route/impact.
MODELS = {"central": dict(sl_slip=0.025, crash_close=False), "conservative": dict(sl_slip=0.05, crash_close=True)}

def inputs():
    fs = [os.path.join(OI, "trader_swaps.csv"), os.path.join(OI, "data/leader_mappings.json"), os.path.join(OI, "trader_trades.csv"), os.path.join(OI, "leader-rank.md"), os.path.join(CF, "x-watch-log.md")] + \
         sorted(glob.glob(os.path.join(CF, "leaderboard*.md"))) + sorted(glob.glob(os.path.join(OI, "data/enh_*_all.json"))) + \
         ["/workspace/trader-analysis/wallets.json", os.path.join(OI, "data/trader_wallets.json")]
    h = hashlib.sha1()
    for f in fs:
        if os.path.exists(f): st = os.stat(f); h.update(f"{f}{st.st_size}{int(st.st_mtime)}".encode())
    h.update(str(len(glob.glob(os.path.join(CT, "candles/*.json")))).encode()); h.update(open(__file__, "rb").read())
    return h.hexdigest(), fs

# ---------- data ----------
_ENH = {}
def leader_fill(tr, wallet, mint, t, usd):
    if tr not in _ENH: _ENH[tr] = load_json(os.path.join(OI, f"data/enh_{tr}_all.json"), []) or []
    best = None
    for tx in _ENH[tr]:
        if abs((tx.get("timestamp") or 0) - t) > 120: continue
        amt = sum(float(x.get("tokenAmount") or 0) for x in tx.get("tokenTransfers") or [] if x.get("mint") == mint and x.get("toUserAccount") == wallet)
        if amt > 0 and (best is None or abs(tx["timestamp"] - t) < best[0]): best = (abs(tx["timestamp"] - t), usd / amt)
    return best[1] if best else None

def supply(mint):
    if mint.endswith("pump"): return 1e9                     # pump.fun fixed supply
    for f in (os.path.join(CT, "rugcheck", mint + ".json"), os.path.join(DATA, "rugcheck_full", mint + ".json")):
        j = load_json(f)
        rep = (j or {}).get("report", j) if j else None
        try:
            tk = rep["token"]; return float(tk["supply"]) / 10 ** int(tk["decimals"])
        except Exception: pass
    return None

def candles(mint, t):
    j = load_json(os.path.join(CT, "candles", f"{mint}_{int(t)}.json"))
    return (j or {}).get("rows") or []

def price_at(c, t):
    prev = None
    for x in c:
        if x[0] <= t < x[0] + 60: return x[1] + (x[4] - x[1]) * (t - x[0]) / 60
        if x[0] + 60 <= t: prev = x
        else: break
    return prev[4] if prev and t - prev[0] <= 180 else None

BAD_MAP = {"cosby", "zelda89", "Altcoinist"}                 # Scout 2026-10-23: these mappings look wrong -> excluded
def load_trades():
    """Prefer Scout's per-swap file (trader_swaps.csv): one copy per (trader, mint) = the leader's FIRST buy; leader exit = last sell on
    that mint; leader return = total sell USD / total buy USD - 1 (partial exits still held count as unsold -> understated). Fallback:
    trader_trades.csv round trips."""
    sw = os.path.join(OI, "trader_swaps.csv")
    if os.path.exists(sw):
        rows = sorted(csv.DictReader(open(sw)), key=lambda r: r["timestamp"]); g = {}
        for r in rows:
            if r["trader"] in BAD_MAP: continue
            g.setdefault((r["trader"], r["mint"]), []).append(r)
        out = []
        for (trader, mint), rs in g.items():
            buys = [r for r in rs if r["side"] == "buy"]
            if not buys: continue                                # sold a coin bought before the window
            b0 = buys[0]; t = ts_of(b0["timestamp"]); sells = [r for r in rs if r["side"] == "sell" and r["timestamp"] >= b0["timestamp"]]
            bu, su = sum(float(r["usd_size"] or 0) for r in buys), sum(float(r["usd_size"] or 0) for r in sells)
            sup = supply(mint); mc = float(b0["mcap_at_fill"] or 0)
            out.append({"trader": trader, "wallet": b0["wallet"], "mint": mint, "t": t, "usd": float(b0["usd_size"] or 0),
                        "t_exit": ts_of(sells[-1]["timestamp"]) if sells else None, "ret": (su / bu - 1) if (sells and bu) else None,
                        "lf": (mc / sup) if (mc and sup) else leader_fill(trader, b0["wallet"], mint, t, float(b0["usd_size"] or 0))})
        out.sort(key=lambda x: x["t"]); return out, len(rows)
    seen, out = set(), []
    rows = sorted(csv.DictReader(open(os.path.join(OI, "trader_trades.csv"))), key=lambda r: r["buy_at"])
    for r in rows:
        k = (r["trader"], r["mint"])
        if k in seen: continue                                 # first buy per coin only
        seen.add(k)
        t = ts_of(r["buy_at"]); usd = float(r["buy_usd"] or 0)
        out.append({"trader": r["trader"], "wallet": r["wallet"], "mint": r["mint"], "t": t, "usd": usd,
                    "t_exit": ts_of(r["sell_at"]) if r["sell_at"] else None, "ret": float(r["pnl_pct"]) / 100 if r["sell_at"] else None,
                    "lf": leader_fill(r["trader"], r["wallet"], r["mint"], t, usd)})
    return out, len(rows)

def coverage():
    sw = os.path.join(OI, "trader_swaps.csv"); cov = {}
    if os.path.exists(sw):
        for r in csv.DictReader(open(sw)):
            a = cov.setdefault(r["trader"], [r["timestamp"], r["timestamp"]]); a[0] = min(a[0], r["timestamp"]); a[1] = max(a[1], r["timestamp"])
    return cov

# ---------- simulation ----------
def slip(stake): return min(S["max_slip"], S["base_slip"] + S["impact"] * stake / S["liq"])

def sim(tr, delay, stake=1.0):
    """-> dict(status, ret, t_exit, mode, flags). ret is fraction of stake after all costs."""
    if tr["usd"] < S["min_buy_usd"]: return {"status": "skip_small_buy"}
    if tr["ret"] is None: return {"status": "open_leader"}
    c = candles(tr["mint"], tr["t"]); sup = supply(tr["mint"]); fl = []
    p_l = price_at(c, tr["t"]) if c else None
    ref = tr["lf"] or p_l
    if c and tr["lf"] and p_l and abs(p_l / tr["lf"] - 1) > 0.3: c, p_l = [], None; fl.append("pool mismatch")
    mcap = ref * sup if (ref and sup) else None
    if mcap is None: fl.append("mcap unknown")
    elif mcap < S["min_mcap"]: return {"status": "skip_mcap", "mcap": mcap}
    s, fee, fx = slip(stake), S["fee"], S["fixed"] / stake
    exit_lead = None
    if c and ref and price_at(c, tr["t"] + delay):
        mode = "path"; p_e = price_at(c, tr["t"] + delay)
        if p_e / ref - 1 > S["chase"]: return {"status": "skip_chase", "chase": p_e / ref - 1}
        entry = p_e * (1 + s); exit_lead = ref * (1 + tr["ret"])
        tp_px, sl_px = entry * (1 + S["tp"]), entry * (1 + S["sl"]); legs, rem, t_out = [], 1.0, tr["t_exit"]
        for x in c:
            if x[0] + 60 <= tr["t"] + delay or x[0] >= tr["t_exit"]: continue
            first = x[0] <= tr["t"] + delay                    # entry candle: only its close is known to be after us
            lo, hi, o = (x[4], x[4], p_e) if first else (x[3], x[2], x[1])
            if lo <= sl_px:                                     # stop before target in the same candle (conservative)
                px = o * (1 - S["sl_slip"]) if (o <= sl_px and not first) else sl_px * (1 - S["sl_slip"])
                if S["crash_close"] and x[4] < sl_px: px = min(px, x[4])             # fast 1-min crash: real TRUTH stop filled at that candle's close
                legs.append((rem, px)); rem = 0; t_out = x[0] + 60; break
            if rem == 1.0 and hi >= tp_px:
                legs.append((S["tp_frac"], max(tp_px, o) if not first else tp_px)); rem -= S["tp_frac"]
        if rem: legs.append((rem, exit_lead))
    else:
        mode = "approx"; fl.append("no 1-min candles: path unknown")
        if not ref: ref = 1.0
        entry = ref * (1 + S["approx_lag"]) * (1 + s); exit_lead = ref * (1 + tr["ret"]); r_l = exit_lead / entry - 1
        if r_l <= -0.8: legs = [(1.0, exit_lead)]               # rug: gap through the stop
        elif r_l < S["sl"]: legs = [(1.0, entry * (1 + S["sl"]) * (1 - S["sl_slip"]))]
        elif r_l >= S["tp"]: legs = [(S["tp_frac"], entry * (1 + S["tp"])), (1 - S["tp_frac"], exit_lead)]
        else: legs = [(1.0, exit_lead)]
        t_out = tr["t_exit"]
    gross_in = (1 - fee) - fx
    cash = sum(f * gross_in * px * (1 - s) / entry * (1 - fee) for f, px in legs) - fx
    return {"status": "closed", "ret": max(cash, 0) - 1, "t": tr["t"], "t_exit": t_out, "mode": mode, "flags": fl, "mcap": mcap}

def stats(rets):
    n = len(rets)
    if not n: return {"trades": 0, "mean_ret": None}
    m = statistics.fmean(rets); sd = statistics.stdev(rets) if n > 1 else 0
    return {"trades": n, "mean_ret": m, "ci_lo": m - 1.96 * sd / math.sqrt(n) if n > 1 else m}

def maxdd(pnls):
    eq = pk = dd = 0.0
    for p in pnls: eq += p; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dd

WHY = {"common": "Leader round trips come from Scout's reconstruction of their wallet (trader_trades.csv); copyfomo's real fills are "
       "not logged, so our fill is a chart estimate. Most trades lack 1-min candles yet (approx mode: no path, so TP/SL hits are guessed "
       "from the round-trip result). A trader's past month is a tiny, regime-specific sample; leaders change style or get front-run by "
       "their own followers.",
       "other": "The leader (who can dump into copiers), bundlers/snipers who bought before the leader, and other copy bots racing us."}

def per_trader(trs, delay):
    out = {}
    for tr in trs:
        r = sim(tr, delay, S["stake"]); r["tr"] = tr
        out.setdefault(tr["trader"], []).append(r)
    return out

def band(trs, split, model):
    """Per-trader net/ex-best/score and all-5-fire P(limit) under a stop/fee model; restores S."""
    old = {k: S[k] for k in model}; S.update(model)
    try:
        R = per_trader(trs, max(S["delays"])); out = {}
        for name, rs in R.items():
            cl = sorted([r for r in rs if r["status"] == "closed"], key=lambda r: r["t"]); pn = [r["ret"] * S["stake"] for r in cl]
            closed = [{"t": r["t"], "pnl": p, "ret": r["ret"], "is_oos": r["t"] >= split} for r, p in zip(cl, pn)]
            sc = scoring.score(stats([r["ret"] for r in cl]), None, closed, scoring.mc_drawdown(pn, S["balance"], 1000) if pn else None)
            out[name] = dict(cl=cl, net=sum(pn), ex_best=sum(pn) - max(pn) if pn else 0, score=sc["score_total"],
                             mean=statistics.fmean([r["ret"] for r in cl]) if cl else None)
        return out
    finally: S.update(old)

def p_limit_all5(cls, stakes, N=10000, seed=11):
    lim = S["balance"] * S["night_limit"]; tn = {}
    for cl in cls:
        for r in cl: tn.setdefault((id(cl), night_of(r["t"])), []).append(r)
    pool = list(tn.values()); rnd = random.Random(seed); out = {}
    for stake in stakes:
        hit = 0
        for _ in range(N):
            ev = []
            for k in range(S["top_n"]):
                for r in rnd.choice(pool):
                    st = (r["t"] - 12 * 3600) % 86400; ev.append((st + ((r["t_exit"] or r["t"]) - r["t"]), r["ret"] * stake))
            real = mn = 0.0
            for _, p in sorted(ev): real += p; mn = min(mn, real)
            hit += mn <= -lim
        out[stake] = hit / N
    return out

def main():
    force = "--force" in sys.argv
    sig, fs = inputs(); sp = os.path.join(LAB, "out/.copy_candidates.sig")
    if not force and os.path.exists(sp) and open(sp).read() == sig:
        print("copy_candidates: inputs unchanged, skip"); return
    trs, nrows = load_trades()
    lr, cb = os.path.join(OI, "leader-rank.md"), sorted(glob.glob(os.path.join(CF, "leaderboard*.md")))
    lb = {}                                                    # handle -> {view: row}
    for f in cb:
        view = None
        for line in open(f):
            m = re.match(r"##\s*(\w+)", line)
            if m: view = m.group(1); continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 11 and cells[0].isdigit():
                lb.setdefault(cells[1].lstrip("@"), {})[view] = dict(rank=int(cells[0]), pnl=cells[3], trades=cells[5], avg_buy=cells[7], copiers=cells[10])
    if os.path.exists(lr):
        for h in re.findall(r"^\|\s*\d*\s*\|?\s*@?([A-Za-z0-9_]{2,20})\s*\|", open(lr).read(), re.M): lb.setdefault(h, {}).setdefault("scout", {})
    wal = {}
    for f in ("/workspace/trader-analysis/wallets.json", os.path.join(OI, "data/trader_wallets.json")):
        for h, v in (load_json(f, {}) or {}).items():
            sol = v.get("solana") if isinstance(v, dict) else next((x for x in v if not x.startswith("0x")), None)
            if sol: wal.setdefault(h, sol)
    named = set(lb)
    traders = sorted({t["trader"] for t in trs})
    res = {d: per_trader(trs, d) for d in S["delays"]}
    split = sorted(t["t"] for t in trs)[int(len(trs) * 0.6)] if trs else 0
    board = []
    for name in traders:
        R = res[max(S["delays"])][name]; cl = [r for r in R if r["status"] == "closed"]; cl.sort(key=lambda r: r["t"])
        pn = [r["ret"] * S["stake"] for r in cl]
        st = stats([r["ret"] for r in cl])
        closed = [{"t": r["t"], "pnl": r["ret"] * S["stake"], "ret": r["ret"], "is_oos": r["t"] >= split} for r in cl]
        mc = scoring.mc_drawdown(pn, S["balance"], 1000) if pn else None
        sc = scoring.score(st, None, closed, mc)
        ni = scoring.nights(closed)
        R3 = [r for r in res[min(S["delays"])][name] if r["status"] == "closed"]
        skips = {}
        for r in R: skips[r["status"]] = skips.get(r["status"], 0) + 1
        oos = [r["ret"] for r in cl if r["t"] >= split]
        board.append({"trader": name, "trades": len(cl), "win": sum(r["ret"] > 0 for r in cl) / len(cl) if cl else 0,
                      "net": sum(pn), "ex_best": sum(pn) - max(pn) if pn else 0, "maxdd": maxdd(pn), "mc": mc, "score": sc,
                      "nights": ni, "net3": sum(r["ret"] * S["stake"] for r in R3), "skips": skips, "oos_n": len(oos),
                      "oos_mean": statistics.fmean(oos) if oos else None, "path": sum(r["mode"] == "path" for r in cl),
                      "mean": st["mean_ret"], "ci_lo": st.get("ci_lo"), "named": name in named, "cl": cl})
    board.sort(key=lambda b: (-b["score"]["score_total"], -b["ex_best"]))
    f2 = lambda v: "-" if v is None else f"{v:+.2f}"
    pc = lambda v: "-" if v is None else f"{v*100:+.0f}%"
    L = [f"# Copy candidates ({iso(time.time())}, PAPER ONLY, proposals only)", "",
         f"Settings modelled (copyfomo): first buy per coin only, skip leader buys < ${S['min_buy_usd']}, skip mcap < ${S['min_mcap']/1e3:.0f}k at buy, "
         f"TP +100% sells half, SL -25% (central: fill 2.5% below trigger; conservative band below), max chase 15%, delay 3-10 s "
         f"(1-min GeckoTerminal candles, interpolated: an APPROXIMATION; headline uses 10 s), remainder exits with the leader, "
         f"2%/side + ${S['fixed']:.3f}/side, slippage {S['base_slip']*100:.1f}% + {S['impact']}x stake/${S['liq']/1e3:.0f}k assumed pool. Stake ${S['stake']:.2f}, balance ${S['balance']:.0f}.", "",
         "## Inputs", "",
         f"- {'trader_swaps.csv (Scout per-swap)' if os.path.exists(os.path.join(OI, 'trader_swaps.csv')) else 'trader_trades.csv'}: {nrows} rows, {len(trs)} first buys, traders: {', '.join(traders)}.",
         f"- Scout leader-rank.md: {'present' if os.path.exists(lr) else 'MISSING (Scout asked)'}.",
         f"- Copycat leaderboard: {', '.join(os.path.basename(x) for x in cb) if cb else 'MISSING (expected /workspace/copyfomo/leaderboard-2026-10-23.md)'}.",
         f"- Copycat leaderboard handles: {len(lb)}; with a Solana wallet in trader-analysis/wallets.json or Scout trader_wallets.json: "
         f"{sum(h in wal for h in lb)}; with per-swap history (trader_trades.csv): {sum(h in traders for h in lb)}.",
         f"- 1-min candle coverage: {sum(b['path'] for b in board)}/{sum(b['trades'] for b in board)} simulated trades (rest = approx mode, path unknown).", "",
         "## Leaderboard -> wallet -> swap-history mapping", "",
         "Handles are matched by exact name. Wallet pairings come from /workspace/trader-analysis/wallets.json (source not recorded, Scout rates them weak-medium). "
         "Leaderboard PnL/trades are copyfomo's own unverified figures; win rate, wallet, account age, typical mcap are not shown by the bot.", "",
         "| handle | 30d rank | 7d rank | bot PnL (30d / 7d) | bot trades | avg buy | copiers | Solana wallet | swap history | status |",
         "|---|---|---|---|---|---|---|---|---|---|"] + [
         f"| {h} | {v.get('30d', {}).get('rank', '-')} | {v.get('7d', {}).get('rank', '-')} | {v.get('30d', {}).get('pnl', '-')} / {v.get('7d', {}).get('pnl', '-')} | "
         f"{(v.get('30d') or v.get('7d') or {}).get('trades', '-')} | {(v.get('30d') or v.get('7d') or {}).get('avg_buy', '-')} | {(v.get('30d') or v.get('7d') or {}).get('copiers', '-')} | "
         f"{(wal[h][:6] + '...' + wal[h][-4:]) if h in wal else 'NOT MAPPED'} | {sum(t['trader'] == h for t in trs) or '-'} | "
         f"{'simulated below' if h in traders else ('wallet known, waiting for Scout swap history' if h in wal else 'cannot simulate: no wallet')} |"
         for h, v in sorted(lb.items(), key=lambda kv: (kv[0] not in traders, kv[0] not in wal, min(x.get('rank', 99) for x in kv[1].values()) if kv[1] else 99))] + ["",
         "## Ranking (score /25 per METHOD.md; candidate needs >= 18, >= 50 trades, holds OOS)", "",
         "| # | trader | trades | win | mean | net $ | net ex best $ | max DD $ | MC DD p5/p50/p95 (% of $91) | nights +/total | OOS n / mean | score | net $ at 3 s | skipped |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, b in enumerate(board, 1):
        mc = b["mc"]; sk = ", ".join(f"{k} {v}" for k, v in b["skips"].items() if k != "closed")
        L.append(f"| {i} | {b['trader']} | {b['trades']} | {b['win']:.0%} | {pc(b['mean'])} | {f2(b['net'])} | {f2(b['ex_best'])} | {b['maxdd']:.2f} | "
                 f"{'/'.join(f'{x*100:.0f}%' for x in mc) if mc else '-'} | {b['score']['nights_profitable']}/{b['score']['nights']} | "
                 f"{b['oos_n']} / {pc(b['oos_mean'])} | {b['score']['score_total']} | {f2(b['net3'])} | {sk} |")
    for b in board:
        s = b["score"]
        L += ["", f"### {b['trader']}", "",
              f"- Scores: OOS risk {s['sc_oos_risk']}, drawdown {s['sc_drawdown']}, trades {s['sc_trades']}, edge {s['sc_edge']}, stability {s['sc_stability']} = **{s['score_total']}/25**"
              f"{' (CANDIDATE)' if s['score_total'] >= 18 and b['trades'] >= 50 and (b['oos_mean'] or 0) > 0 else ' (not a candidate)'}.",
              "- Walk-forward by night (Dublin): " + ", ".join(f"{k[5:]} {v:+.1f}" for k, v in sorted(b["nights"].items())),
              f"- WHY THIS COULD FAIL: {WHY['common']}" + (f" Without the single best trade P&L is {f2(b['ex_best'])} -> one lottery ticket." if b["ex_best"] < 0 < b["net"] else "") +
              (f" Only {b['trades']} trades." if b["trades"] < 50 else "") +
              (f" Crowding: {(lb.get(b['trader'], {}).get('30d') or lb.get(b['trader'], {}).get('7d') or {}).get('copiers')} copyfomo copiers race the same buys." if b["trader"] in lb else ""),
              f"- Who is on the other side: {WHY['other']}"]
    # ---------- stake test ----------
    top = [b for b in board][:S["top_n"]]
    allc = [(b["trader"], r) for b in top for r in b["cl"]]
    nights_ = {}
    for tr, r in allc: nights_.setdefault(night_of(r["t"]), []).append((tr, r))
    def night_eval(items, stake):
        ev = sorted([(r["t"], 1, r) for _, r in items] + [(r["t_exit"], -1, r) for _, r in items], key=lambda x: (x[0], x[1]))
        cur = mx = 0; real = mn = 0.0
        for t, k, r in ev:
            if k == 1: cur += 1; mx = max(mx, cur)
            else: cur -= 1; real += r["ret"] * stake; mn = min(mn, real)
        return mx, mx * stake, real, mn
    lim = S["balance"] * S["night_limit"]
    L += ["", "## Stake-size test", "",
          f"Balance ${S['balance']:.0f}, nightly loss limit {S['night_limit']:.0%} = ${lim:.2f}, per-trade cap {S['trade_cap']:.0%} = ${S['balance']*S['trade_cap']:.2f}. "
          f"Traders available: {len(top)} of the approved 5 ({', '.join(b['trader'] for b in top)}). Copies = simulated trades above (10 s delay, all filters).", "",
          "Historical nights (all available traders together):", "",
          "| stake | nights | max open at once | worst-night exposure $ | worst-night realised $ | worst intra-night running loss $ | nights hitting limit |", "|---|---|---|---|---|---|---|"]
    for stake in S["stakes"]:
        e = [night_eval(v, stake) for v in nights_.values()]
        if not e: break
        L.append(f"| ${stake:.2f} | {len(e)} | {max(x[0] for x in e)} | {max(x[1] for x in e):.2f} | {min(x[2] for x in e):+.2f} | {min(x[3] for x in e):+.2f} | {sum(x[3] <= -lim for x in e)} |")
    # Monte Carlo: (A) joint calendar nights; (B) 5 traders all firing: 5 trader-nights drawn from the pool, aligned by time of day
    tn = {}
    for tr, r in allc: tn.setdefault((tr, night_of(r["t"])), []).append(r)
    pool = list(tn.values()); cal = list(nights_.values()); rnd = random.Random(11); N = 10000
    def shift(rs):          # align to a common night by time of day (Dublin-ish: seconds since 12:00 UTC)
        o = []
        for r in rs:
            st = (r["t"] - 12 * 3600) % 86400; o.append({**r, "t": st, "t_exit": st + ((r["t_exit"] or r["t"]) - r["t"])})
        return o
    L += ["", f"Monte Carlo over nights ({N:,} draws): A = random historical night with whichever traders traded; "
          "B = all 5 fire the same night (5 trader-nights drawn from the available traders' active nights, aligned by time of day; "
          "assumes the 3 missing traders behave like these and are independent).", "",
          "| stake | A: P(hit $%.2f limit) | A: p95 night loss $ | B: P(hit limit) | B: p95 night loss $ | B: median max open | B: p95 max open | B: p95 exposure $ |" % lim,
          "|---|---|---|---|---|---|---|---|"]
    mcB = {}
    for stake in S["stakes"]:
        if not pool: break
        A = [night_eval(rnd.choice(cal), stake) for _ in range(N)]
        B = []
        for _ in range(N):
            its = []
            for k in range(S["top_n"]): its += [("x", r) for r in shift(rnd.choice(pool))]
            B.append(night_eval(its, stake))
        q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
        pa, pb = sum(x[3] <= -lim for x in A) / N, sum(x[3] <= -lim for x in B) / N; mcB[stake] = pb
        L.append(f"| ${stake:.2f} | {pa:.1%} | {-q([x[3] for x in A], 0.05):.2f} | {pb:.1%} | {-q([x[3] for x in B], 0.05):.2f} | "
                 f"{q([x[0] for x in B], 0.5)} | {q([x[0] for x in B], 0.95)} | {q([x[1] for x in B], 0.95):.2f} |")
    ok = [s for s in S["stakes"] if mcB.get(s, 1) <= 0.05]
    rec = max(ok) if ok else min(S["stakes"])
    L += ["", f"**Stake recommendation (proposal): ${rec:.2f}** = the largest tested stake whose probability of hitting the ${lim:.2f} nightly limit "
          f"is <= 5% when all 5 traders fire (B: {mcB.get(rec, 0):.1%}; A, these 2 traders only: see table)" + ("" if ok else " -- NONE of the tested stakes met 5%; smallest tested shown") +
          f". All tested stakes are under the ${S['balance']*S['trade_cap']:.2f} per-trade cap. Hitting the limit is counted on the running "
          "realised loss within the night (stop-outs land before winners close)."]
    # ---------- model band (central vs conservative) ----------
    cons = band(trs, split, MODELS["conservative"])
    pc5 = p_limit_all5([cons[b["trader"]]["cl"] for b in top], S["stakes"])
    ok_c = [x for x in S["stakes"] if pc5[x] <= 0.05]
    L += ["", "## Model band (one real fill, so a conservative band is kept)", "",
          "CENTRAL (headline above) = fit to the real TRUTH copy: stop fills 2.5% below the -25% trigger, copyfomo 2%/side, $0.03 gas per round trip. "
          "CONSERVATIVE = stop fills 5% below the trigger and never better than a crash candle's close (the previous model).", "",
          "| trader | central net $ | conservative net $ | central ex-best $ | conservative ex-best $ | central score | conservative score |", "|---|---|---|---|---|---|---|"]
    for b in board:
        c_ = cons[b["trader"]]
        L.append(f"| {b['trader']} | {f2(b['net'])} | {f2(c_['net'])} | {f2(b['ex_best'])} | {f2(c_['ex_best'])} | {b['score']['score_total']} | {c_['score']} |")
    cov = coverage(); mp = load_json(os.path.join(OI, "data/leader_mappings.json"), {}) or {}
    STATUS = {"_benjitrades": "live copy, $6 probation", "ExactTallTakin": "ended (Zero)"}
    L += ["", "## Versus the ~5% round-trip cost drag (record only; Zero: no new copy leaders for now)", "",
          "Leader mean = the leader's own return on the coins we would copy (before our costs). Copy mean = our simulated return per copy after "
          "all costs (central / conservative). To beat the drag, copy mean must be > 0 with the 95% lower bound > 0.", "",
          "| trader | status | mapping conf. | swap coverage (UTC) | copies | leader mean | copy mean central / cons. | copy median | 95% low (central) | net $ central / cons. | beats drag? |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in board:
        c_ = cons[b["trader"]]; lm = [r["tr"]["ret"] for r in b["cl"]]
        cv = cov.get(b["trader"]); full = cv and cv[0] <= "2026-09-26"
        verdict = "yes" if (b["mean"] or -1) > 0 and (b["ci_lo"] or -1) > 0 else ("no (too few copies)" if b["trades"] < 30 else "no")
        L.append(f"| {b['trader']} | {STATUS.get(b['trader'], 'record only')} | {(mp.get(b['trader']) or {}).get('confidence', '?')} | "
                 f"{(cv[0][5:10] + ' to ' + cv[1][5:10]) if cv else '-'}{'' if full else ' PARTIAL'} | {b['trades']} | "
                 f"{pc(statistics.fmean(lm)) if lm else '-'} | {pc(b['mean'])} / {pc(c_['mean'])} | {pc(statistics.median([r['ret'] for r in b['cl']])) if b['cl'] else '-'} | {pc(b['ci_lo'])} | {f2(b['net'])} / {f2(c_['net'])} | {verdict} |")
    L += ["", "Excluded: cosby, zelda89, Altcoinist (Scout: the mappings look wrong). PARTIAL = Scout's fetch cap: bystevenr from Oct 8, pointfarmcap "
          "from Oct 16. Means are carried by 1-3 lottery coins (e.g. bystevenr's best copy is +3,300% from a +7,007% leader round, unverified); "
          "the median copy loses money for everyone except pointfarmcap (8 copies, 6 days). Leader return uses Scout's USD sizes, so a coin still "
          "partly held reads as a loss and any token received off-swap inflates the sell side. Every mapping except ExactTallTakin (medium) and pointfarmcap (medium-low) is LOW confidence: the history may not be the leader's."]
    L += ["", "P(hit the nightly limit) when all 5 fire, conservative model: " + ", ".join(f"${x:.2f} {pc5[x]:.1%}" for x in S["stakes"]) +
          f". Largest stake <= 5%: {'$%.2f' % max(ok_c) if ok_c else 'none tested'}."]
    # ---------- TRUTH calibration ----------
    L += ["", "## Calibration: TRUTH (_benjitrades, real copyfomo copy)", ""]
    cal_f = os.path.join(CT, "truth_1m.json"); pool_truth = "GUkDEvSyoJJ5yFHUYKuePjwTTAZYLBmWsHQ2fYaCMKYm"
    if not os.path.exists(cal_f) and "--no-network" not in sys.argv:
        j = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_truth}/ohlcv/minute?aggregate=1&limit=60"
                     f"&currency=usd&token=base&before_timestamp={int(ts_of('2026-10-23T21:05:00Z'))}", 6.5)
        try: atomic_write(cal_f, json.dumps(sorted([[int(x[0])] + [float(v) for v in x[1:6]] for x in j["data"]["attributes"]["ohlcv_list"]])))
        except Exception: pass
    c = load_json(cal_f, []) or []
    L += ["Real (Copycat): buy $9.40 (no fill price shown); stop message 'all @ $0.000293, pnl $-2.78 (-29.5%)'; /copies realised -$2.81 (-29.9%). "
          "Bot times UTC-4: notice 20:42 UTC, stop 20:47 UTC. The bot's % = USD P&L / dollars in.", ""]
    if c:
        t0, lead = ts_of("2026-10-23T20:42:00Z"), 0.000442
        L += ["| delay | our chart fill | chase vs leader | central model | conservative model |", "|---|---|---|---|---|"]
        for d in (3, 10, 30):
            p_e = price_at(c, t0 + d)
            if not p_e: continue
            row = []
            for mname in ("central", "conservative"):
                old = {k: S[k] for k in MODELS[mname]}; S.update(MODELS[mname])
                tr = {"mint": "x", "t": t0, "usd": 259.18, "ret": 0.0, "t_exit": t0 + 3600, "lf": lead}
                entry = p_e * (1 + slip(S["stake"])); sl_px = entry * (1 + S["sl"]); res_ = None
                for x in c:
                    if x[0] + 60 <= t0 + d: continue
                    first = x[0] <= t0 + d; lo = x[4] if first else x[3]
                    if lo <= sl_px:
                        px = x[1] * (1 - S["sl_slip"]) if (not first and x[1] <= sl_px) else sl_px * (1 - S["sl_slip"])
                        if S["crash_close"] and x[4] < sl_px: px = min(px, x[4])
                        fx = S["fixed"] / S["stake"]
                        res_ = (px, ((1 - S["fee"]) - fx) * px * (1 - slip(S["stake"])) / entry * (1 - S["fee"]) - fx - 1); break
                S.update(old); row.append(f"exit ${res_[0]:.6f}, {res_[1]:+.1%}" if res_ else "stop not hit")
            L.append(f"| {d}s | ${p_e:.6f} (${p_e*1e9/1e3:.0f}k) | {p_e/lead-1:+.1%} | {row[0]} | {row[1]} |")
        L += ["", "Reconciliation (Zero's question 1):",
              "- If all $9.40 bought tokens and $0.000293 was the fill, -29.9% implies entry $0.000418 ($418k mcap), or $0.000400 if copyfomo's 2%/side "
              "is inside the P&L. The 20:42 UTC 1-min candle never traded below $0.000445 (open $0.000445, low $0.000445), and a 3-10 s copy lands at "
              "$0.000449-0.000459. So that reading needs an entry 6-13% below every chart print that minute.",
              "- SOL/USD 20:42 -> 20:47 UTC: $103.76 -> $103.54 (-0.2%). Too small, and SOL falling would make a USD loss worse, not better.",
              "- '$9.40 includes fees/priority before the token' goes the wrong way too: fewer tokens means a bigger loss at the same exit price.",
              "- Most likely: entry matched the chart (~$0.000449-0.000459), the stop filled near its trigger (~$0.00033, 2-3% below the -25% line, "
              "partway down the 20:46 crash), and copyfomo's published 2%/side is inside the -$2.78. Math: 0.75 x 0.975 x 0.98 x 0.98 = -29.9%. "
              "The '@ $0.000293' would then be a reference price: it equals the 20:46 close / 20:47 open, i.e. the price when the message was built. "
              "That fits the docs: /portfolio prices are 'what each token would fetch if you sold it right now'. The extra $0.03 in /copies = gas billed back "
              "(per DefiLlama's adapter: '2% service fee plus the gas copyfomo fronts, billed back as one stablecoin transfer').",
              "- Uncertainty: n=1, and no fill price was shown. The alternative (the leader actually bought in the 20:41 candle, which ranged "
              "$0.000239-0.000578, and our copy filled ~$0.000415 in a dip) can't be excluded. Benji's mapped wallet 9PB1...C3sc has no transaction "
              "after 19:44:58 UTC (public RPC), so we can't see the leader's own TRUTH swap. That also means this buy came from a wallet Scout "
              "doesn't have. Fastest check: /portfolio -> trade history shows 'the market cap you entered and exited at'. Entry ~$450k = most likely; "
              "~$415k = the alternative.",
              "- So no: the real stop cost was about -30% all-in, not -38 to -40%. The old model double-counted: 5 pts of stop slip PLUS 2%/side "
              "PLUS the crash-close rule. Central is now about -30.5% at 10 s (real -29.9%). The old rule is kept as the conservative band."]
    else:
        L.append("- 1-min TRUTH candles not available (no network this run).")
    # ---------- all-in cost per round trip ----------
    L += ["", "## copyfomo all-in cost per round trip (Zero's question 3)", "",
          "Sources: copyfomo's docs give no fee number. Third-party fee page (degenbench) and DefiLlama's copyfomo adapter: 2% service fee on every buy and every sell "
          "(1.8% with a referral), plus the gas copyfomo fronts, billed back in stablecoin. Rent for token accounts is paid by copyfomo's fee payer and netted "
          "when the account closes. The '$0.95 minimum' on copyfomo.io is FOMO's own swap fee per an unverified review, and our real copy shows no such charge.",
          "Assumptions: PumpSwap pool fee ~0.30%/side, possibly up to ~1.25% on low-mcap tiers; it's inside the fill price, so it shows up as slippage vs the chart. "
          "USDC->SOL hop ~0.05%/side. Impact = 2 x stake / $20k pool. Fixed: $0.03/round trip observed (TRUTH: -$2.81 vs -$2.78). Pessimistic: $0.25 (busy-launch priority/tips, "
          "or ~0.002 SOL ATA rent ~= $0.21 at $104/SOL if ever not refunded).", "",
          "| stake | service 2x2% | pool+route (0.35-1.3%/side) | impact | fixed (obs. $0.03) | fixed as % of stake (obs. / pess. $0.25) | all-in round trip (central / pessimistic) |",
          "|---|---|---|---|---|---|---|"]
    for st_ in (4.0, 6.0, 9.40):
        imp = 2 * S["impact"] * st_ / S["liq"]
        cen = 0.04 + 0.007 + imp + 0.03 / st_; pes = 0.04 + 0.026 + imp + 0.25 / st_
        L.append(f"| ${st_:.2f} | 4.0% | 0.7-2.6% | {imp:.2%} | ${0.03:.2f} | {0.03/st_:.2%} / {0.25/st_:.2%} | {cen:.1%} / {pes:.1%} |")
    L += ["", "Verdict: costs are mostly percentage-based, about 4.7% + impact per round trip. The fixed part is 0.75% of a $4 ticket "
          "vs 0.32% of $9.40 (pessimistic: 6.3% vs 2.7%). On cost alone, small tickets are still fine: $4 costs ~0.4 pt more than $9.40 at the observed $0.03. "
          "The real hurdle is the ~5% round-trip drag vs the leaders' simulated mean return per copy (see ranking). Ticket size doesn't fix that.",
          "Settings note (copyfomo backup in skips-log.csv): 'leader sells at a loss: sell with them'. Exits otherwise mirror the leader, "
          "with SL -25% kept after TP. That matches this model."]
    L += ["", "## Missing inputs", "", "- Scout /workspace/onchain-intel/leader-rank.md (the shortlist of up to 5)." if not os.path.exists(lr) else None,
          "- Copycat /workspace/copyfomo/leaderboard-2026-10-23.md." if not cb else None,
          f"- Per-swap history (Scout) for leaderboard traders with a known wallet: {', '.join(h for h in lb if h in wal and h not in traders) or 'none'}.",
          f"- No wallet mapping at all (cannot simulate until someone pairs handle -> wallet): {', '.join(h for h in lb if h not in wal) or 'none'}.",
          "- 1-min candles for most leader trades (copytests.py fetches ~8 per pipeline run, newest first)."]
    p = os.path.join(LAB, "out/copy_candidates.md"); atomic_write(p, "\n".join(l for l in L if l is not None) + "\n")
    with open(p.replace(".md", ".csv") + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["rank", "trader", "trades", "win_rate", "net_usd", "net_ex_best_usd", "max_dd_usd", "mc_dd_p5", "mc_dd_p50", "mc_dd_p95",
                                        "nights", "nights_profitable", "score_total", "path_trades"])
        for i, b in enumerate(board, 1):
            w.writerow([i, b["trader"], b["trades"], round(b["win"], 3), round(b["net"], 2), round(b["ex_best"], 2), round(b["maxdd"], 2),
                        *([round(x, 3) for x in b["mc"]] if b["mc"] else ["", "", ""]), b["score"]["nights"], b["score"]["nights_profitable"],
                        b["score"]["score_total"], b["path"]])
    os.replace(p.replace(".md", ".csv") + ".tmp", p.replace(".md", ".csv"))
    open(sp, "w").write(sig); print(f"copy_candidates: {len(board)} traders -> {p}")

if __name__ == "__main__":
    main()
