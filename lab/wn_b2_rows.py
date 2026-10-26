#!/usr/bin/env python3
"""PAPER ONLY. Leaderboard rows WN_B2_* for winners batch-2 (held-out WALLETS) replication: their entries with fixed exits
and the 16 trail exits (picked on batch 1). is_oos = last 30% of batch-2 trades by entry date. $5 stake, real cost
(4.7% <$1M approx mcap, else 2%), +2 pts on stop/trail exits (inherited from wn_b2.trail). -> out/leaderboard_extra_WN.json (appends/replaces WN_B2_)."""
import csv, json, os, glob, bisect, statistics as S, datetime as dt, importlib.util, sys, io, contextlib
from cl_sim import sim, boot, DEFAULT, OUT
from scoring import mc_drawdown, score, variants_tried
with contextlib.redirect_stdout(io.StringIO()):
    spec = importlib.util.spec_from_file_location("wnb2", "wn_b2.py"); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
fl, ts_ = M.fl, M.ts_
rs = sorted([r for r in M.W if r["wallet"][:4] not in M.B1], key=lambda r: r["entry_time"])
cut = ts_(rs[int(len(rs) * 0.7)]["entry_time"])
V = {"fixed_dflt_SL25TP50_2h": [], "fixed_quick_SL20TP30_30m": []}; V.update({f"trail{int(a*100)}_arm{int(c*100)}": [] for a, c in M.RULES})
for r in rs:
    t = ts_(r["entry_time"]); d = M.C.get((r["mint"], t))
    if not d or len(d["rows"]) < 10: continue
    rows = [x for x in d["rows"] if x[4] and x[4] > 0]
    if not rows or rows[0][0] > t or rows[-1][0] < t: continue
    m = fl(r["mcap_at_entry_usd_approx"]); cost = 0.02 if (m and m >= 1e6) else 0.047; cs = dict(rows=rows, supply=1e9)
    for k, cfg in (("fixed_dflt_SL25TP50_2h", DEFAULT), ("fixed_quick_SL20TP30_30m", dict(DEFAULT, sl=0.20, tp=0.30, hold_m=30))):
        s = sim(cs, t, dict(cfg, cost_pump=cost, cost_big=cost))
        if s: V[k].append(dict(t=t, ret=s["ret"], is_oos=t >= cut))
    for a, c in M.RULES:
        v = M.trail(rows, t, cost, a, c)
        if v is not None: V[f"trail{int(a*100)}_arm{int(c*100)}"].append(dict(t=t, ret=v, is_oos=t >= cut))
vt = variants_tried([dict(name=f"WN_B2_{k}", family="wn_b2", key=k) for k in V])
out = []
for k, tr in V.items():
    for x in tr: x["pnl"] = 5 * x["ret"]
    rets = [x["ret"] for x in tr]; oos = [x for x in tr if x["is_oos"]]; ci = boot(rets)
    st = dict(trades=len(tr), mean_ret=S.fmean(rets) if rets else None, ci_lo=ci[0] if ci else None)
    mc = mc_drawdown([x["pnl"] for x in tr], 100.0); sc = score(st, None, tr, mc)
    pn = [x["pnl"] for x in tr]; best = max(pn) if pn else 0
    eq = pk = dd = 0
    for p in pn: eq += p; pk = max(pk, eq); dd = max(dd, pk - eq)
    oosm = S.fmean([x["ret"] for x in oos]) if oos else None
    holds = "insufficient" if len(oos) < 20 else ("yes" if oosm > 0 else "no")
    cand = "yes" if sc["score_total"] >= 18 and len(tr) >= 50 and holds == "yes" else "no"
    out.append(dict(variant=f"WN_B2_{k}", trades=len(tr), win_rate=round(sum(r > 0 for r in rets) / len(rets), 3), net_profit_after_costs=round(sum(pn), 2),
        max_drawdown=round(dd, 2), holds_out_of_sample=f"{holds} (n_out={len(oos)})", n_in_sample=len(tr) - len(oos), n_out_of_sample=len(oos),
        mean_ret=round(st["mean_ret"], 4), median_ret=round(S.median(rets), 4), ci95_mean_ret=f"[{ci[0]:+.2f},{ci[1]:+.2f}]", oos_mean_ret=round(oosm, 4) if oosm is not None else None,
        in_net_pnl=round(sum(x["pnl"] for x in tr if not x["is_oos"]), 2), out_net_pnl=round(sum(x["pnl"] for x in oos), 2), net_ex_best_trade=round(sum(pn) - best, 2),
        mc_dd_p5=round(mc[0], 3), mc_dd_p50=round(mc[1], 3), mc_dd_p95=round(mc[2], 3), **sc, candidate=cand,
        lucky_number="n/a (picked on b1)" if k != "trail15_arm20" else "no (b1 pick)", family="wn_b2",
        note=f"winners batch-2 wallets (held out by wallet; exits picked on batch 1), {k}; OOS = b2 entries >= {dt.datetime.fromtimestamp(cut, dt.timezone.utc):%m-%dT%H:%MZ}", variants_tried=vt))
p = os.path.join(OUT, "leaderboard_extra_WN.json"); old = [r for r in json.load(open(p)) if not r["variant"].startswith("WN_B2_")]
json.dump(old + out, open(p, "w"), indent=0)
for r in out: print(r["variant"], r["trades"], r["mean_ret"], r["ci95_mean_ret"], r["n_out_of_sample"], r["oos_mean_ret"], r["score_total"], r["candidate"])
print("cut", dt.datetime.fromtimestamp(cut, dt.timezone.utc), "variants_tried", vt)
