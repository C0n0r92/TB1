import pickle, json, statistics
import scoring
from if_backtest import stats, EXITS, WS, RS, DELAYS, boot
meta, G = pickle.load(open("out/.if_grid.pkl", "rb")); res = pickle.load(open("out/.if_res.pkl", "rb"))
def nm(k): W, R, d, (tp, sl, h) = k; return f"IF_w{W}_r{int(R)}_d{d:02d}_tp{int(tp*100):02d}_sl{int(sl*100):02d}_h{h:02d}"
cfgs = [{"name": nm(k), "family": "inflow_proxy", "W": k[0], "R": k[1], "delay": k[2], "tp": k[3][0], "sl": k[3][1], "hold": k[3][2], "src": "backfill_1m_vol_proxy"} for k in G]
rk = sorted([k for k in res if res[k][1]["n"] >= 20], key=lambda k: -res[k][1]["mean"])
pick = list(dict.fromkeys(rk[:5] + [(W, R, 15, ex) for W in WS for R in RS for ex in ((0.2, 0.15, 30), (0.2, 0.15, 60))]
                          + [(5, 2.0, d, (0.08, 0.15, 5)) for d in DELAYS]))
span_h = (meta["span"][1] - meta["span"][0]) / 3600
rows = []
for k in pick:
    tr = sorted(G[k], key=lambda t: t["t"]); a, i, o, b, bi, bo = res[k]
    closed = [{"ret": t["net_p1"], "is_oos": t["oos"], "t": t["t"], "pnl": t["net_p1"] * 10} for t in tr]
    mc = scoring.mc_drawdown([c["pnl"] for c in closed], 100.0)
    st_all = {"trades": len(tr), "mean_ret": a["mean"], "ci_lo": a["ci"][0]}
    sc = scoring.score(st_all, None, closed, mc)
    pn = [c["pnl"] for c in closed]
    rows.append({"variant": nm(k), "trades": len(tr), "win_rate": round(a["win"], 3), "net_profit_after_costs": round(sum(pn), 2), "max_drawdown": "",
        "holds_out_of_sample": "no", "n_in_sample": i["n"], "n_out_of_sample": o["n"], "mean_ret": round(a["mean"], 4), "median_ret": round(a["median"], 4),
        "ci95_mean_ret": f"[{a['ci'][0]:.4f},{a['ci'][1]:.4f}]", "oos_mean_ret": round(o["mean"], 4) if o["n"] else "",
        "in_net_pnl": round(sum(c["pnl"] for c in closed if not c["is_oos"]), 2), "out_net_pnl": round(sum(c["pnl"] for c in closed if c["is_oos"]), 2),
        **{x: sc[x] for x in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
        "net_ex_best_trade": round(sum(pn) - max(pn), 2), "mc_dd_p5": round(mc[0], 3), "mc_dd_p50": round(mc[1], 3), "mc_dd_p95": round(mc[2], 3),
        "candidate": "no", "lucky_number": "n/a (not profitable)", "family": "inflow_proxy",
        "note": f"PAPER inflow-spike PROXY (1m volume spike + green window, no buyer data), {meta['n_pools']} on-chain sampled graduations, $10-equivalent pnl at 0.04 SOL costs (2%/side+slip+prio 0.0001); base mean {b['mean']:+.4f}; see out/inflow.md"})
st = {"variant_configs": cfgs, "rows": rows}
json.dump(st, open("out/.if_rows.json", "w"), indent=0)
for r in rows[:5]: print(r["variant"], r["score_total"], r["sc_oos_risk"], r["sc_drawdown"], r["sc_trades"], r["sc_edge"], r["sc_stability"], r["nights"], r["nights_profitable"], r["net_ex_best_trade"])
print(len(rows), "rows;", max(r["score_total"] for r in rows), "best score")
