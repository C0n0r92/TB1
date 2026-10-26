#!/usr/bin/env python3
"""Confluence (CL_) simulator, PAPER ONLY. Reads data/cl/events.json + data/cl/candles/*.json (cache only, no network).
Writes out/cl_trades.csv, out/cl_results.json, out/.cl_rows.json (staging for merge_extra.py CL)."""
import json, os, glob, random, statistics as S, datetime as dt, csv, math
from zoneinfo import ZoneInfo
import scoring
from labcore import night_of
LAB = os.path.dirname(os.path.abspath(__file__)); CL = os.path.join(LAB, "data", "cl"); OUT = os.path.join(LAB, "out")
DUB = ZoneInfo("Europe/Dublin")
DEFAULT = dict(sl=0.25, tp=0.50, hold_m=120, delay_s=10, cost_pump=0.047, cost_big=0.02, ladder=False)
STAKE, EQUITY = 5.0, 100.0

def load_series():
    C = {}
    for f in glob.glob(os.path.join(CL, "candles", "*.json")):
        d = json.load(open(f)); rows = []; cut = 0
        for s in d.get("series", []):
            rs = [r for r in s["rows"] if r[0] >= cut and r[4] and r[4] > 0]
            if rows and rs: rs = [r for r in rs if r[0] > rows[-1][0]]
            rows += rs
            if rs: cut = rs[-1][0]
        pump = d["mint"].endswith("pump") or any(s["dex"] in ("pump-fun", "pumpfun", "pumpswap") for s in d.get("series", []))
        sup = 1e9 if pump else None
        if not pump:
            for p in d.get("pools", []):
                try:
                    if p.get("fdv") and p.get("price"): sup = float(p["fdv"]) / float(p["price"]); break
                except (TypeError, ValueError, ZeroDivisionError): pass
        C[d["mint"]] = dict(rows=rows, supply=sup, status=d["status"])
    return C

def flat_time(t):
    d = dt.datetime.fromtimestamp(t, DUB); f = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if f <= d: f += dt.timedelta(days=1)
    return f.timestamp()

