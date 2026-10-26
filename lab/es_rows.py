#!/usr/bin/env python3
"""PAPER ONLY. Scored leaderboard rows ES_* from out/es_rules.json: pooled winners' entries, in-sample = batch 1 wallets,
out-of-sample = batch 2 wallets (held out by wallet; rules pre-registered on b1). $5 stake on $100. -> out/.es_rows.json (staging for merge_extra.py ES)."""
import json, statistics as S
from cl_sim import boot
from scoring import mc_drawdown, score
R = json.load(open("out/es_rules.json")); rows = []; cfgs = []
for nm, tr in R["trades"].items():
    if nm == "ACTUAL": continue
    tr = [dict(x, is_oos=x["b"] == "b2", pnl=5 * x["ret"]) for x in tr]
    rets = [x["ret"] for x in tr]; oos = [x for x in tr if x["is_oos"]]; ci = boot(rets); oci = boot([x["ret"] for x in oos])
    st = dict(trades=len(tr), mean_ret=S.fmean(rets), ci_lo=ci[0]); mc = mc_drawdown([x["pnl"] for x in tr], 100.0); sc = score(st, None, tr, mc)
    pn = [x["pnl"] for x in sorted(tr, key=lambda x: x["t"])]; eq = pk = dd = 0
    for p in pn: eq += p; pk = max(pk, eq); dd = max(dd, pk - eq)
    oosm = S.fmean([x["ret"] for x in oos]); inp = sum(x["pnl"] for x in tr if not x["is_oos"])
    holds = "insufficient" if len(oos) < 20 else ("yes" if inp > 0 and oosm > 0 and oci[0] > 0 else "no")
    cand = "yes" if sc["score_total"] >= 18 and len(tr) >= 50 and holds == "yes" else "no"
    rr = R["rows"][nm]
    rows.append(dict(variant=nm, trades=len(tr), win_rate=round(sum(r > 0 for r in rets) / len(rets), 3), net_profit_after_costs=round(sum(pn), 2), max_drawdown=round(dd, 2),
        holds_out_of_sample=f"{holds} (n_out={len(oos)})", n_in_sample=len(tr) - len(oos), n_out_of_sample=len(oos), mean_ret=round(st["mean_ret"], 4), median_ret=round(S.median(rets), 4),
        ci95_mean_ret=f"[{ci[0]:+.2f},{ci[1]:+.2f}]", oos_mean_ret=round(oosm, 4), in_net_pnl=round(inp, 2), out_net_pnl=round(sum(x["pnl"] for x in oos), 2),
        net_ex_best_trade=round(sum(pn) - max(pn), 2), mc_dd_p5=round(mc[0], 3), mc_dd_p50=round(mc[1], 3), mc_dd_p95=round(mc[2], 3), **sc, candidate=cand,
        lucky_number=R["luck"].get(nm, "n/a (baseline)"), family="es_exit_signal",
        note=f"exit-signal rule on winners' own entries; IS=b1 wallets {rr['b1']['mean']:+.3f}, OOS=b2 wallets {rr['b2']['mean']:+.3f}; date split early {rr['early']['mean']:+.3f} / late {rr['late']['mean']:+.3f} (cut {R['cut'][:16]}Z)"))
    cfgs.append(dict(name=nm, family="es_exit_signal", key=nm, study="winners_exit_signal_2026-10-24"))
json.dump(dict(rows=rows, variant_configs=cfgs), open("out/.es_rows.json", "w"), indent=0)
for r in rows: print(r["variant"], r["trades"], r["mean_ret"], r["ci95_mean_ret"], r["oos_mean_ret"], r["holds_out_of_sample"], r["score_total"], r["mc_dd_p95"], r["nights_profitable"] if "nights_profitable" in r else "", r["candidate"])
