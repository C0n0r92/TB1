"""Copyfomo trader-swap simulation on Scout's trader_trades.csv (PAPER ONLY, no network).
Rules: each Monday 00:00 UTC rank traders by their TRAILING 7-day closed-round P&L (point-in-time: only rounds sold
before the ranking time). Follow the top trader's NEW buys, exit when they exit (their sell_at), our return =
their pnl_pct worsened by copy lag, slippage and 2%/side fees. After N consecutive losing copies, demote to the next-
ranked trader until the next weekly ranking. Fixed-trader baselines follow one trader all the time.
Size: 0.25x the leader's buy, capped at stake_cap of equity (default 15% of $100 = $15); P&L reported in $.
Caveat: the source's "$52 -> $4,939 in 24h" is marketing; leaders' own pnl_pct is taken as the gross move."""
import datetime as dt
from labcore import iso
import sources

def variant_defs(cfg):
    Q = cfg.get("copytrade", {})
    base = {"source": "trader_trades", "min_score": 0, "size_x": 0.25, "lag": Q.get("assumed_lag", 0.05),
            "liq": Q.get("assumed_liq_usd", 20000), "warmup_d": 7, "stop": Q.get("stop", -0.25), "stop_slip": Q.get("stop_slip", 0.05)}
    vs = [{**base, "name": "COPYSWAP_top_demote2", "mode": "swap", "demote_after": 2},
          {**base, "name": "COPYSWAP_top_demote3", "mode": "swap", "demote_after": 3},
          {**base, "name": "COPYSWAP_top_nodemote", "mode": "swap", "demote_after": 0}]
    for tr in Q.get("fixed_traders", ["ExactTallTakin", "_benjitrades"]):
        vs.append({**base, "name": f"COPYFIXED_{tr}", "mode": "fixed", "trader": tr, "demote_after": 0})
    vs.append({**base, "name": "COPYSWAP_demote2_lag0", "mode": "swap", "demote_after": 2, "lag": 0.0})
    vs.append({**base, "name": "COPYSWAP_demote2_lag15", "mode": "swap", "demote_after": 2, "lag": 0.15})
    d = cfg.get("defaults", {})
    return [{**d, **v} for v in vs]

def _monday(t):
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc); m = (d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return m.timestamp()

def run(cfg, V, split):
    from backtest import slip
    C = cfg["costs"]; fee, fx, eq = C["fee_per_side"], C["fixed_cost_usd"], C["start_equity_usd"]
    tt = sources.trader_trades(cfg)
    if not tt: return []
    traders = sorted({r["trader"] for r in tt}); t_first = min(r["t"] for r in tt)
    start = _monday(t_first) + 7 * 86400 if V["warmup_d"] else t_first     # first full week with trailing data
    ts = sorted(r["t"] for r in tt if r["t"] >= start)
    split = ts[int(len(ts) * (1 - cfg["sim"]["holdout_fraction"]))] if ts else None   # own time split (latest 40% = OOS)
    def ranking(at):
        sc = {tr: sum(r["ret"] for r in tt if r["trader"] == tr and at - 7 * 86400 <= r["t_exit"] < at) for tr in traders}
        return sorted(traders, key=lambda tr: -sc[tr])
    out, open_exits, cur, rank, week, losses = [], [], None, None, None, 0
    for r in sorted(tt, key=lambda r: r["t"]):
        if r["t"] < start: continue
        if V["mode"] == "swap":
            w = _monday(r["t"])
            if w != week: week, rank, losses = w, ranking(w), 0; cur = rank[0]
            # demotions decided by copies that CLOSED before this buy (point-in-time)
            if V["demote_after"]:
                done = [x for x in out if x["status"] == "closed" and x["trader"] == cur and x["exit_t"] <= r["t"] and x["t"] >= week]
                streak = 0
                for x in sorted(done, key=lambda x: x["exit_t"]):
                    streak = streak + 1 if x["pnl"] < 0 else 0
                if streak >= V["demote_after"]:
                    cur = rank[(rank.index(cur) + 1) % len(rank)]; rank = rank[rank.index(cur):] + rank[:rank.index(cur)]
            if r["trader"] != cur: continue
        elif r["trader"] != V["trader"]: continue
        bet = min(V["size_x"] * (r["buy_usd"] or 0) or C["bet_usd"], V.get("stake_cap", 0.15) * eq)
        open_exits = [x for x in open_exits if x > r["t"]]
        st = "closed"
        if len(open_exits) >= cfg["sim"]["max_open"]: st = "skip"
        else: open_exits.append(r["t_exit"])
        s = slip(cfg, V["liq"], bet)
        gross = (1 + r["ret"]) / (1 + V["lag"])
        # copyfomo -25% stop with ~5 pts extra stop slippage (TRUTH filled -29.5%); no price path here, so assume a leader
        # round trip worse than the stop means we stopped out first; rugs (<= -80%) gap through -> keep the leader's crash.
        stp, ss = V.get("stop", -0.25), V.get("stop_slip", 0.05)
        if stp is not None and gross - 1 < stp and r["ret"] > -0.8: gross = 1 + stp - ss
        cash = (bet * (1 - fee) - fx) * (1 - s) / (1 + s) * gross * (1 - fee) - fx     # buy slip + sell slip ~ symmetric
        cash = max(cash, 0.0); pnl = cash - bet
        t = {"status": st, "t": r["t"], "t_entry": r["t"], "exit_t": r["t_exit"], "pnl": pnl if st == "closed" else 0,
             "ret": pnl / bet, "bet": bet, "rug": r["ret"] <= -0.8, "trader": r["trader"], "is_oos": split is not None and r["t"] >= split,
             "e": {"t": r["t"], "token": r["mint"], "src": "trader_trades", "symbol": r["trader"]}}
        t["row"] = {"signal_ts": iso(r["t"]), "symbol": r["trader"], "status": st, "why_skipped": "max_open" if st == "skip" else "",
                    "entry_ts": iso(r["t"]), "exit_ts": iso(r["t_exit"]), "exit": "leader exit", "pnl_usd": round(pnl, 2),
                    "ret": round(pnl / bet, 3), "rug": int(t["rug"]), "sample": "out" if t["is_oos"] else "in", "token": r["mint"] or "",
                    "src": "trader_trades"}
        out.append(t)
    return out
