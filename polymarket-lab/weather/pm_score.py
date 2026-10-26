"""Lab METHOD.md rubric for Polymarket paper tracks. Trades: dicts with keys t_entry (iso), day, cost, pnl, ret, sample('in'/'out')."""
import math, random, statistics as S, csv, os, json

def bootstrap_ci(xs, n=2000, seed=7):
    if len(xs) < 2: return (float("nan"), float("nan"))
    rnd = random.Random(seed); ms = sorted(S.fmean(rnd.choices(xs, k=len(xs))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]

def max_dd(pnls, equity0=100.0):
    eq = peak = equity0; dd = 0.0
    for p in pnls:
        eq += p; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak if peak > 0 else 1)
    return dd

def mc_dd(pnls, runs=1000, seed=11):
    if not pnls: return (0, 0, 0)
    rnd = random.Random(seed); d = []
    for _ in range(runs):
        x = pnls[:]; rnd.shuffle(x); d.append(max_dd(x))
    d.sort(); return d[int(.05 * runs)], d[int(.5 * runs)], d[min(runs - 1, int(.95 * runs))]

def holdout_split(trades, frac=0.4):
    ts = sorted(t["t_entry"] for t in trades)
    if not ts: return None
    cut = ts[int(len(ts) * (1 - frac))] if len(ts) > 1 else ts[0]
    for t in trades: t["sample"] = "out" if t["t_entry"] >= cut else "in"
    return cut

def score(trades, min_oos=20):
    closed = [t for t in trades if t.get("pnl") is not None]
    rets = [t["ret"] for t in closed]; pnls = [t["pnl"] for t in sorted(closed, key=lambda t: t["t_entry"])]
    ins = [t for t in closed if t["sample"] == "in"]; outs = [t for t in closed if t["sample"] == "out"]
    o_r = [t["ret"] for t in outs]
    mean = S.fmean(rets) if rets else 0; lo, hi = bootstrap_ci(rets)
    # sc_oos_risk
    if len(o_r) < 2 or S.fmean(o_r) <= 0: s1 = 1
    else:
        q = S.fmean(o_r) / (S.pstdev(o_r) or 1e-9); s1 = 2 if q < .1 else 3 if q < .2 else 4 if q < .35 else 5
    p5, p50, p95 = mc_dd(pnls)
    s2 = 1 if p95 > .5 else 2 if p95 > .3 else 3 if p95 > .2 else 4 if p95 > .1 else 5
    n = len(closed); s3 = 1 if n < 10 else 2 if n < 25 else 3 if n < 50 else 4 if n < 100 else 5
    s4 = 1 if mean <= -.05 else 2 if mean <= 0 else 3 if mean <= .05 else 4
    if n >= 2 and lo > 0: s4 = 5
    days = {}
    for t in closed: days[t["day"]] = days.get(t["day"], 0) + t["pnl"]
    nd = len(days); npos = sum(v > 0 for v in days.values()); sh = npos / nd if nd else 0
    s5 = 1 if nd < 3 else (1 if sh < .3 else 2 if sh < .5 else 3 if sh < .6 else 4 if sh < .8 else 5)
    tot = s1 + s2 + s3 + s4 + s5
    o_lo, _ = bootstrap_ci(o_r)
    in_p = sum(t["pnl"] for t in ins); out_p = sum(t["pnl"] for t in outs)
    if len(outs) < min_oos: holds = f"insufficient (n_out={len(outs)}<{min_oos})"
    else: holds = "yes" if (in_p > 0 and S.fmean(o_r) > 0 and o_lo > 0) else "no"
    wins = sum(t["pnl"] > 0 for t in closed)
    return {"trades": n, "win_rate": round(wins / n, 3) if n else "", "net_profit_after_costs": round(sum(pnls), 2),
            "max_drawdown": round(max_dd(pnls) * 100, 2), "holds_out_of_sample": holds, "n_in_sample": len(ins), "n_out_of_sample": len(outs),
            "mean_ret": round(mean, 3) if n else "", "median_ret": round(S.median(rets), 3) if n else "",
            "ci95_mean_ret": f"[{lo:+.2f},{hi:+.2f}]" if n > 1 else "", "oos_mean_ret": round(S.fmean(o_r), 3) if o_r else "",
            "in_net_pnl": round(in_p, 2), "out_net_pnl": round(out_p, 2),
            "sc_oos_risk": s1, "sc_drawdown": s2, "sc_trades": s3, "sc_edge": s4, "sc_stability": s5, "score_total": tot,
            "net_ex_best_trade": round(sum(pnls) - max(pnls), 2) if pnls else "", "mc_dd_p5": round(p5, 3), "mc_dd_p50": round(p50, 3),
            "mc_dd_p95": round(p95, 3), "nights": nd, "nights_profitable": npos,
            "candidate": "yes" if (tot >= 18 and n >= 50 and holds == "yes") else "no"}

def lucky(results):
    """results: list of (param, score_dict) sorted by param. yes if a profitable setting has an unprofitable neighbour."""
    flags = {}
    for i, (p, s) in enumerate(results):
        if not s["trades"]: flags[p] = "n/a"; continue
        nb = [results[j][1] for j in (i - 1, i + 1) if 0 <= j < len(results)]
        flags[p] = "yes" if s["net_profit_after_costs"] > 0 and any(x["net_profit_after_costs"] <= 0 for x in nb) else ("no" if s["net_profit_after_costs"] > 0 else "untested")
    return flags

LB = "/workspace/polymarket-lab/data/lab_style_leaderboard.csv"
def upsert_leaderboard(rows, prefix):
    """Replace rows whose variant starts with prefix; keep existing header/columns untouched (extra keys dropped)."""
    if not os.path.exists(LB): return
    with open(LB) as fh:
        rd = csv.DictReader(fh); cols = rd.fieldnames; old = [r for r in rd if not r["variant"].startswith(prefix)]
    with open(LB + ".pmtmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(old)
        for r in rows: w.writerow({c: r.get(c, "") for c in cols})
    os.replace(LB + ".pmtmp", LB)
    # also persist so backtest.py's full rewrite can re-merge them
    extra = os.path.join("/workspace/polymarket-lab/data", f"leaderboard_extra_{prefix.strip('_')}.json")
    with open(extra, "w") as fh: json.dump(rows, fh)