def entry_at(rows, t):
    m = int(t // 60 * 60)
    for i, r in enumerate(rows):
        if r[0] == m: return i, r[4], r[0] + 60
        if r[0] > m:
            return (i, r[1], r[0]) if r[0] - t <= 600 else (None, None, None)
    return None, None, None

def sim(cs, t_sig, cfg):
    rows = cs["rows"]; i, px, t_in = entry_at(rows, t_sig + cfg["delay_s"])
    if i is None or not px: return None
    mcap = px * cs["supply"] if cs["supply"] else None
    cost = cfg["cost_big"] if (mcap and mcap >= 1e6) else cfg["cost_pump"]
    stop = px * (1 - cfg["sl"]); tp = px * (1 + cfg["tp"]) if cfg["tp"] else None
    t_end = min(t_in + cfg["hold_m"] * 60, flat_time(t_in), t_sig + 12 * 3600)
    exit_px = None; why = "time"; last = px; part = 0.0; peak = px; frac = 1.0; trail = None
    for r in rows[i + 1:]:
        if r[0] >= t_end: break
        o, h, l, c = r[1], r[2], r[3], r[4]
        st = max(stop, trail) if trail else stop
        if l <= st:
            f = o if o <= st else (c if c <= st else st)
            exit_px = f; why = "stop" if not trail or st == stop else "trail"; break
        if tp and h >= tp and not trail:
            if cfg["ladder"]:
                part += 0.5 * (tp / px); frac = 0.5; trail = tp * (1 - cfg["ladder"]); peak = h
            else: exit_px = tp; why = "tp"; break
        if trail:
            peak = max(peak, h); trail = max(trail, peak * (1 - cfg["ladder"]))
        last = c
    if exit_px is None: exit_px = last
    gross = part + frac * exit_px / px
    ret = gross - 1 - cost
    rug = exit_px <= 0.2 * px
    if rug: ret = min(ret, -0.9)
    return dict(t=t_sig, t_in=t_in, entry=px, mcap=mcap, cost=cost, ret=ret, why=why, rug=rug)

def boot(x, it=5000, seed=7):
    if len(x) < 2: return (None, None)
    r = random.Random(seed); ms = sorted(S.fmean(r.choices(x, k=len(x))) for _ in range(it))
    return ms[int(0.025 * it)], ms[int(0.975 * it)]

def stats(trades, hold_t=None):
    x = [t["ret"] for t in trades]
    if not x: return dict(trades=0)
    ts = sorted(t["t"] for t in trades); ho = hold_t if hold_t else ts[int(0.6 * (len(ts) - 1))] if len(ts) > 1 else ts[0]
    for t in trades: t["is_oos"] = t["t"] > ho
    oos = [t["ret"] for t in trades if t["is_oos"]]; ins = [t["ret"] for t in trades if not t["is_oos"]]
    lo, hi = boot(x); olo, ohi = boot(oos)
    pn = [r * STAKE for r in x]
    best = max(pn)
    return dict(trades=len(x), mean_ret=S.fmean(x), median_ret=S.median(x), ci_lo=lo, ci_hi=hi, win_rate=sum(r > 0 for r in x) / len(x),
                n_in=len(ins), n_out=len(oos), oos_mean=S.fmean(oos) if oos else None, oos_ci=(olo, ohi),
                in_pnl=sum(ins) * STAKE, out_pnl=sum(oos) * STAKE, net=sum(pn), net_ex_best=sum(pn) - best,
                rug_rate=sum(t["rug"] for t in trades) / len(x), holdout_after=ho)

def run(events, C, cfg, key="t"):
    out = []
    for e in events:
        cs = C.get(e["mint"])
        if not cs or not cs["rows"]: continue
        r = sim(cs, e[key], cfg)
        if r: r.update(mint=e["mint"], n_w=len(e.get("wallets", []))); out.append(r)
    return out

def controls(events, C, cfg, nrand=40, seed=3):
    """same token random time (+-4h, not within 5 min of signal); same time other tokens."""
    rnd = random.Random(seed); same_tok = []; same_time = []
    mints = [m for m, c in C.items() if c["rows"]]
    for e in events:
        cs = C.get(e["mint"])
        if not cs or not cs["rows"]: continue
        ts = [r[0] for r in cs["rows"] if abs(r[0] - e["t"]) <= 4 * 3600 and abs(r[0] - e["t"]) > 300]
        rs = []
        for _ in range(nrand):
            if not ts: break
            r = sim(cs, rnd.choice(ts) + rnd.random() * 60, cfg)
            if r: rs.append(r["ret"])
        if rs: same_tok.append(S.fmean(rs))
        oth = [m for m in mints if m != e["mint"] and any(abs(r[0] - e["t"]) <= 600 for r in C[m]["rows"])]
        rs = []
        for m in rnd.sample(oth, min(10, len(oth))):
            r = sim(C[m], e["t"], cfg)
            if r: rs.append(r["ret"])
        if rs: same_time.append(S.fmean(rs))
    f = lambda v: dict(n=len(v), mean=S.fmean(v) if v else None, ci=boot(v))
    return dict(same_token_random_time=f(same_tok), same_time_other_tokens=f(same_time))

def row(name, trades, st, family, note, lookahead):
    if not trades: return None
    mc = scoring.mc_drawdown([t["ret"] * STAKE for t in trades], EQUITY)
    closed = [dict(t=t["t"], pnl=t["ret"] * STAKE, ret=t["ret"], is_oos=t["is_oos"]) for t in trades]
    sc = scoring.score(dict(trades=st["trades"], mean_ret=st["mean_ret"], ci_lo=st["ci_lo"] if st["ci_lo"] is not None else -1), None, closed, mc)
    oos_ok = st["n_out"] >= 20 and st["in_pnl"] > 0 and (st["oos_mean"] or 0) > 0 and (st["oos_ci"][0] or -1) > 0
    hold = "yes" if oos_ok else (f"insufficient (n_out={st['n_out']}<20)" if st["n_out"] < 20 else "no")
    cand = "no (LOOKAHEAD)" if lookahead else ("yes" if sc["score_total"] >= 18 and st["trades"] >= 50 and hold == "yes" else "no")
    ci = f"[{st['ci_lo']:+.2f},{st['ci_hi']:+.2f}]" if st["ci_lo"] is not None else ""
    return dict(variant=name, trades=st["trades"], win_rate=round(st["win_rate"], 3), net_profit_after_costs=round(st["net"], 2),
                max_drawdown=round(mc[2] * EQUITY, 2) if mc else None, holds_out_of_sample=hold, n_in_sample=st["n_in"], n_out_of_sample=st["n_out"],
                mean_ret=round(st["mean_ret"], 4), median_ret=round(st["median_ret"], 4), ci95_mean_ret=ci, rug_rate=round(st["rug_rate"], 3),
                open=0, skipped=0, pending=0, no_candles=0, uncovered=0, filtered_out=0,
                oos_mean_ret=round(st["oos_mean"], 4) if st["oos_mean"] is not None else None,
                in_net_pnl=round(st["in_pnl"], 2), out_net_pnl=round(st["out_pnl"], 2), **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
                net_ex_best_trade=round(st["net_ex_best"], 2), mc_dd_p5=round(mc[0], 3), mc_dd_p50=round(mc[1], 3), mc_dd_p95=round(mc[2], 3),
                candidate=cand, lucky_number="", family=family, note=note)
